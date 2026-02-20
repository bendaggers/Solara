"""
features/feature_engineer.py — Feature Engineering
=====================================================
Transforms raw validated OHLCV DataFrame into model-ready features.
Runs ONCE per timeframe cycle. Result is shared read-only to all models.

Computation order (must not be changed — stages depend on each other):
  Stage 1: Raw price features  (body_size, candle_body_pct)
  Stage 2: Return features     (ret, ret_lag1/2/3)
  Stage 3: Momentum            (price_momentum)
  Stage 4: RSI                 (rsi_value)
  Stage 5: RSI slope features  (rsi_slope, lags, RSI_slope_3)
  Stage 6: Bollinger Bands     (bb_upper, bb_lower, dist_bb_upper/lower)
  Stage 7: BB lag features     (dist_bb_upper_lag1/2/3)
  Stage 8: Final trim          (keep only latest bar per symbol)
"""
import pandas as pd
import numpy as np
import structlog
import config

log = structlog.get_logger(__name__)


class FeatureEngineer:
    """Computes all SAQ features from raw OHLCV data."""

    def compute(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Run all 8 computation stages on the full multi-bar DataFrame.

        Args:
            df:         Validated, sorted DataFrame (multiple bars per symbol).
            timeframe:  Used for logging only.

        Returns:
            DataFrame with 1 row per symbol containing all computed features.
        """
        result_frames = []

        for symbol, group in df.groupby("symbol"):
            g = group.sort_values("timestamp").copy().reset_index(drop=True)
            g = self._compute_all_stages(g)
            # Stage 8: keep only the latest bar
            result_frames.append(g.iloc[[-1]])

        if not result_frames:
            return pd.DataFrame()

        featured = pd.concat(result_frames, ignore_index=True)
        log.info(
            "features_computed",
            timeframe=timeframe,
            symbols=len(featured),
            feature_count=len(featured.columns),
        )
        return featured

    def _compute_all_stages(self, g: pd.DataFrame) -> pd.DataFrame:
        """Apply all 8 feature stages to a single-symbol sorted DataFrame."""

        # ── Stage 1: Raw price features ──────────────────────────────────────
        g["body_size"] = (g["close"] - g["open"]).abs()
        candle_range = g["high"] - g["low"]
        g["candle_body_pct"] = g["body_size"] / candle_range.replace(0, np.nan)
        g["candle_body_pct"] = g["candle_body_pct"].fillna(0.0)

        # ── Stage 2: Return features ──────────────────────────────────────────
        g["ret"]      = g["close"].pct_change(1)
        g["ret_lag1"] = g["ret"].shift(1)
        g["ret_lag2"] = g["ret"].shift(2)
        g["ret_lag3"] = g["ret"].shift(3)

        # ── Stage 3: Momentum ─────────────────────────────────────────────────
        g["price_momentum"] = g["close"].pct_change(3)

        # ── Stage 4: RSI (Wilder's smoothing, period=14) ──────────────────────
        delta    = g["close"].diff(1)
        gain     = delta.clip(lower=0)
        loss     = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / config.RSI_PERIOD, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        g["rsi_value"] = 100 - (100 / (1 + rs))
        g["rsi_value"] = g["rsi_value"].fillna(50.0)  # neutral on insufficient data

        # ── Stage 5: RSI slope features ───────────────────────────────────────
        g["rsi_slope"]      = g["rsi_value"].diff(1)
        g["rsi_slope_lag1"] = g["rsi_slope"].shift(1)
        g["rsi_slope_lag2"] = g["rsi_slope"].shift(2)
        g["rsi_slope_lag3"] = g["rsi_slope"].shift(3)
        g["RSI_slope_3"]    = g["rsi_value"].diff(3)

        # ── Stage 6: Bollinger Bands (period=20, std_dev=2) ───────────────────
        bb_mid = g["close"].rolling(config.BB_PERIOD).mean()
        bb_std = g["close"].rolling(config.BB_PERIOD).std(ddof=0)
        bb_upper = bb_mid + (config.BB_STD_DEV * bb_std)
        bb_lower = bb_mid - (config.BB_STD_DEV * bb_std)
        g["dist_bb_upper"] = g["close"] - bb_upper
        g["dist_bb_lower"] = g["close"] - bb_lower

        # ── Stage 7: BB lag features ──────────────────────────────────────────
        g["dist_bb_upper_lag1"] = g["dist_bb_upper"].shift(1)
        g["dist_bb_upper_lag2"] = g["dist_bb_upper"].shift(2)
        g["dist_bb_upper_lag3"] = g["dist_bb_upper"].shift(3)

        return g
