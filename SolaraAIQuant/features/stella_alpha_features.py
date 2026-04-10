"""
Solara AI Quant - Stella Alpha Feature Engineer

Feature engineering class for the Stella Alpha Long model.
Computes the exact 25 features the model was trained on.

Input:  merged DataFrame (H4 base + d1_ columns from D1 merge)
Output: DataFrame with all 25 Stella Alpha features computed
"""

import pandas as pd
import numpy as np
from typing import List
import logging

from .base_feature_engineer import BaseFeatureEngineer

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
RSI_PERIOD   = 14
BB_PERIOD    = 20
BB_STD       = 2.0
ATR_PERIOD   = 14
ADX_PERIOD   = 14


def _col(df: pd.DataFrame, name: str, default=0) -> pd.Series:
    """Safe column getter — always returns a properly-indexed Series."""
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index, dtype=float)


class StellaAlphaFeatureEngineer(BaseFeatureEngineer):
    """
    Computes features for Stella Alpha Long predictor.

    Stella Alpha requires H4 base data + D1 merged data.
    It produces 25 features covering RSI, BB, trend, EMAs,
    ATR, volume, session, D1 cross-TF, and MTF alignment.
    """

    def get_required_input_columns(self) -> List[str]:
        """Columns that must exist before compute() runs."""
        return [
            # H4 base (always present)
            'timestamp', 'close', 'open', 'high', 'low', 'volume',
            # D1 merged (from merge_timeframes: [D1])
            'd1_close',
        ]

    def get_output_features(self) -> List[str]:
        """The 25 features Stella Alpha was trained on."""
        return [
            # RSI
            'rsi_value', 'rsi_slope_3', 'rsi_slope_5', 'rsi_percentile',
            # Bollinger Bands
            'bb_position', 'bb_width_pct', 'bb_touch_strength',
            # Trend
            'trend_strength', 'trend_direction', 'ema_8', 'ema_21',
            # Volatility
            'atr_pct', 'atr_percentile',
            # Volume
            'volume_ratio',
            # Session
            'hour', 'is_london_session', 'is_ny_session',
            # D1 cross-TF
            'd1_rsi_value', 'd1_bb_position',
            'd1_trend_strength', 'd1_trend_direction',
            # MTF alignment
            'mtf_rsi_aligned', 'mtf_trend_aligned', 'mtf_confluence_score',
        ]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all 25 Stella Alpha features.

        Args:
            df: Merged DataFrame with H4 base + d1_ columns

        Returns:
            DataFrame with all 25 output features added
        """
        df = df.copy()

        df = self._compute_rsi(df)
        df = self._compute_bollinger_bands(df)
        df = self._compute_atr_volatility(df)
        df = self._compute_trend(df)
        df = self._compute_volume(df)
        df = self._compute_session(df)
        df = self._compute_d1_features(df)
        df = self._compute_cross_tf(df)

        # Clean up any remaining NaN/inf
        df = df.replace([np.inf, -np.inf], np.nan).fillna(0)

        return df

    # ── Stage computations ─────────────────────────────────────────────────

    def _compute_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        delta    = df['close'].diff()
        gain     = delta.where(delta > 0, 0)
        loss     = (-delta).where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, np.inf)
        df['rsi_value']     = 100 - (100 / (1 + rs))
        df['rsi_slope_3']   = df['rsi_value'].diff(3) / 3
        df['rsi_slope_5']   = df['rsi_value'].diff(5) / 5
        df['rsi_overbought'] = (df['rsi_value'] > 70).astype(int)
        df['rsi_percentile'] = df['rsi_value'].rolling(50).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        return df

    def _compute_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        sma   = df['close'].rolling(BB_PERIOD).mean()
        std   = df['close'].rolling(BB_PERIOD).std()
        upper = sma + std * BB_STD
        lower = sma - std * BB_STD

        df['middle_band']      = sma
        df['upper_band']       = upper
        df['lower_band']       = lower
        df['bb_position']      = np.where(
            (upper - lower) > 0, (df['close'] - lower) / (upper - lower), 0.5
        )
        df['bb_width_pct']     = np.where(sma > 0, (upper - lower) / sma, 0)
        df['bb_touch_strength'] = np.where(upper > 0, df['high'] / upper, 0)
        return df

    def _compute_atr_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        high_low    = df['high'] - df['low']
        high_close  = np.abs(df['high'] - df['close'].shift(1))
        low_close   = np.abs(df['low'] - df['close'].shift(1))
        tr          = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr         = tr.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean()

        df['atr']      = atr
        df['atr_pct']  = atr / df['close']
        df['atr_percentile'] = df['atr_pct'].rolling(100).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        return df

    def _compute_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        ema_8  = df['close'].ewm(span=8,  adjust=False).mean()
        ema_21 = df['close'].ewm(span=21, adjust=False).mean()
        ema_50 = df['close'].ewm(span=50, adjust=False).mean()

        df['ema_8']  = ema_8
        df['ema_21'] = ema_21
        df['ema_50'] = ema_50

        df['trend_strength'] = (
            (df['close'] > ema_8).astype(int) +
            (df['close'] > ema_21).astype(int) +
            (df['close'] > ema_50).astype(int) +
            (ema_8 > ema_21).astype(int) +
            (ema_21 > ema_50).astype(int)
        ) / 5.0

        df['trend_direction'] = np.where(
            df['close'] > ema_21,
            np.minimum((df['close'] - ema_21) / (df['close'] * 0.01), 1),
            np.maximum((df['close'] - ema_21) / (df['close'] * 0.01), -1)
        )
        return df

    def _compute_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'volume' in df.columns:
            vol_ma = df['volume'].rolling(20).mean()
            df['volume_ratio'] = np.where(vol_ma > 0, df['volume'] / vol_ma, 1)
        else:
            df['volume_ratio'] = 1.0
        return df

    def _compute_session(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'timestamp' not in df.columns:
            df['hour'] = 0
            df['is_london_session'] = 0
            df['is_ny_session'] = 0
            return df

        ts = pd.to_datetime(df['timestamp'])
        df['hour']              = ts.dt.hour
        df['is_london_session'] = ((df['hour'] >= 8) & (df['hour'] < 16)).astype(int)
        df['is_ny_session']     = ((df['hour'] >= 13) & (df['hour'] < 21)).astype(int)
        return df

    def _compute_d1_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute derived indicators on the D1 merged columns."""
        if 'd1_close' not in df.columns:
            for col in ['d1_rsi_value', 'd1_bb_position',
                        'd1_trend_strength', 'd1_trend_direction']:
                df[col] = 0
            return df

        # D1 RSI
        d1_delta    = df['d1_close'].diff()
        d1_gain     = d1_delta.where(d1_delta > 0, 0)
        d1_loss     = (-d1_delta).where(d1_delta < 0, 0)
        d1_avg_gain = d1_gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
        d1_avg_loss = d1_loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
        d1_rs       = d1_avg_gain / d1_avg_loss.replace(0, np.inf)
        df['d1_rsi_value'] = 100 - (100 / (1 + d1_rs))

        # D1 Bollinger Band position
        d1_sma   = df['d1_close'].rolling(BB_PERIOD).mean()
        d1_std   = df['d1_close'].rolling(BB_PERIOD).std()
        d1_upper = d1_sma + d1_std * BB_STD
        d1_lower = d1_sma - d1_std * BB_STD
        df['d1_bb_position'] = np.where(
            (d1_upper - d1_lower) > 0,
            (df['d1_close'] - d1_lower) / (d1_upper - d1_lower),
            0.5
        )

        # D1 trend
        d1_ema_21 = df['d1_close'].ewm(span=21, adjust=False).mean()
        df['d1_trend_strength'] = np.where(df['d1_close'] > d1_ema_21, 1.0, -1.0)
        df['d1_trend_direction'] = np.where(
            df['d1_close'] > d1_ema_21,
            np.minimum((df['d1_close'] - d1_ema_21) / (df['d1_close'] * 0.01), 1),
            np.maximum((df['d1_close'] - d1_ema_21) / (df['d1_close'] * 0.01), -1)
        )
        return df

    def _compute_cross_tf(self, df: pd.DataFrame) -> pd.DataFrame:
        """MTF alignment scores combining H4 and D1 signals."""
        h4_rsi_ob = (_col(df, 'rsi_overbought', 0)).astype(int)
        d1_rsi_ob = (_col(df, 'd1_rsi_value', 50) > 70).astype(int)
        df['mtf_rsi_aligned'] = ((h4_rsi_ob == 1) & (d1_rsi_ob == 1)).astype(int)

        h4_trend = np.sign(_col(df, 'trend_direction', 0))
        d1_trend = np.sign(_col(df, 'd1_trend_direction', 0))
        df['mtf_trend_aligned'] = (h4_trend == d1_trend).astype(int)

        h4_bb_high = (_col(df, 'bb_position', 0.5) > 0.8).astype(int)
        d1_bb_high = (_col(df, 'd1_bb_position', 0.5) > 0.8).astype(int)
        df['mtf_bb_aligned'] = ((h4_bb_high == 1) & (d1_bb_high == 1)).astype(int)

        df['mtf_confluence_score'] = (
            df['mtf_rsi_aligned']   * 0.33 +
            df['mtf_bb_aligned']    * 0.33 +
            df['mtf_trend_aligned'] * 0.34
        )
        return df
