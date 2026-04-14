"""
Solara AI Quant — Pull Back Entry Predictor
============================================

Runs the H1 entry model (entry_H1.joblib) for the Pull Back strategy.

Entry conditions (all must pass per symbol):
  1. Trend alignment:  ≥ 2/3 of (W1, D1, H4) trend models agree on direction
  2. Pullback exhaust: H4 pullback model class-2 prob ≥ 0.65
  3. Entry signal:     H1 entry model prob ≥ 0.80

One predictor class handles both LONG and SHORT via config.model_type.
Direction comes from the consensus trend (_pb_direction from the FE).

Model artifact (entry_H1.joblib):
  pkg['model']        → XGBoost binary classifier
  pkg['feature_cols'] → list[str], 37 features
  pkg['threshold']    → float, default 0.80
  pkg['sl_pips']      → int
  pkg['tp_pips']      → int

Magic numbers:
  LONG  → 500301  (XX=50 Pull Back, YY=03 H1, ZZ=01 Long)
  SHORT → 500302
"""

import logging
from pathlib import Path
from typing import List, Dict

import joblib
import numpy as np
import pandas as pd

from .base_predictor import BasePredictor, PredictionSignal

logger = logging.getLogger(__name__)

# Confidence gates used by the FE (replicated here for clarity / pre-filter log)
_PB_EXHAUST_THRESHOLD = 0.65
_ENTRY_THRESHOLD      = 0.80   # default; overridden by pkg['threshold'] at load

# Features the entry model expects (must match ENTRY_FEATURES in pull_back_features.py)
ENTRY_FEATURES = [
    'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
    'candle_body_pct', 'atr_pct', 'trend_strength',
    'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
    'session',
    'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
    'price_momentum', 'prev_was_rally', 'previous_touches', 'time_since_last_touch',
    'bb_touch_strength_long', 'candle_rejection_long', 'rsi_divergence_long',
    'price_momentum_long', 'prev_was_selloff', 'previous_touches_long',
    'time_since_last_touch_long',
    'close_location', 'upper_wick_ratio', 'lower_wick_ratio',
    'h4_pb_label', 'h4_pb_depth', 'h4_trend_dir',
    'h4_trend_prob_up', 'h4_trend_prob_down',
    'candles_since_exhaustion',
    'h4_pb_prob_trend', 'h4_pb_prob_pullback', 'h4_pb_prob_exhaust',
]


class PullBackEntryPredictor(BasePredictor):
    """
    Pull Back Entry predictor — LONG or SHORT depending on config.model_type.

    Gating logic (applied before the XGBoost entry model):
      1. _pb_trend_aligned == True (FE computed ≥ 2/3 trend alignment)
      2. _pb_direction matches this instance's model_type
         (LONG → 'uptrend', SHORT → 'downtrend')
      3. _pb_exhaust_prob >= _PB_EXHAUST_THRESHOLD (0.65)
      4. entry_prob (from XGBoost) >= threshold (0.80)
    """

    _entry_threshold : float = _ENTRY_THRESHOLD
    _feature_cols    : List[str] = []

    # ─────────────────────────────────────────────────────────────────────────
    # BasePredictor interface
    # ─────────────────────────────────────────────────────────────────────────

    def load_model(self, model_path: Path):
        """Load joblib package and unpack components."""
        pkg = joblib.load(model_path)
        self._feature_cols    = pkg.get('feature_cols', ENTRY_FEATURES)
        self._entry_threshold = float(pkg.get('threshold', _ENTRY_THRESHOLD))
        logger.info(
            f"[PullBackEntry] Model loaded — "
            f"threshold={self._entry_threshold:.2f}  "
            f"features={len(self._feature_cols)}  "
            f"sl={pkg.get('sl_pips')}  tp={pkg.get('tp_pips')}"
        )
        return pkg['model']

    def get_required_features(self) -> List[str]:
        # 37 model features + gate columns the predictor reads for gating logic
        base = self._feature_cols if self._feature_cols else ENTRY_FEATURES
        gate_cols = [
            '_pb_trend_aligned', '_pb_direction',
            '_pb_exhaust_prob', '_pb_h4_label', 'close',
        ]
        return base + [c for c in gate_cols if c not in base]

    def predict(self, df_features: pd.DataFrame, config) -> List[Dict]:
        if not self.model_loaded or self.model is None:
            logger.warning("[PullBackEntry] Model not loaded")
            return []

        if df_features is None or len(df_features) == 0:
            return []

        _mt = getattr(config, 'model_type', 'LONG')
        model_type = _mt.value.upper() if hasattr(_mt, 'value') else str(_mt).upper()
        required_direction = 'uptrend' if model_type == 'LONG' else 'downtrend'

        signals = []
        for _, row in df_features.iterrows():
            sig = self._predict_row(row, config, required_direction, model_type)
            if sig is not None:
                signals.append(sig)

        return signals

    # ─────────────────────────────────────────────────────────────────────────
    # Per-row inference
    # ─────────────────────────────────────────────────────────────────────────

    def _predict_row(self, row, config, required_direction: str, model_type: str):
        sym = row.get('symbol', 'UNKNOWN')

        # ── Gate 1: trend alignment ────────────────────────────────────────
        if not row.get('_pb_trend_aligned', False):
            logger.debug(f"[PullBackEntry] {sym}: trend not aligned — skip")
            return None

        # ── Gate 2: direction match ────────────────────────────────────────
        pb_dir = row.get('_pb_direction', 'sideways')
        if pb_dir != required_direction:
            logger.debug(f"[PullBackEntry] {sym}: direction {pb_dir} ≠ {required_direction} — skip")
            return None

        # ── Gate 3: pullback exhaustion probability ────────────────────────
        exhaust_prob = float(row.get('_pb_exhaust_prob', 0.0))
        if exhaust_prob < _PB_EXHAUST_THRESHOLD:
            logger.debug(f"[PullBackEntry] {sym}: exhaust_prob={exhaust_prob:.3f} < {_PB_EXHAUST_THRESHOLD} — skip")
            return None

        # ── Gate 4: entry model ────────────────────────────────────────────
        feature_cols = self._feature_cols if self._feature_cols else ENTRY_FEATURES
        X = self._build_feature_row(row, feature_cols)
        if X is None:
            return None

        try:
            entry_prob = float(self.model.predict_proba(X)[0, 1])
        except Exception as exc:
            logger.error(f"[PullBackEntry] {sym}: predict_proba failed: {exc}")
            return None

        if entry_prob < self._entry_threshold:
            logger.debug(f"[PullBackEntry] {sym}: entry_prob={entry_prob:.3f} < {self._entry_threshold} — skip")
            return None

        # ── Build signal ───────────────────────────────────────────────────
        entry_price = float(row.get('close', 0.0))
        if entry_price <= 0:
            return None

        tp_pips = getattr(config, 'tp_pips', 30)
        sl_pips = getattr(config, 'sl_pips', 20)
        magic   = getattr(config, 'magic', 0)
        comment = getattr(config, 'comment', 'PB_Entry')

        logger.info(
            f"[PullBackEntry] {sym} {model_type} SIGNAL — "
            f"exhaust={exhaust_prob:.3f} entry={entry_prob:.3f} "
            f"price={entry_price} tp={tp_pips} sl={sl_pips}"
        )

        return {
            'symbol':      sym,
            'direction':   model_type,
            'confidence':  entry_prob,
            'entry_price': entry_price,
            'tp_pips':     tp_pips,
            'sl_pips':     sl_pips,
            'model_name':  getattr(config, 'name', 'Pull Back Entry'),
            'magic':       magic,
            'comment':     comment,
            'features': {
                'exhaust_prob':          round(exhaust_prob, 4),
                'entry_prob':            round(entry_prob, 4),
                'h4_pb_label':           int(row.get('h4_pb_label', 0)),
                'candles_since_exhaust': float(row.get('candles_since_exhaustion', 99)),
                'h4_trend_dir':          int(row.get('h4_trend_dir', 0)),
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build_feature_row(self, row, feature_cols: List[str]):
        """Build a single-row DataFrame for predict_proba."""
        values = {}
        missing = []
        for col in feature_cols:
            val = row.get(col, np.nan)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                missing.append(col)
                values[col] = 0.0
            else:
                values[col] = float(val)

        if missing:
            logger.debug(f"[PullBackEntry] {row.get('symbol','?')}: {len(missing)} features missing, filled 0")

        return pd.DataFrame([values])[feature_cols]
