"""
Solara AI Quant - UBB Rejection Short Predictor

Upper Bollinger Band candle rejection short model.

Model artifact structure (dict):
    pkl['pipeline']     → sklearn Pipeline (expects DataFrame input)
    pkl['threshold']    → float, trained threshold (0.74)
    pkl['feature_cols'] → list[str], exact feature order for inference
    pkl['metadata']     → dict, training stats

Pre-filter (before model inference):
    1. Candle A must have a BB-event (a_bb_event_type > 0)
    2. Candle A RSI >= RSI_MIN (default 45)
    3. Candle B must be bearish (b_candle_body_pct < 0)
"""

from typing import List, Dict, Optional
from pathlib import Path
import logging

import pandas as pd
import numpy as np

from .base_predictor import BasePredictor, PredictionSignal

logger = logging.getLogger(__name__)

RSI_MIN = 45


class UBBRejectionPredictor(BasePredictor):
    """
    Upper BB Rejection Short — LightGBM A/B/C reversal model.
    The .pkl is a dict — load_model() unpacks it.
    """

    _feature_cols: List[str] = []
    _model_threshold: float  = 0.74

    def load_model(self, model_path: Path):
        """Unpack the dict artifact and return the sklearn Pipeline."""
        import pickle
        with open(model_path, 'rb') as f:
            artifact = pickle.load(f)

        if not isinstance(artifact, dict):
            raise ValueError(
                f"Expected dict artifact, got {type(artifact)}. "
                f"Keys expected: pipeline, threshold, feature_cols, metadata"
            )

        self._feature_cols    = artifact['feature_cols']
        self._model_threshold = float(artifact.get('threshold', 0.74))

        logger.info(
            f"UBB model loaded — threshold={self._model_threshold:.2f}  "
            f"features={len(self._feature_cols)}"
        )
        return artifact['pipeline']

    def get_required_features(self) -> List[str]:
        if self._feature_cols:
            return list(self._feature_cols)
        return [
            'session',
            'a_open', 'a_high', 'a_low',
            'a_bb_position', 'a_bb_width_pct', 'a_rsi_value',
            'a_volume_ratio', 'a_candle_rejection', 'a_candle_body_pct',
            'a_atr_pct', 'a_trend_strength', 'a_prev_volume_ratio',
            'a_price_momentum', 'a_previous_touches', 'a_time_since_last_touch',
            'a_support_distance_pct',
            'b_open', 'b_high', 'b_low', 'b_close',
            'b_bb_touch_strength', 'b_bb_position', 'b_bb_width_pct',
            'b_rsi_value', 'b_volume_ratio', 'b_candle_body_pct',
            'b_atr_pct', 'b_trend_strength', 'b_prev_candle_body_pct',
            'b_prev_volume_ratio', 'b_gap_from_prev_close',
            'b_price_momentum', 'b_support_distance_pct',
            'c_high', 'c_low', 'c_close',
            'c_bb_touch_strength', 'c_bb_position', 'c_bb_width_pct',
            'c_rsi_value', 'c_volume_ratio', 'c_candle_rejection',
            'c_candle_body_pct', 'c_atr_pct', 'c_trend_strength',
            'c_prev_candle_body_pct', 'c_prev_volume_ratio',
            'c_gap_from_prev_close', 'c_price_momentum',
            'c_time_since_last_touch', 'c_support_distance_pct',
            'a_bb_event_type', 'a_bb_event_strength',
            'a_close_above_ubb', 'a_near_upper_bb',
            'a_failed_break_ubb', 'a_ubb_distance_close',
            'a_upper_wick_pct',
        ]

    def predict(self, df_features: pd.DataFrame, config) -> List[Dict]:
        predictions = []

        if not self.model_loaded or self.model is None:
            logger.warning(f"UBB model not loaded: {config.name}")
            return predictions

        df = self.filter_by_symbols(df_features)
        if df.empty:
            return predictions

        if not self.validate_features(df, self.get_required_features()):
            return predictions

        for _, row in df.iterrows():
            try:
                signal = self._predict_row(row, config)
                if signal:
                    predictions.append(signal.to_dict())
            except Exception as e:
                logger.error(f"UBB: error on {row.get('symbol', '?')}: {e}")

        if predictions:
            logger.info(
                f"UBB Rejection: {len(predictions)} SHORT signal(s) generated"
            )

        return predictions

    def _predict_row(self, row: pd.Series, config) -> Optional[PredictionSignal]:
        symbol     = row.get('symbol', 'UNKNOWN')
        a_bb_event = int(float(row.get('a_bb_event_type', 0)))
        a_rsi      = float(row.get('a_rsi_value', 0))
        b_body_pct = float(row.get('b_candle_body_pct', 0))
        b_bearish  = b_body_pct < 0
        a_bb_pos   = float(row.get('a_bb_position', 0))
        a_near_ubb = int(float(row.get('a_near_upper_bb', 0)))
        a_close_ab = int(float(row.get('a_close_above_ubb', 0)))
        if config.confidence_tiers:
            threshold = min(t.min_confidence for t in config.confidence_tiers)
        else:
            threshold = float(getattr(config, 'min_confidence', self._model_threshold))

        base = (
            f"UBB: {symbol:<10}  "
            f"a_bb_event={a_bb_event}  "
            f"a_rsi={a_rsi:.1f}  "
            f"b_confirm={b_bearish}  "
            f"a_bb_pos={a_bb_pos:.3f}  "
            f"a_near_ubb={a_near_ubb}  "
            f"a_close_above={a_close_ab}"
        )

        # ── Pre-filter 1: Candle A BB event ───────────────────────────
        if a_bb_event == 0:
            logger.debug(f"{base}  | skip: no BB event")
            return None

        # ── Pre-filter 2: Candle A RSI ────────────────────────────────
        if a_rsi < RSI_MIN:
            logger.debug(f"{base}  | skip: RSI {a_rsi:.1f} < {RSI_MIN}")
            return None

        # ── Pre-filter 3: Candle B bearish ────────────────────────────
        if not b_bearish:
            logger.debug(
                f"{base}  | skip: B not bearish (body={b_body_pct:+.4f})"
            )
            return None

        # ── Model inference ────────────────────────────────────────────
        # Pipeline expects a DataFrame with named columns — NOT a numpy array
        X = self._prepare_features(row)
        try:
            proba      = self.model.predict_proba(X)
            confidence = float(proba[0][1])
        except Exception as e:
            logger.error(f"UBB: inference error on {symbol}: {e}")
            return None

        # ── Log score vs threshold ─────────────────────────────────────
        if confidence >= threshold:
            logger.info(
                f"{base}  | score={confidence:.4f}  threshold={threshold:.2f}  ✔ SIGNAL"
            )
        else:
            logger.debug(
                f"{base}  | score={confidence:.4f}  threshold={threshold:.2f}  ✖ below"
            )
            return None

        entry_price = float(row.get('c_close', row.get('close', 0)))

        key_features = {
            'a_bb_event_type':   float(a_bb_event),
            'a_bb_position':     a_bb_pos,
            'a_rsi_value':       a_rsi,
            'a_upper_wick_pct':  float(row.get('a_upper_wick_pct', 0)),
            'b_candle_body_pct': b_body_pct,
            'c_bb_position':     float(row.get('c_bb_position', 0)),
            'model_score':       confidence,
        }

        logger.info(
            f"UBB SHORT SIGNAL: {symbol}  "
            f"entry={entry_price:.5f}  "
            f"score={confidence:.4f}  "
            f"a_bb_event={a_bb_event}  "
            f"a_rsi={a_rsi:.1f}"
        )

        return self.create_signal(
            symbol=symbol,
            direction="SHORT",
            confidence=confidence,
            entry_price=entry_price,
            features=key_features,
        )

    def _prepare_features(self, row: pd.Series) -> pd.DataFrame:
        """
        Build a single-row DataFrame in the exact column order the
        pipeline was trained on.

        The sklearn Pipeline uses string-based column selection internally
        so it requires a DataFrame — a plain numpy array will raise:
        'Specifying the columns using strings is only supported for dataframes'
        """
        features = {}
        for feat in self.get_required_features():
            value = row.get(feat, 0)
            if pd.isna(value) or np.isinf(float(value) if value is not None else 0):
                value = 0
            features[feat] = float(value)

        return pd.DataFrame([features], columns=self.get_required_features())

    def get_metadata(self) -> Dict:
        base = super().get_metadata()
        base.update({
            'strategy':         'Upper BB Rejection',
            'direction':        'SHORT',
            'candle_structure': 'A/B/C triplet',
            'n_features':       len(self.get_required_features()),
            'model_threshold':  self._model_threshold,
            'test_auc':         0.8217,
            'test_precision':   '91.53%',
        })
        return base
