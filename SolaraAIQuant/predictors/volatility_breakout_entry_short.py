"""
Solara AI Quant — Volatility Breakout Entry SHORT Predictor
============================================================

Loads entry_breakout_H1_short.joblib and fires SHORT signals when:
  Gate 1 — _vb_break_detected == True
              (FE confirmed: active compression zone + excursion gate + breakout
               model class-1 probability >= bc['threshold'])
  Gate 2 — entry_prob >= em['threshold']  (0.496)
              (XGBoost entry classifier confirms winning SHORT)

The feature engineer (VolatilityBreakoutShortFeatureEngineer) handles all heavy
lifting: compression detection, breakout model scoring, trend soft features.
This predictor only needs to gate on _vb_break_detected and run the entry model.

Model artifact (entry_breakout_H1_short.joblib):
  pkg['model']        → XGBClassifier (binary)
  pkg['feature_cols'] → list[str], 57 features
  pkg['threshold']    → float (walk-forward optimised, default 0.496)
  pkg['direction']    → 'short'
  pkg['sl_pips']      → 20
  pkg['tp_pips']      → 60

Magic number: 700301  (XX=70 VolBreakout, YY=03 H1, ZZ=01 Short)

Walk-forward validation (5 folds, 2003-2021, 28 pairs):
  Mean EV/trade: +8.0 pips  |  Win rate: 35.0%  |  Break-even: 25.0% (3:1 RR)
  All 5 folds positive after 2-pip round-trip cost.
  EURGBP excluded from production — 17.9% raw WR, 7pp below break-even.

Threshold note:
  The joblib threshold (0.496) is the walk-forward optimised value.
  The live threshold is overridden by registry confidence_tiers (get_min_confidence()).
  To tune without retraining, adjust confidence_tiers in model_registry.yaml.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional

import joblib
import numpy as np
import pandas as pd

from .base_predictor import BasePredictor, PredictionSignal

logger = logging.getLogger(__name__)

# Default threshold — overridden by pkg['threshold'] at load time, then by registry
_DEFAULT_THRESHOLD = 0.496


class VolatilityBreakoutEntryShortPredictor(BasePredictor):
    """
    Volatility Breakout SHORT entry predictor.

    Gating logic (2 gates):
      1. _vb_break_detected == True
            FE confirmed: active compression zone + excursion + breakout model
      2. entry_prob >= threshold
            XGBoost entry model confirms winning trade

    On signal: places SHORT at current H1 close, SL=20p above, TP=60p below (3:1 RR).
    """

    _entry_threshold: float    = _DEFAULT_THRESHOLD
    _feature_cols:    List[str] = []

    # Populated after each predict() call — read by cycle_digest.py
    # gate=0 → signal, gate=1 → no breakout (FE), gate=2 → below entry threshold, gate=99 → error
    _last_cycle_results: Dict = {}

    # ─────────────────────────────────────────────────────────────────────────
    # BasePredictor interface
    # ─────────────────────────────────────────────────────────────────────────

    def load_model(self, model_path: Path):
        """Load joblib artifact and unpack components.

        NOTE: _entry_threshold is set here as a fallback from the .joblib.
        The actual gate threshold is overridden in predict() by config's
        get_min_confidence() — which reads the lowest confidence_tier from
        model_registry.yaml. To tune the entry threshold in production,
        adjust confidence_tiers in model_registry.yaml without retraining.
        """
        pkg = joblib.load(model_path)
        self._feature_cols    = pkg.get('feature_cols', [])
        self._entry_threshold = float(pkg.get('threshold', _DEFAULT_THRESHOLD))
        meta = pkg.get('metadata', {})
        logger.info(
            f"[VBShortEntry] Entry model loaded — "
            f"joblib_threshold={self._entry_threshold:.3f}  "
            f"features={len(self._feature_cols)}  "
            f"direction={pkg.get('direction', 'short')}  "
            f"sl={pkg.get('sl_pips')}p  tp={pkg.get('tp_pips')}p  "
            f"(live threshold set by registry confidence_tiers)"
        )
        return pkg['model']

    def get_required_features(self) -> List[str]:
        """57 entry model features + gate column the predictor reads."""
        base      = self._feature_cols if self._feature_cols else []
        gate_cols = ['_vb_break_detected', 'close']
        return base + [c for c in gate_cols if c not in base]

    def predict(self, df_features: pd.DataFrame, config) -> List[Dict]:
        if not self.model_loaded or self.model is None:
            logger.warning("[VBShortEntry] Model not loaded — no predictions")
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

        # ── Gate 1: breakout confirmed by FE ──────────────────────────────
        if not row.get('_vb_break_detected', False):
            logger.debug(f"[VBShortEntry] {sym}: _vb_break_detected=False — skip")
            self._last_cycle_results[sym] = {'gate': 1, 'prob': 0.0}
            return None

        # ── Gate 2: entry model ───────────────────────────────────────────
        # Live threshold from registry confidence_tiers (lowest tier min_confidence).
        # Falls back to joblib threshold (_entry_threshold) if no registry tiers.
        live_threshold = self._entry_threshold
        if hasattr(config, 'get_min_confidence'):
            live_threshold = config.get_min_confidence()
        elif hasattr(config, 'min_confidence'):
            live_threshold = float(config.min_confidence)

        feature_cols = self._feature_cols if self._feature_cols else []
        if not feature_cols:
            logger.warning(f"[VBShortEntry] {sym}: no feature_cols loaded")
            return None

        X = self._build_feature_row(row, feature_cols)
        if X is None:
            return None

        try:
            entry_prob = float(self.model.predict_proba(X)[0, 1])
        except Exception as exc:
            logger.error(f"[VBShortEntry] {sym}: predict_proba failed: {exc}")
            self._last_cycle_results[sym] = {'gate': 99, 'prob': 0.0}
            return None

        if entry_prob < live_threshold:
            logger.debug(
                f"[VBShortEntry] {sym}: entry_prob={entry_prob:.3f} "
                f"< {live_threshold:.3f} — skip"
            )
            self._last_cycle_results[sym] = {
                'gate': 2, 'prob': entry_prob,
                'bp_valid': float(row.get('breakout_prob_valid', 0.0)),
            }
            return None

        self._last_cycle_results[sym] = {'gate': 0, 'prob': entry_prob}

        # ── Both gates passed → SHORT signal ──────────────────────────────
        entry_price = float(row.get('close', 0.0))
        if entry_price <= 0:
            logger.warning(f"[VBShortEntry] {sym}: invalid entry_price={entry_price}")
            return None

        tp_pips = getattr(config, 'tp_pips', 60)
        sl_pips = getattr(config, 'sl_pips', 20)
        magic   = getattr(config, 'magic', 0)
        comment = getattr(config, 'comment', 'VB_Short')

        logger.info(
            f"[VBShortEntry] {sym} SHORT SIGNAL — "
            f"entry_prob={entry_prob:.3f}  "
            f"bp_valid={row.get('breakout_prob_valid', 0):.3f}  "
            f"excursion={row.get('excursion_atr', 0):.2f}ATR  "
            f"comp_dur={row.get('comp_duration', 0):.0f}bars  "
            f"trend_h4={int(row.get('trend_dir_h4', 0))}  "
            f"price={entry_price}  tp={tp_pips}p  sl={sl_pips}p"
        )

        return {
            'symbol':      sym,
            'direction':   'SHORT',
            'confidence':  entry_prob,
            'entry_price': entry_price,
            'tp_pips':     tp_pips,
            'sl_pips':     sl_pips,
            'model_name':  getattr(config, 'name', 'Volatility Breakout Short'),
            'magic':       magic,
            'comment':     comment,
            'features': {
                'entry_prob':           round(entry_prob, 4),
                'breakout_prob_valid':  round(float(row.get('breakout_prob_valid', 0)), 4),
                'excursion_atr':        round(float(row.get('excursion_atr', 0)), 3),
                'comp_duration':        int(row.get('comp_duration', 0)),
                'comp_tightness':       round(float(row.get('comp_tightness', 0)), 3),
                'trend_dir_h4':         int(row.get('trend_dir_h4', 0)),
                'trend_alignment':      int(row.get('trend_alignment', 0)),
                'consecutive_bearish':  int(row.get('consecutive_bearish', 0)),
                'rsi_value':            round(float(row.get('rsi_value', 0)), 1),
                'vol_expansion':        round(float(row.get('vol_expansion', 0)), 2),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build_feature_row(self, row, feature_cols: List[str]) -> Optional[pd.DataFrame]:
        """Build a single-row DataFrame for predict_proba."""
        values  = {}
        missing = []
        for col in feature_cols:
            val = row.get(col, np.nan)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                missing.append(col)
                values[col] = 0.0
            else:
                try:
                    values[col] = float(val)
                except (TypeError, ValueError):
                    missing.append(col)
                    values[col] = 0.0

        if missing:
            logger.debug(
                f"[VBShortEntry] {row.get('symbol', '?')}: "
                f"{len(missing)} features missing (filled 0): {missing[:5]}"
            )

        return pd.DataFrame([values])[feature_cols]
