"""
predictors/bb_reversal_long.py — BB Reversal Long Predictor
=============================================================
Bollinger Band reversal strategy — LONG entries only.

BUG FIX NOTE:
  The legacy Solara system had BOTH long and short predictors pointing
  to the same class (BBReversalShortPredictor). This class is the
  CORRECTED long-specific implementation.
"""
import joblib
import pandas as pd
import structlog
from predictors.base_predictor import BasePredictor
from signals.signal_models import RawSignal

log = structlog.get_logger(__name__)

FEATURE_LIST_V3 = [
    "ret", "ret_lag1", "ret_lag2", "ret_lag3",
    "body_size", "candle_body_pct",
    "rsi_value", "rsi_slope", "rsi_slope_lag1", "rsi_slope_lag2",
    "rsi_slope_lag3", "RSI_slope_3",
    "dist_bb_upper", "dist_bb_lower",
    "dist_bb_upper_lag1", "dist_bb_upper_lag2", "dist_bb_upper_lag3",
    "price_momentum",
]


class BBReversalLongPredictor(BasePredictor):
    """BB Reversal LONG strategy — sklearn pipeline loaded from .pkl."""

    def __init__(self, entry) -> None:
        super().__init__(entry)
        self._model = joblib.load(entry.model_path)
        log.info("predictor_loaded", model=entry.name, path=str(entry.model_path))

    def get_feature_list(self) -> list[str]:
        return FEATURE_LIST_V3

    def predict(self, featured_df: pd.DataFrame) -> list[RawSignal]:
        signals = []
        features = self.get_feature_list()
        df = featured_df[features].dropna()

        if df.empty:
            return signals

        proba = self._model.predict_proba(df)
        # Class 1 = LONG signal probability
        long_proba = proba[:, 1]

        for i, (idx, row) in enumerate(featured_df.iterrows()):
            confidence = float(long_proba[i]) if i < len(long_proba) else 0.0
            if confidence >= self._entry.min_confidence:
                # Apply symbol whitelist if configured
                symbol = str(row["symbol"])
                if self._entry.symbols and symbol not in self._entry.symbols:
                    continue

                signals.append(RawSignal(
                    symbol=symbol,
                    direction="LONG",
                    confidence=confidence,
                    model_name=self._entry.name,
                    model_type="LONG",
                    timeframe=self._entry.timeframe,
                    magic=self._entry.magic,
                    weight=self._entry.weight,
                    price=float(row.get("price", row["close"])),
                    comment=f"{self._entry.comment} {confidence:.2f}",
                ))

        return signals
