"""
Solara AI Quant - Feature Engineering

Computes technical indicators and derived features from OHLCV data.
Supports multiple feature versions for different model requirements.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Set
from pathlib import Path
import yaml
import logging

from config import feature_config, PROJECT_ROOT

logger = logging.getLogger(__name__)


def _col(df: pd.DataFrame, name: str, default) -> pd.Series:
    """
    Safe column getter — always returns a Series.

    df.get(col, scalar) returns a scalar when the column is missing,
    which breaks .astype() and np.sign(). This helper always returns
    a properly-indexed Series regardless.
    """
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index, dtype=float)


class FeatureEngineer:
    """
    Computes features for model predictions.

    Features are computed in stages to allow dependencies:
    1. Base features (from raw OHLCV)
    2. RSI
    3. Bollinger Bands
    4. ATR and Volatility
    5. Trend indicators (EMAs, ADX)
    6. Session/Time features
    7. Derived features (slopes, percentiles)
    8. Cross-timeframe features (D1 or other merged TFs)
    """

    def __init__(self):
        self.feature_versions = self._load_feature_versions()
        self._rsi_period = 14
        self._bb_period = 20
        self._bb_std = 2.0
        self._atr_period = 14
        self._adx_period = 14

    def _load_feature_versions(self) -> Dict:
        """Load feature versions from YAML."""
        versions_path = PROJECT_ROOT / "features" / "feature_versions.yaml"
        if versions_path.exists():
            with open(versions_path, 'r') as f:
                return yaml.safe_load(f)
        return {'versions': {}}

    def get_version_features(self, version: str) -> Set[str]:
        """Get list of features for a specific version."""
        versions = self.feature_versions.get('versions', {})

        if version not in versions:
            logger.warning(f"Unknown feature version: {version}")
            return set()

        features = set(versions[version].get('features', []))

        extends = versions[version].get('extends')
        if extends and extends in versions:
            features.update(self.get_version_features(extends))

        return features

    def validate_features(
        self,
        df: pd.DataFrame,
        required_version: str
    ) -> tuple[bool, List[str]]:
        """
        Validate that DataFrame has all features for a version.

        Returns:
            (is_valid, list of missing features)
        """
        required = self.get_version_features(required_version)
        available = set(df.columns)
        missing = required - available
        return len(missing) == 0, list(missing)

    def compute_all_features(
        self,
        df: pd.DataFrame,
        include_d1: bool = True
    ) -> pd.DataFrame:
        """
        Compute all features on DataFrame.

        Args:
            df: DataFrame with OHLCV columns
            include_d1: If True, compute cross-TF features (requires d1_ columns)

        Returns:
            DataFrame with computed features
        """
        logger.info(f"Computing features for {len(df)} rows")
        df = df.copy()

        # Stage 1: Base features
        df = self._compute_base_features(df)

        # Stage 2: RSI
        df = self._compute_rsi(df)

        # Stage 3: Bollinger Bands
        df = self._compute_bollinger_bands(df)

        # Stage 4: ATR and Volatility
        df = self._compute_volatility(df)

        # Stage 5: Trend indicators
        df = self._compute_trend(df)

        # Stage 6: Session/Time features
        df = self._compute_session_features(df)

        # Stage 7: Derived features
        df = self._compute_derived_features(df)

        # Stage 8: Cross-timeframe features (only if secondary TF data was merged)
        if include_d1 and 'd1_close' in df.columns:
            df = self._compute_d1_features(df)
            df = self._compute_cross_tf_features(df)

        logger.info(f"  Computed {len(df.columns)} columns")
        return df

    # =========================================================================
    # Stage implementations
    # =========================================================================

    def _compute_base_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Stage 1: Base price features."""
        df['candle_body'] = df['close'] - df['open']
        df['candle_range'] = df['high'] - df['low']
        df['candle_body_pct'] = np.where(
            df['candle_range'] > 0,
            np.abs(df['candle_body']) / df['candle_range'],
            0
        )

        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['candle_rejection'] = np.where(
            df['candle_range'] > 0,
            df['upper_wick'] / df['candle_range'],
            0
        )

        df['prev_candle_body_pct'] = df['candle_body_pct'].shift(1)
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_3'] = df['close'].pct_change(3)
        df['price_momentum'] = df['close'].pct_change(5)
        df['gap_from_prev_close'] = (
            (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        )

        return df

    def _compute_rsi(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        prefix: str = ''
    ) -> pd.DataFrame:
        """Stage 2: RSI and related features."""
        delta = df[column].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        avg_gain = gain.ewm(alpha=1 / self._rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self._rsi_period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))

        col_name = f'{prefix}rsi_value' if prefix else 'rsi_value'
        df[col_name] = rsi

        # RSI derivatives — only for primary (non-prefixed) calculation
        if not prefix:
            df['rsi_slope_3'] = df['rsi_value'].diff(3) / 3
            df['rsi_slope_5'] = df['rsi_value'].diff(5) / 5
            df['rsi_overbought'] = (df['rsi_value'] > 70).astype(int)
            df['rsi_extreme'] = (df['rsi_value'] > 80).astype(int)
            df['rsi_oversold'] = (df['rsi_value'] < 30).astype(int)
            df['rsi_percentile'] = df['rsi_value'].rolling(50).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
            )

        return df

    def _compute_bollinger_bands(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        prefix: str = ''
    ) -> pd.DataFrame:
        """Stage 3: Bollinger Bands."""
        sma = df[column].rolling(self._bb_period).mean()
        std = df[column].rolling(self._bb_period).std()
        upper = sma + (std * self._bb_std)
        lower = sma - (std * self._bb_std)

        df[f'{prefix}middle_band'] = sma
        df[f'{prefix}upper_band'] = upper
        df[f'{prefix}lower_band'] = lower
        df[f'{prefix}bb_position'] = np.where(
            (upper - lower) > 0,
            (df[column] - lower) / (upper - lower),
            0.5
        )
        df[f'{prefix}bb_width_pct'] = np.where(sma > 0, (upper - lower) / sma, 0)

        if not prefix:
            df['bb_touch_strength'] = np.where(upper > 0, df['high'] / upper, 0)
            df['dist_from_upper'] = (upper - df['close']) / df['close']
            df['dist_from_lower'] = (df['close'] - lower) / df['close']

            bb_width_pct_20 = df['bb_width_pct'].rolling(100).quantile(0.2)
            bb_width_pct_80 = df['bb_width_pct'].rolling(100).quantile(0.8)
            df['bb_squeeze'] = (df['bb_width_pct'] < bb_width_pct_20).astype(int)
            df['bb_expansion'] = (df['bb_width_pct'] > bb_width_pct_80).astype(int)

        return df

    def _compute_volatility(self, df: pd.DataFrame, prefix: str = '') -> pd.DataFrame:
        """Stage 4: ATR and volatility."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / self._atr_period, adjust=False).mean()

        df[f'{prefix}atr'] = atr
        df[f'{prefix}atr_pct'] = atr / df['close']

        if not prefix:
            df['atr_percentile'] = df['atr_pct'].rolling(100).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
            )
            df['volatility_regime'] = pd.cut(
                df['atr_percentile'],
                bins=[0, 0.33, 0.67, 1.0],
                labels=['low', 'medium', 'high']
            )
            if 'volume' in df.columns:
                vol_ma = df['volume'].rolling(20).mean()
                df['volume_ratio'] = np.where(vol_ma > 0, df['volume'] / vol_ma, 1)
                df['prev_volume_ratio'] = df['volume_ratio'].shift(1)

        return df

    def _compute_trend(self, df: pd.DataFrame, prefix: str = '') -> pd.DataFrame:
        """Stage 5: Trend indicators — EMAs, trend strength, ADX."""
        ema_8 = df['close'].ewm(span=8, adjust=False).mean()
        ema_21 = df['close'].ewm(span=21, adjust=False).mean()
        ema_50 = df['close'].ewm(span=50, adjust=False).mean()

        # ── Save EMA columns so models can use them as features ──────────────
        if not prefix:
            df['ema_8'] = ema_8
            df['ema_21'] = ema_21
            df['ema_50'] = ema_50

        df[f'{prefix}trend_strength'] = (
            (df['close'] > ema_8).astype(int) +
            (df['close'] > ema_21).astype(int) +
            (df['close'] > ema_50).astype(int) +
            (ema_8 > ema_21).astype(int) +
            (ema_21 > ema_50).astype(int)
        ) / 5.0

        df[f'{prefix}trend_direction'] = np.where(
            df['close'] > ema_21,
            np.minimum((df['close'] - ema_21) / (df['close'] * 0.01), 1),
            np.maximum((df['close'] - ema_21) / (df['close'] * 0.01), -1)
        )

        if not prefix:
            df = self._compute_adx(df)
            df['is_trending'] = (df['adx'] > 25).astype(int)
            df['is_ranging'] = (df['adx'] < 20).astype(int)

        return df

    def _compute_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute ADX indicator."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        up_move = df['high'] - df['high'].shift(1)
        down_move = df['low'].shift(1) - df['low']
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        atr = pd.Series(tr).ewm(span=self._adx_period, adjust=False).mean()
        plus_di = (
            100 * pd.Series(plus_dm).ewm(span=self._adx_period, adjust=False).mean() / atr
        )
        minus_di = (
            100 * pd.Series(minus_dm).ewm(span=self._adx_period, adjust=False).mean() / atr
        )

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = pd.Series(dx).ewm(span=self._adx_period, adjust=False).mean()

        df['adx'] = adx
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di

        return df

    def _compute_session_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Stage 6: Session/time features."""
        if 'timestamp' not in df.columns:
            return df

        ts = pd.to_datetime(df['timestamp'])
        df['hour'] = ts.dt.hour
        df['day_of_week'] = ts.dt.dayofweek
        df['is_asian_session'] = ((df['hour'] >= 0) & (df['hour'] < 8)).astype(int)
        df['is_london_session'] = ((df['hour'] >= 8) & (df['hour'] < 16)).astype(int)
        df['is_ny_session'] = ((df['hour'] >= 13) & (df['hour'] < 21)).astype(int)
        df['is_overlap_session'] = ((df['hour'] >= 13) & (df['hour'] < 16)).astype(int)

        return df

    def _compute_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Stage 7: Derived features — BB touch tracking."""
        if 'bb_touch_strength' in df.columns:
            touched = (df['bb_touch_strength'] >= 0.98).astype(int)
            df['previous_touches'] = touched.rolling(20).sum()

            touch_mask = touched == 1
            df['time_since_last_touch'] = touch_mask.groupby(
                (touch_mask != touch_mask.shift()).cumsum()
            ).cumcount()

            if 'upper_band' in df.columns:
                recent_high = df['high'].rolling(20).max()
                df['resistance_distance_pct'] = (recent_high - df['close']) / df['close']

        return df

    def _compute_d1_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Stage 8a: Compute derived indicators on already-merged D1 columns."""
        if 'd1_close' not in df.columns:
            return df

        if 'd1_rsi_value' not in df.columns:
            df = self._compute_rsi(df, column='d1_close', prefix='d1_')

        if 'd1_bb_position' not in df.columns and 'd1_middle_band' not in df.columns:
            df = self._compute_bollinger_bands(df, column='d1_close', prefix='d1_')

        if 'd1_trend_strength' not in df.columns or 'd1_trend_direction' not in df.columns:
            df = self._compute_trend_simple(df, column='d1_close', prefix='d1_')

        if 'd1_atr_pct' not in df.columns and 'd1_high' in df.columns:
            d1_range = df['d1_high'] - df['d1_low']
            df['d1_atr_pct'] = d1_range / df['d1_close']

        if 'd1_adx' in df.columns:
            df['d1_is_trending'] = (df['d1_adx'] > 25).astype(int)
        else:
            df['d1_is_trending'] = 0

        return df

    def _compute_trend_simple(
        self,
        df: pd.DataFrame,
        column: str,
        prefix: str
    ) -> pd.DataFrame:
        """Simplified EMA-based trend for secondary TF columns."""
        ema_21 = df[column].ewm(span=21, adjust=False).mean()

        df[f'{prefix}trend_strength'] = np.where(
            df[column] > ema_21, 1, -1
        ).astype(float)

        df[f'{prefix}trend_direction'] = np.where(
            df[column] > ema_21,
            np.minimum((df[column] - ema_21) / (df[column] * 0.01), 1),
            np.maximum((df[column] - ema_21) / (df[column] * 0.01), -1)
        )

        return df

    def _compute_cross_tf_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Stage 8b: Cross-timeframe alignment features.

        Uses _col() helper throughout so every df.get() call returns
        a properly-indexed Series even when the column is absent.
        """
        # ── RSI alignment ────────────────────────────────────────────────────
        h4_rsi_ob = _col(df, 'rsi_overbought', 0)
        d1_rsi_ob = (_col(df, 'd1_rsi_value', 50) > 70).astype(int)
        df['mtf_rsi_aligned'] = ((h4_rsi_ob == 1) & (d1_rsi_ob == 1)).astype(int)

        # ── BB alignment ─────────────────────────────────────────────────────
        h4_bb_high = (_col(df, 'bb_position', 0.5) > 0.8).astype(int)
        d1_bb_high = (_col(df, 'd1_bb_position', 0.5) > 0.8).astype(int)
        df['mtf_bb_aligned'] = ((h4_bb_high == 1) & (d1_bb_high == 1)).astype(int)

        # ── Trend alignment ──────────────────────────────────────────────────
        h4_trend = np.sign(_col(df, 'trend_direction', 0))
        d1_trend = np.sign(_col(df, 'd1_trend_direction', 0))
        df['mtf_trend_aligned'] = (h4_trend == d1_trend).astype(int)

        # ── Confluence score ─────────────────────────────────────────────────
        df['mtf_confluence_score'] = (
            df['mtf_rsi_aligned'] * 0.33 +
            df['mtf_bb_aligned'] * 0.33 +
            df['mtf_trend_aligned'] * 0.34
        )

        # ── D1 directional support/opposition ────────────────────────────────
        d1_trend_dir = _col(df, 'd1_trend_direction', 0)
        df['d1_supports_short'] = (d1_trend_dir < -0.3).astype(int)
        df['d1_opposes_short'] = (d1_trend_dir > 0.3).astype(int)
        df['d1_supports_long'] = (d1_trend_dir > 0.3).astype(int)
        df['d1_opposes_long'] = (d1_trend_dir < -0.3).astype(int)

        return df

    def get_latest_row_features(self, df: pd.DataFrame) -> pd.Series:
        """Get the most recent row's features for live prediction."""
        if len(df) == 0:
            raise ValueError("DataFrame is empty")
        return df.iloc[-1]


# Global instance
feature_engineer = FeatureEngineer()
