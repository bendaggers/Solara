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


class FeatureEngineer:
    """
    Computes features for model predictions.
    
    Features are computed in stages to allow dependencies:
    1. Base features (from raw OHLCV)
    2. Indicator features (RSI, BB, ATR)
    3. Derived features (slopes, percentiles)
    4. Cross-timeframe features (H4 vs D1)
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
        
        # If extends another version, include parent features
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
        
        # Stage 7: Derived features (slopes, percentiles)
        df = self._compute_derived_features(df)
        
        # Stage 8: Cross-timeframe features (if D1 data available)
        if include_d1 and 'd1_close' in df.columns:
            df = self._compute_d1_features(df)
            df = self._compute_cross_tf_features(df)
        
        logger.info(f"  Computed {len(df.columns)} columns")
        
        return df
    
    def _compute_base_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute base price features."""
        # Candle body
        df['candle_body'] = df['close'] - df['open']
        df['candle_range'] = df['high'] - df['low']
        df['candle_body_pct'] = np.where(
            df['candle_range'] > 0,
            np.abs(df['candle_body']) / df['candle_range'],
            0
        )
        
        # Rejection (upper/lower wick)
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['candle_rejection'] = np.where(
            df['candle_range'] > 0,
            df['upper_wick'] / df['candle_range'],
            0
        )
        
        # Previous candle features
        df['prev_candle_body_pct'] = df['candle_body_pct'].shift(1)
        
        # Price momentum
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_3'] = df['close'].pct_change(3)
        df['price_momentum'] = df['close'].pct_change(5)
        
        # Gap
        df['gap_from_prev_close'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        return df
    
    def _compute_rsi(self, df: pd.DataFrame, column: str = 'close', prefix: str = '') -> pd.DataFrame:
        """Compute RSI and related features."""
        delta = df[column].diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        # Wilder's smoothing (EMA)
        avg_gain = gain.ewm(alpha=1/self._rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self._rsi_period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        
        col_name = f'{prefix}rsi_value' if prefix else 'rsi_value'
        df[col_name] = rsi
        
        # RSI derivatives (only for H4, not D1)
        if not prefix:
            df['rsi_slope_3'] = df['rsi_value'].diff(3) / 3
            df['rsi_slope_5'] = df['rsi_value'].diff(5) / 5
            
            # RSI levels
            df['rsi_overbought'] = (df['rsi_value'] > 70).astype(int)
            df['rsi_extreme'] = (df['rsi_value'] > 80).astype(int)
            df['rsi_oversold'] = (df['rsi_value'] < 30).astype(int)
            
            # RSI percentile (rolling)
            df['rsi_percentile'] = df['rsi_value'].rolling(50).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
            )
        
        return df
    
    def _compute_bollinger_bands(self, df: pd.DataFrame, column: str = 'close', prefix: str = '') -> pd.DataFrame:
        """Compute Bollinger Bands and related features."""
        sma = df[column].rolling(self._bb_period).mean()
        std = df[column].rolling(self._bb_period).std()
        
        upper = sma + (std * self._bb_std)
        lower = sma - (std * self._bb_std)
        
        # Core BB columns
        df[f'{prefix}middle_band'] = sma
        df[f'{prefix}upper_band'] = upper
        df[f'{prefix}lower_band'] = lower
        
        # BB position (0 = at lower, 1 = at upper)
        df[f'{prefix}bb_position'] = np.where(
            (upper - lower) > 0,
            (df[column] - lower) / (upper - lower),
            0.5
        )
        
        # BB width percentage
        df[f'{prefix}bb_width_pct'] = np.where(
            sma > 0,
            (upper - lower) / sma,
            0
        )
        
        # BB touch strength (only for H4)
        if not prefix:
            df['bb_touch_strength'] = np.where(
                upper > 0,
                df['high'] / upper,
                0
            )
            
            # Distance from bands
            df['dist_from_upper'] = (upper - df['close']) / df['close']
            df['dist_from_lower'] = (df['close'] - lower) / df['close']
            
            # BB squeeze (low volatility)
            bb_width_pct_20 = df['bb_width_pct'].rolling(100).quantile(0.2)
            df['bb_squeeze'] = (df['bb_width_pct'] < bb_width_pct_20).astype(int)
            
            # BB expansion
            bb_width_pct_80 = df['bb_width_pct'].rolling(100).quantile(0.8)
            df['bb_expansion'] = (df['bb_width_pct'] > bb_width_pct_80).astype(int)
        
        return df
    
    def _compute_volatility(self, df: pd.DataFrame, prefix: str = '') -> pd.DataFrame:
        """Compute ATR and volatility features."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/self._atr_period, adjust=False).mean()
        
        df[f'{prefix}atr'] = atr
        df[f'{prefix}atr_pct'] = atr / df['close']
        
        if not prefix:
            # ATR percentile
            df['atr_percentile'] = df['atr_pct'].rolling(100).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
            )
            
            # Volatility regime
            df['volatility_regime'] = pd.cut(
                df['atr_percentile'],
                bins=[0, 0.33, 0.67, 1.0],
                labels=['low', 'medium', 'high']
            )
            
            # Volume ratio
            if 'volume' in df.columns:
                vol_ma = df['volume'].rolling(20).mean()
                df['volume_ratio'] = np.where(vol_ma > 0, df['volume'] / vol_ma, 1)
                df['prev_volume_ratio'] = df['volume_ratio'].shift(1)
        
        return df
    
    def _compute_trend(self, df: pd.DataFrame, prefix: str = '') -> pd.DataFrame:
        """Compute trend indicators."""
        # EMAs
        ema_8 = df['close'].ewm(span=8, adjust=False).mean()
        ema_21 = df['close'].ewm(span=21, adjust=False).mean()
        ema_50 = df['close'].ewm(span=50, adjust=False).mean()
        
        # Trend strength (price position relative to EMAs)
        df[f'{prefix}trend_strength'] = (
            (df['close'] > ema_8).astype(int) +
            (df['close'] > ema_21).astype(int) +
            (df['close'] > ema_50).astype(int) +
            (ema_8 > ema_21).astype(int) +
            (ema_21 > ema_50).astype(int)
        ) / 5.0
        
        # Trend direction (-1 to +1)
        df[f'{prefix}trend_direction'] = np.where(
            df['close'] > ema_21,
            np.minimum((df['close'] - ema_21) / (df['close'] * 0.01), 1),
            np.maximum((df['close'] - ema_21) / (df['close'] * 0.01), -1)
        )
        
        if not prefix:
            # ADX calculation
            df = self._compute_adx(df)
            
            # Is trending
            df['is_trending'] = (df['adx'] > 25).astype(int)
            df['is_ranging'] = (df['adx'] < 20).astype(int)
        
        return df
    
    def _compute_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute ADX indicator."""
        # True Range
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Directional Movement
        up_move = df['high'] - df['high'].shift(1)
        down_move = df['low'].shift(1) - df['low']
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smoothed values
        atr = pd.Series(tr).ewm(span=self._adx_period, adjust=False).mean()
        plus_di = 100 * pd.Series(plus_dm).ewm(span=self._adx_period, adjust=False).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).ewm(span=self._adx_period, adjust=False).mean() / atr
        
        # DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = pd.Series(dx).ewm(span=self._adx_period, adjust=False).mean()
        
        df['adx'] = adx
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        
        return df
    
    def _compute_session_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute session/time features."""
        if 'timestamp' not in df.columns:
            return df
        
        ts = pd.to_datetime(df['timestamp'])
        
        df['hour'] = ts.dt.hour
        df['day_of_week'] = ts.dt.dayofweek
        
        # Trading sessions (UTC)
        # Asian: 00:00 - 08:00
        # London: 08:00 - 16:00
        # NY: 13:00 - 21:00
        # Overlap: 13:00 - 16:00
        
        df['is_asian_session'] = ((df['hour'] >= 0) & (df['hour'] < 8)).astype(int)
        df['is_london_session'] = ((df['hour'] >= 8) & (df['hour'] < 16)).astype(int)
        df['is_ny_session'] = ((df['hour'] >= 13) & (df['hour'] < 21)).astype(int)
        df['is_overlap_session'] = ((df['hour'] >= 13) & (df['hour'] < 16)).astype(int)
        
        return df
    
    def _compute_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute derived features (slopes, percentiles, etc.)."""
        # BB touch tracking
        if 'bb_touch_strength' in df.columns:
            # Count touches in last N bars
            touched = (df['bb_touch_strength'] >= 0.98).astype(int)
            df['previous_touches'] = touched.rolling(20).sum()
            
            # Time since last touch
            touch_mask = touched == 1
            df['time_since_last_touch'] = touch_mask.groupby(
                (touch_mask != touch_mask.shift()).cumsum()
            ).cumcount()
            
            # Resistance distance
            if 'upper_band' in df.columns:
                recent_high = df['high'].rolling(20).max()
                df['resistance_distance_pct'] = (recent_high - df['close']) / df['close']
        
        return df
    
    def _compute_d1_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute features for D1 columns (already merged with d1_ prefix)."""
        # Only compute if we have D1 close
        if 'd1_close' not in df.columns:
            return df
        
        # D1 RSI (if not already computed)
        if 'd1_rsi_value' not in df.columns:
            df = self._compute_rsi(df, column='d1_close', prefix='d1_')
        
        # D1 BB position (if not already computed)
        if 'd1_bb_position' not in df.columns and 'd1_middle_band' not in df.columns:
            df = self._compute_bollinger_bands(df, column='d1_close', prefix='d1_')
        
        # D1 Trend
        if 'd1_trend_strength' not in df.columns:
            df = self._compute_trend_simple(df, column='d1_close', prefix='d1_')
        
        # D1 ATR
        if 'd1_atr_pct' not in df.columns and 'd1_high' in df.columns:
            # Simple ATR approximation using D1 range
            d1_range = df['d1_high'] - df['d1_low']
            df['d1_atr_pct'] = d1_range / df['d1_close']
        
        # D1 is trending
        df['d1_is_trending'] = (df.get('d1_adx', 30) > 25).astype(int) if 'd1_adx' in df.columns else 0
        
        return df
    
    def _compute_trend_simple(self, df: pd.DataFrame, column: str, prefix: str) -> pd.DataFrame:
        """Simplified trend calculation for D1 data."""
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
        """Compute cross-timeframe (H4 vs D1) alignment features."""
        # RSI alignment (both overbought)
        h4_rsi_ob = df.get('rsi_overbought', 0)
        d1_rsi_ob = (df.get('d1_rsi_value', 50) > 70).astype(int)
        df['mtf_rsi_aligned'] = ((h4_rsi_ob == 1) & (d1_rsi_ob == 1)).astype(int)
        
        # BB alignment (both near upper band)
        h4_bb_high = (df.get('bb_position', 0.5) > 0.8).astype(int)
        d1_bb_high = (df.get('d1_bb_position', 0.5) > 0.8).astype(int)
        df['mtf_bb_aligned'] = ((h4_bb_high == 1) & (d1_bb_high == 1)).astype(int)
        
        # Trend alignment (both same direction)
        h4_trend = np.sign(df.get('trend_direction', 0))
        d1_trend = np.sign(df.get('d1_trend_direction', 0))
        df['mtf_trend_aligned'] = (h4_trend == d1_trend).astype(int)
        
        # Confluence score (0 to 1)
        df['mtf_confluence_score'] = (
            df['mtf_rsi_aligned'] * 0.33 +
            df['mtf_bb_aligned'] * 0.33 +
            df['mtf_trend_aligned'] * 0.34
        )
        
        # D1 supports/opposes the trade direction
        # For SHORT: D1 should be bearish (trend_direction < 0)
        df['d1_supports_short'] = (df.get('d1_trend_direction', 0) < -0.3).astype(int)
        df['d1_opposes_short'] = (df.get('d1_trend_direction', 0) > 0.3).astype(int)
        
        # For LONG: D1 should be bullish
        df['d1_supports_long'] = (df.get('d1_trend_direction', 0) > 0.3).astype(int)
        df['d1_opposes_long'] = (df.get('d1_trend_direction', 0) < -0.3).astype(int)
        
        return df
    
    def get_latest_row_features(self, df: pd.DataFrame) -> pd.Series:
        """
        Get features for the latest (most recent) row.
        Used for live prediction.
        
        Returns:
            Series with feature values
        """
        if len(df) == 0:
            raise ValueError("DataFrame is empty")
        
        return df.iloc[-1]


# Global instance
feature_engineer = FeatureEngineer()
