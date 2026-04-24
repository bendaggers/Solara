"""
Solara AI Quant — Trend Reversal SHORT Entry Predictor
========================================================

Loads reversal_H4_short.joblib and fires SHORT signals when:
  Gate 1 — _rev_break_detected == True  (FE confirmed cascade flip + structure break)
  Gate 2 — predict_proba >= threshold   (XGBoost reversal classifier ≥ 0.74)

This is a 2-gate model — much simpler than the Pull Back 4-gate pipeline.
The feature engineer (ReversalShortFeatureEngineer) handles all the heavy
detection logic before predict() is called.

Model artifact (reversal_H4_short.joblib):
  pkg['model']        → fitted XGBClassifier
  pkg['feature_cols'] → list[str], 19 REVERSAL_FEATURES
  pkg['threshold']    → float (walk-forward optimised, default 0.74)
  pkg['direction']    → 'short'
  pkg['metadata']     → dict with WF stats

Magic number: 600401  (XX=60 Reversal, YY=04 H4, ZZ=01 Short)

Walk-forward validation results (5 folds, 2000–2025):
  Mean precision : 59.3% ± 10.9%
  Mean EV/trade  : +27.4 ± 8.7 pips
  Break-even prec: 25.0%  (SL=20p / TP=60p)
  Worst fold     : 44.4% precision (2019–2022, COVID era)
  All 5 folds    : positive EV
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional

import joblib
import numpy as np
import pandas as pd

from .base_predictor import BasePredictor, PredictionSignal

logger = logging.getLogger(__name__)

# Default threshold — overridden by pkg['threshold'] at load time
_DEFAULT_THRESHOLD = 0.74

# Feature list (must match ReversalShortFeatureEngineer.REVERSAL_FEATURES)
REVERSAL_FEATURES = [
    'break_magnitude_pips',
    'break_magnitude_atr',
    'break_magnitude_vs_impulse',
    'brk_body_pct_of_range',
    'brk_upper_wick_ratio',
    'brk_lower_wick_ratio',
    'brk_close_location',
    'brk_bb_position',
    'brk_volume_ratio',
    'brk_rsi_value',
    'brk_candle_rejection',
    'brk_bb_width_pct',
    'brk_trend_strength',
    'brk_candle_body_pct',
    'h4_prob_down_at_break',
    'd1_prob_down_at_break',
    'w1_prob_up_at_break',
    'impulse_range_pips',
    'prior_uptrend_bars',
]


class ReversalShortEntryPredictor(BasePredictor):
    """
    Trend Reversal SHORT entry predictor.

    Gating logic:
      1. _rev_break_detected == True  → FE confirmed H4 cascade flip + structure break
      2. reversal_prob >= threshold   → XGBoost confirms high-conviction break (≥ 0.74)

    On signal: places SHORT at current close, TP=60p, SL=20p.
    """

    _rev_threshold: float    = _DEFAULT_THRESHOLD
    _feature_cols:  List[str] = []

    # Populated after each predict() call — read by cycle_digest.py
    # {symbol: {'gate': int, 'prob': float}}
    # gate=0 → signal, gate=1 → no break, gate=2 → below threshold, gate=99 → error
    _last_cycle_results: Dict = {}

    # ─────────────────────────────────────────────────────────────────────────
    # BasePredictor interface
    # ─────────────────────────────────────────────────────────────────────────

    def load_model(self, model_path: Path):
        """Load joblib artifact and unpack components.

        NOTE: _rev_threshold is set here as a fallback from the .joblib.
        The actual gate threshold is overridden in predict() by config's
        get_min_confidence() — which reads the lowest confidence_tier from
        model_registry.yaml. This lets you tune the threshold in the registry
        without retraining. The joblib threshold (0.74) is the WF-optimised
        value; the registry value (currently 0.60) is the live-trading value.
        """
        pkg = joblib.load(model_path)
        self._feature_cols  = pkg.get('feature_cols', REVERSAL_FEATURES)
        self._rev_threshold = float(pkg.get('threshold', _DEFAULT_THRESHOLD))
        meta = pkg.get('metadata', {})
        logger.info(
            f"[ReversalShortEntry] Model loaded — "
            f"joblib_threshold={self._rev_threshold:.2f}  "
            f"features={len(self._feature_cols)}  "
            f"direction={pkg.get('direction', 'short')}  "
            f"WF_precision={meta.get('wf_precision_mean', '?')}  "
            f"WF_ev={meta.get('wf_ev_mean', '?')}p  "
            f"(live threshold set by registry confidence_tiers)"
        )
        return pkg['model']

    def get_required_features(self) -> List[str]:
        """19 model features + gate column the predictor reads."""
        base = self._feature_cols if self._feature_cols else REVERSAL_FEATURES
        gate_cols = ['_rev_break_detected', 'close']
        return base + [c for c in gate_cols if c not in base]

    def predict(self, df_features: pd.DataFrame, config) -> List[Dict]:
        if not self.model_loaded or self.model is None:
            logger.warning("[ReversalShortEntry] Model not loaded")
            return []

        if df_features is None or len(df_features) == 0:
            return []

        self._last_cycle_results = {}

        signals = []
        for _, row in df_features.iterrows():
            sig = self._predict_row(row, config)
            if sig is not None:
                signals.append(sig)

        return signals

    # ─────────────────────────────────────────────────────────────────────────
    # Per-row inference
    # ─────────────────────────────────────────────────────────────────────────

    def _predict_row(self, row, config) -> Optional[Dict]:
        sym = row.get('symbol', 'UNKNOWN')

        # ── Gate 1: break detected by FE ──────────────────────────────────
        if not row.get('_rev_break_detected', False):
            logger.debug(f"[ReversalShortEntry] {sym}: no break detected — skip")
            self._last_cycle_results[sym] = {'gate': 1, 'prob': 0.0}
            return None

        # ── Gate 2: reversal classifier ───────────────────────────────────
        # Use the registry's minimum confidence tier as the live threshold.
        # This lets the threshold be tuned in model_registry.yaml without retraining.
        # Falls back to joblib threshold (_rev_threshold) if config has no tiers.
        live_threshold = self._rev_threshold
        if hasattr(config, 'get_min_confidence'):
            live_threshold = config.get_min_confidence()
        elif hasattr(config, 'min_confidence'):
            live_threshold = float(config.min_confidence)

        feature_cols = self._feature_cols if self._feature_cols else REVERSAL_FEATURES
        X = self._build_feature_row(row, feature_cols)
        if X is None:
            self._last_cycle_results[sym] = {'gate': 99, 'prob': 0.0}
            return None

        try:
            reversal_prob = float(self.model.predict_proba(X)[0, 1])
        except Exception as exc:
            logger.error(f"[ReversalShortEntry] {sym}: predict_proba failed: {exc}")
            self._last_cycle_results[sym] = {'gate': 99, 'prob': 0.0}
            return None

        if reversal_prob < live_threshold:
            logger.debug(
                f"[ReversalShortEntry] {sym}: reversal_prob={reversal_prob:.3f} "
                f"< {live_threshold:.2f} — skip"
            )
            self._last_cycle_results[sym] = {'gate': 2, 'prob': reversal_prob}
            return None

        # ── Signal ────────────────────────────────────────────────────────
        self._last_cycle_results[sym] = {'gate': 0, 'prob': reversal_prob}

        entry_price = float(row.get('close', 0.0))
        if entry_price <= 0:
            return None

        tp_pips = getattr(config, 'tp_pips', 60)
        sl_pips = getattr(config, 'sl_pips', 20)
        magic   = getattr(config, 'magic', 0)
        comment = getattr(config, 'comment', 'Rev_Short')

        logger.info(
            f"[ReversalShortEntry] {sym} SHORT SIGNAL — "
            f"reversal_prob={reversal_prob:.3f}  "
            f"break_mag={row.get('break_magnitude_pips', 0):.1f}p  "
            f"h4_pd={row.get('h4_prob_down_at_break', 0):.3f}  "
            f"price={entry_price}  tp={tp_pips}p  sl={sl_pips}p"
        )

        return {
            'symbol':      sym,
            'direction':   'SHORT',
            'confidence':  reversal_prob,
            'entry_price': entry_price,
            'tp_pips':     tp_pips,
            'sl_pips':     sl_pips,
            'model_name':  getattr(config, 'name', 'Trend Reversal Short'),
            'magic':       magic,
            'comment':     comment,
            'features': {
                'reversal_prob':       round(reversal_prob, 4),
                'break_mag_pips':      round(float(row.get('break_magnitude_pips', 0)), 2),
                'break_mag_atr':       round(float(row.get('break_magnitude_atr', 0)), 3),
                'brk_body_pct':        round(float(row.get('brk_body_pct_of_range', 0)), 3),
                'brk_volume_ratio':    round(float(row.get('brk_volume_ratio', 0)), 3),
                'h4_prob_down':        round(float(row.get('h4_prob_down_at_break', 0)), 3),
                'prior_uptrend_bars':  int(row.get('prior_uptrend_bars', 0)),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build_feature_row(self, row, feature_cols: List[str]):
        """Build a single-row DataFrame for predict_proba."""
        values  = {}
        missing = []
        for col in feature_cols:
            val = row.get(col, np.nan)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                missing.append(col)
                values[col] = 0.0
            else:
                values[col] = float(val)

        if missing:
            logger.debug(
                f"[ReversalShortEntry] {row.get('symbol','?')}: "
                f"{len(missing)} features missing (filled 0): {missing[:5]}"
            )

        return pd.DataFrame([values])[feature_cols]
