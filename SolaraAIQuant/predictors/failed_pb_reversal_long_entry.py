"""
Solara AI Quant — Failed Pullback Reversal LONG Entry Predictor
===============================================================

Runs the H1 reversal entry model (reversal_entry_H1_long.joblib) for the
Failed Pullback Reversal LONG strategy.

Entry conditions (all must pass per symbol):
  1. H4 failed pullback condition met (computed by FE):
       - Prior H4 trend was DOWN (trend_dir_encoded == -1)
       - PB model exhaust_prob < 0.40  (low → pullback NOT exhausting → trend failing)
       - Pullback active for ≥ 2 consecutive H4 bars
  2. Entry signal: H1 reversal entry model prob ≥ threshold (auto-tuned, default 0.80)

This model is LONG-only. Direction is not configurable via model_type.

Model artifact (reversal_entry_H1_long.joblib):
  pkg['model']        → XGBoost binary classifier
  pkg['feature_cols'] → list[str], ~50 features
  pkg['threshold']    → float, auto-tuned (default 0.80)
  pkg['sl_pips']      → 20
  pkg['tp_pips']      → 30

Magic number: 500501
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from .base_predictor import BasePredictor

logger = logging.getLogger(__name__)

_DEFAULT_ENTRY_THRESHOLD = 0.80

# Superset of expected feature names — predictor uses pkg['feature_cols'] at runtime
ENTRY_FEATURES = [
    'bb_position', 'bb_width_pct', 'rsi_value', 'volume_ratio',
    'candle_body_pct', 'atr_pct', 'trend_strength',
    'prev_candle_body_pct', 'prev_volume_ratio', 'gap_from_prev_close',
    'bb_touch_strength', 'candle_rejection', 'rsi_divergence',
    'price_momentum', 'prev_was_rally', 'previous_touches',
    'time_since_last_touch', 'resistance_distance_pct', 'support_distance_pct',
    'prev_was_selloff',
    'bb_touch_strength_long', 'candle_rejection_long',
    'rsi_divergence_long', 'price_momentum_long',
    'previous_touches_long', 'time_since_last_touch_long',
    'close_location', 'upper_wick_ratio', 'lower_wick_ratio', 'body_size_atr',
    'h4_fpb_label', 'h4_trend_dir_encoded',
    'h4_trend_prob_up', 'h4_trend_prob_down',
    'h4_pb_exhaust_prob', 'h4_exhaust_prob_slope',
    'h4_pullback_duration_bars', 'candles_since_failure',
    'h4_trend_conviction_delta',
    'h4_d1_trend_agreement', 'h4_d1_prob_against_trend',
    'h4_w1_d1_h4_alignment_score',
    'h1_momentum_vs_trend', 'h1_rsi_divergence_from_trend',
    'bars_since_pb_start',
    'rsi_slope_5', 'rsi_above_50', 'bb_pos_slope_3',
    'h1_higher_low', 'h1_new_high_3', 'h1_consecutive_bull', 'h1_volume_surge',
    'session_london', 'session_new_york', 'session_asian', 'session_other',
]


class FailedPBReversalLongEntryPredictor(BasePredictor):
    """
    Failed Pullback Reversal LONG entry predictor.

    Two sequential gates:
      Gate 1 — _fpb_condition_met: H4-level conditions (prior downtrend +
               low exhaust prob + active pullback). Computed by FE.
      Gate 2 — entry_prob ≥ threshold: XGBoost reversal entry model.

    After each predict() call, self._last_cycle_results holds per-symbol
    outcome dict for cycle_digest logging.
    """

    _entry_threshold : float      = _DEFAULT_ENTRY_THRESHOLD
    _feature_cols    : List[str]  = []
    _last_cycle_results: Dict     = {}

    # ─────────────────────────────────────────────────────────────────────────
    # BasePredictor interface
    # ─────────────────────────────────────────────────────────────────────────

    def load_model(self, model_path: Path):
        """Load the reversal entry joblib and unpack components."""
        # Guard parallel-thread case: ensure vendor/ is in sys.path
        import sys
        _saq_root   = Path(__file__).resolve().parent.parent
        _vendor_dir = str(_saq_root / 'vendor')
        if _vendor_dir not in sys.path:
            sys.path.insert(0, _vendor_dir)

        pkg = joblib.load(model_path)
        self._feature_cols    = pkg.get('feature_cols', ENTRY_FEATURES)
        self._entry_threshold = float(pkg.get('threshold', _DEFAULT_ENTRY_THRESHOLD))
        logger.info(
            f"[FPBRevLongEntry] Model loaded — "
            f"threshold={self._entry_threshold:.2f}  "
            f"features={len(self._feature_cols)}  "
            f"sl={pkg.get('sl_pips')}p  tp={pkg.get('tp_pips')}p"
        )
        return pkg['model']

    def get_required_features(self) -> List[str]:
        """All model features + gate columns used by this predictor."""
        base      = self._feature_cols if self._feature_cols else ENTRY_FEATURES
        gate_cols = ['_fpb_condition_met', '_fpb_exhaust_prob', '_fpb_pullback_duration', 'close']
        return base + [c for c in gate_cols if c not in base]

    def predict(self, df_features: pd.DataFrame, config) -> List[Dict]:
        if not self.model_loaded or self.model is None:
            logger.warning("[FPBRevLongEntry] Model not loaded")
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

    def _predict_row(self, row, config) -> Optional[dict]:
        sym = row.get('symbol', 'UNKNOWN')

        _digest = {
            'fpb_condition':  bool(row.get('_fpb_condition_met', False)),
            'exhaust_prob':   float(row.get('_fpb_exhaust_prob', 1.0)),
            'pb_duration':    int(row.get('_fpb_pullback_duration', 0)),
            'entry_prob':     0.0,
            'gate':           99,
        }

        # ── Gate 1: H4 failed pullback condition ───────────────────────────
        if not row.get('_fpb_condition_met', False):
            _digest['gate'] = 1
            self._last_cycle_results[sym] = _digest
            logger.debug(
                f"[FPBRevLongEntry] {sym}: FPB condition not met "
                f"(exhaust={_digest['exhaust_prob']:.3f} "
                f"dur={_digest['pb_duration']}) — skip"
            )
            return None

        # ── Gate 2: entry model ────────────────────────────────────────────
        live_threshold = self._entry_threshold
        if hasattr(config, 'get_min_confidence'):
            live_threshold = config.get_min_confidence()
        elif hasattr(config, 'min_confidence'):
            live_threshold = float(config.min_confidence)

        feature_cols = self._feature_cols if self._feature_cols else ENTRY_FEATURES
        X = self._build_feature_row(row, feature_cols)
        if X is None:
            _digest['gate'] = 99
            self._last_cycle_results[sym] = _digest
            return None

        try:
            entry_prob = float(self.model.predict_proba(X)[0, 1])
        except Exception as exc:
            _digest['gate'] = 99
            self._last_cycle_results[sym] = _digest
            logger.error(f"[FPBRevLongEntry] {sym}: predict_proba failed: {exc}")
            return None

        _digest['entry_prob'] = entry_prob

        if entry_prob < live_threshold:
            _digest['gate'] = 2
            self._last_cycle_results[sym] = _digest
            logger.debug(
                f"[FPBRevLongEntry] {sym}: entry_prob={entry_prob:.3f} < "
                f"{live_threshold:.2f} — skip"
            )
            return None

        # ── All gates passed → LONG signal ────────────────────────────────
        _digest['gate'] = 0
        self._last_cycle_results[sym] = _digest

        entry_price = float(row.get('close', 0.0))
        if entry_price <= 0:
            return None

        tp_pips = getattr(config, 'tp_pips', 30)
        sl_pips = getattr(config, 'sl_pips', 20)
        magic   = getattr(config, 'magic', 0)
        comment = getattr(config, 'comment', 'FPBRev_Long')

        exhaust_prob = float(row.get('_fpb_exhaust_prob', 1.0))
        pb_dur       = int(row.get('_fpb_pullback_duration', 0))

        logger.info(
            f"[FPBRevLongEntry] {sym} LONG SIGNAL — "
            f"exhaust={exhaust_prob:.3f}  pb_dur={pb_dur}  "
            f"entry_prob={entry_prob:.3f}  price={entry_price}  "
            f"tp={tp_pips}p  sl={sl_pips}p"
        )

        return {
            'symbol':      sym,
            'direction':   'LONG',
            'confidence':  entry_prob,
            'entry_price': entry_price,
            'tp_pips':     tp_pips,
            'sl_pips':     sl_pips,
            'model_name':  getattr(config, 'name', 'Failed PB Reversal Long'),
            'magic':       magic,
            'comment':     comment,
            'features': {
                'exhaust_prob':       round(exhaust_prob, 4),
                'pb_duration':        pb_dur,
                'entry_prob':         round(entry_prob, 4),
                'h4_trend_dir':       int(row.get('h4_trend_dir_encoded', 0)),
                'candles_since_fail': float(row.get('candles_since_failure', 99)),
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
                f"[FPBRevLongEntry] {row.get('symbol','?')}: "
                f"{len(missing)} features missing, filled 0"
            )

        return pd.DataFrame([values])[feature_cols]


