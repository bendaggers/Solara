"""
Solara AI Quant — Trend Reversal LONG Entry Predictor
=======================================================

Mirror of reversal_short_entry.py for the LONG direction.
Loads reversal_H4_long.joblib and fires LONG signals when:
  Gate 1 — _rev_break_detected == True  (FE confirmed cascade flip + structure break above swing_high)
  Gate 2 — predict_proba >= threshold   (XGBoost reversal classifier, threshold set by registry)

Walk-forward validation results (5 folds, 2000–2025):
  Mean precision : 50.9% ± 7.4%
  Mean EV/trade  : +20.7 ± 5.9 pips
  Break-even prec: 25.0%  (SL=20p / TP=60p)
  All 5 folds    : positive EV
  Live threshold : 0.50 (registry) vs 0.76 (WF-optimised) for higher frequency

Magic number: 600402  (XX=60 Reversal, YY=04 H4, ZZ=02 Long)
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional

import joblib
import numpy as np
import pandas as pd

from .base_predictor import BasePredictor, PredictionSignal

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 0.76   # WF median; overridden by registry to 0.50

REVERSAL_LONG_FEATURES = [
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
    'h4_prob_up_at_break',
    'd1_prob_up_at_break',
    'w1_prob_down_at_break',
    'impulse_range_pips',
    'prior_downtrend_bars',
]


class ReversalLongEntryPredictor(BasePredictor):
    """
    Trend Reversal LONG entry predictor.

    Gate 1: _rev_break_detected == True  (cascade flip downtrend→uptrend + close > swing_high)
    Gate 2: reversal_prob >= live_threshold (from registry confidence_tiers, default 0.50)
    """

    _rev_threshold: float    = _DEFAULT_THRESHOLD
    _feature_cols:  List[str] = []

    def load_model(self, model_path: Path):
        pkg = joblib.load(model_path)
        self._feature_cols  = pkg.get('feature_cols', REVERSAL_LONG_FEATURES)
        self._rev_threshold = float(pkg.get('threshold', _DEFAULT_THRESHOLD))
        meta = pkg.get('metadata', {})
        logger.info(
            f"[ReversalLongEntry] Model loaded — "
            f"joblib_threshold={self._rev_threshold:.2f}  "
            f"features={len(self._feature_cols)}  "
            f"WF_precision={meta.get('wf_precision_mean', '?')}  "
            f"WF_ev={meta.get('wf_ev_mean', '?')}p  "
            f"(live threshold set by registry confidence_tiers)"
        )
        return pkg['model']

    def get_required_features(self) -> List[str]:
        base = self._feature_cols if self._feature_cols else REVERSAL_LONG_FEATURES
        gate_cols = ['_rev_break_detected', 'close']
        return base + [c for c in gate_cols if c not in base]

    def predict(self, df_features: pd.DataFrame, config) -> List[Dict]:
        if not self.model_loaded or self.model is None:
            logger.warning("[ReversalLongEntry] Model not loaded")
            return []
        if df_features is None or len(df_features) == 0:
            return []
        signals = []
        for _, row in df_features.iterrows():
            sig = self._predict_row(row, config)
            if sig is not None:
                signals.append(sig)
        return signals

    def _predict_row(self, row, config) -> Optional[Dict]:
        sym = row.get('symbol', 'UNKNOWN')

        # ── Gate 1: break detected ─────────────────────────────────────────
        if not row.get('_rev_break_detected', False):
            logger.debug(f"[ReversalLongEntry] {sym}: no break detected — skip")
            return None

        # ── Gate 2: classifier (threshold from registry) ───────────────────
        live_threshold = self._rev_threshold
        if hasattr(config, 'get_min_confidence'):
            live_threshold = config.get_min_confidence()
        elif hasattr(config, 'min_confidence'):
            live_threshold = float(config.min_confidence)

        feature_cols = self._feature_cols if self._feature_cols else REVERSAL_LONG_FEATURES
        X = self._build_feature_row(row, feature_cols)
        if X is None:
            return None

        try:
            reversal_prob = float(self.model.predict_proba(X)[0, 1])
        except Exception as exc:
            logger.error(f"[ReversalLongEntry] {sym}: predict_proba failed: {exc}")
            return None

        if reversal_prob < live_threshold:
            logger.debug(
                f"[ReversalLongEntry] {sym}: reversal_prob={reversal_prob:.3f} "
                f"< {live_threshold:.2f} — skip"
            )
            return None

        entry_price = float(row.get('close', 0.0))
        if entry_price <= 0:
            return None

        tp_pips = getattr(config, 'tp_pips', 60)
        sl_pips = getattr(config, 'sl_pips', 20)
        magic   = getattr(config, 'magic', 0)
        comment = getattr(config, 'comment', 'Rev_Long')

        logger.info(
            f"[ReversalLongEntry] {sym} LONG SIGNAL — "
            f"reversal_prob={reversal_prob:.3f}  "
            f"break_mag={row.get('break_magnitude_pips', 0):.1f}p  "
            f"h4_pu={row.get('h4_prob_up_at_break', 0):.3f}  "
            f"price={entry_price}  tp={tp_pips}p  sl={sl_pips}p"
        )

        return {
            'symbol':      sym,
            'direction':   'LONG',
            'confidence':  reversal_prob,
            'entry_price': entry_price,
            'tp_pips':     tp_pips,
            'sl_pips':     sl_pips,
            'model_name':  getattr(config, 'name', 'Trend Reversal Long'),
            'magic':       magic,
            'comment':     comment,
            'features': {
                'reversal_prob':        round(reversal_prob, 4),
                'break_mag_pips':       round(float(row.get('break_magnitude_pips', 0)), 2),
                'break_mag_atr':        round(float(row.get('break_magnitude_atr', 0)), 3),
                'brk_body_pct':         round(float(row.get('brk_body_pct_of_range', 0)), 3),
                'brk_volume_ratio':     round(float(row.get('brk_volume_ratio', 0)), 3),
                'h4_prob_up':           round(float(row.get('h4_prob_up_at_break', 0)), 3),
                'prior_downtrend_bars': int(row.get('prior_downtrend_bars', 0)),
            },
        }

    def _build_feature_row(self, row, feature_cols: List[str]):
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
                f"[ReversalLongEntry] {row.get('symbol','?')}: "
                f"{len(missing)} features missing (filled 0)"
            )
        return pd.DataFrame([values])[feature_cols]
