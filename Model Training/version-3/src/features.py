"""
Feature engineering and selection - COMPREHENSIVE SHORT STRATEGY.

VERSION: 3.0 - SHORT STRATEGY (COMPREHENSIVE)

PIPELINE:
=========
1. DataExporterEA_SHORT.mq5 calculates BASE features from raw OHLCV
2. This module calculates DERIVED + STATISTICAL + MOMENTUM features

BASE FEATURES (from EA CSV - DO NOT RECALCULATE):
─────────────────────────────────────────────────
• OHLCV (open, high, low, close, volume)
• Bollinger Bands (lower_band, middle_band, upper_band)
• bb_touch_strength (high/upper_band)
• bb_position, bb_width_pct
• rsi_value, rsi_divergence (bearish)
• volume_ratio, candle_rejection (upper wick)
• candle_body_pct, atr_pct, trend_strength
• prev_candle_body_pct, prev_volume_ratio
• gap_from_prev_close, price_momentum (HIGH-based)
• prev_was_rally, previous_touches (UPPER band)
• time_since_last_touch (UPPER band)
• resistance_distance_pct, session

DERIVED FEATURES (calculated here):
───────────────────────────────────
• Lag features (RSI, BB position, price, volume)
• Slope features (rate of change)
• Binary features (overbought flags, bearish patterns)
• Quality indicators (exhaustion signals)

NEW STATISTICAL FEATURES:
─────────────────────────
• Rolling statistics (std, skewness, kurtosis)
• Z-scores (price, RSI, volume)
• Percentile ranks
• Volatility measures

NEW MOMENTUM FEATURES:
──────────────────────
• Rate of Change (ROC)
• Momentum oscillators
• Acceleration/deceleration
• Trend exhaustion indicators

NEW PATTERN FEATURES:
─────────────────────
• Consecutive candle patterns
• Reversal pattern detection
• Volume profile analysis
• BB squeeze detection
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass
import warnings
import logging
from scipy import stats as scipy_stats

from sklearn.feature_selection import RFE, RFECV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.exceptions import ConvergenceWarning


# =============================================================================
# PART 1: FEATURE ENGINEERING (COMPREHENSIVE)
# =============================================================================

class FeatureEngineering:
    """
    Comprehensive feature engineering for SHORT strategy.
    
    VERSION 3.0
    
    Calculates DERIVED features from EA CSV output including:
    - Lag features
    - Slope features
    - Statistical features (z-scores, percentiles, rolling stats)
    - Momentum features (ROC, acceleration)
    - Pattern features (consecutive candles, reversals)
    - Quality indicators
    - Exhaustion score
    """
    
    # Rolling window sizes
    WINDOW_SHORT = 5
    WINDOW_MEDIUM = 10
    WINDOW_LONG = 20
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        if verbose:
            logging.basicConfig(level=logging.INFO)
    
    def calculate_features(
        self, 
        df: pd.DataFrame,
        drop_na: bool = True,
        min_periods: int = 20  # Increased for rolling statistics
    ) -> pd.DataFrame:
        """
        Calculate all DERIVED features from EA CSV output.
        
        Args:
            df: DataFrame from DataExporterEA_SHORT.mq5 CSV output
            drop_na: If True, drop rows with NaN. If False, forward fill.
            min_periods: Number of initial rows to drop (default 20 for rolling stats)
                
        Returns:
            DataFrame with original data and all calculated features
        """
        self._validate_input(df)
        
        if self.verbose:
            logging.info(f"Input shape: {df.shape}")
            logging.info("Calculating comprehensive features for SHORT strategy")
        
        df_features = df.copy()
        df_features.columns = df_features.columns.str.lower()
        
        # Fix BB position if needed
        df_features = self._fix_bb_position_if_needed(df_features)
        
        # === DERIVED FEATURES ===
        df_features = self._add_binary_features(df_features)
        df_features = self._add_price_change_features(df_features)
        df_features = self._add_lag_features(df_features)
        df_features = self._add_slope_features(df_features)
        
        # === NEW: STATISTICAL FEATURES ===
        df_features = self._add_zscore_features(df_features)
        df_features = self._add_rolling_statistics(df_features)
        df_features = self._add_percentile_features(df_features)
        
        # === NEW: MOMENTUM FEATURES ===
        df_features = self._add_roc_features(df_features)
        df_features = self._add_acceleration_features(df_features)
        df_features = self._add_momentum_divergence(df_features)
        
        # === NEW: PATTERN FEATURES ===
        df_features = self._add_consecutive_patterns(df_features)
        df_features = self._add_reversal_patterns(df_features)
        df_features = self._add_bb_patterns(df_features)
        df_features = self._add_volume_patterns(df_features)
        
        # === QUALITY & EXHAUSTION ===
        df_features = self._add_quality_features(df_features)
        df_features = self._add_exhaustion_score(df_features)
        
        # Handle NaN values
        if drop_na:
            initial_rows = len(df_features)
            df_features = df_features.iloc[min_periods:].reset_index(drop=True)
            if self.verbose:
                logging.info(f"Dropped first {min_periods} rows ({initial_rows} -> {len(df_features)})")
        else:
            df_features = df_features.ffill().bfill()
        
        if self.verbose:
            logging.info(f"Final shape: {df_features.shape}")
            logging.info(f"Total features: {len(df_features.columns)}")
            nan_count = df_features.isnull().sum().sum()
            if nan_count > 0:
                logging.warning(f"Remaining NaN values: {nan_count}")

        df_features = df_features.copy()

        return df_features
    
    # =========================================================================
    # INPUT VALIDATION
    # =========================================================================
    
    def _validate_input(self, df: pd.DataFrame) -> None:
        """Validate EA CSV has required columns."""
        df_cols_lower = [c.lower() for c in df.columns]
        
        required_from_ea = [
            'open', 'high', 'low', 'close', 'volume',
            'lower_band', 'middle_band', 'upper_band',
            'bb_position', 'bb_width_pct',
            'rsi_value', 'volume_ratio', 'atr_pct', 'trend_strength',
            'time_since_last_touch'
        ]
        
        # Optional columns that shouldn't break the pipeline if missing
        optional_columns = ['resistance_distance_pct', 'bb_touch_strength', 
                           'prev_candle_body_pct', 'prev_volume_ratio',
                           'gap_from_prev_close', 'price_momentum',
                           'prev_was_rally', 'previous_touches', 'session']
        
        missing = [col for col in required_from_ea if col not in df_cols_lower]
        if missing:
            raise ValueError(
                f"Missing columns from EA CSV: {missing}\n"
                f"Ensure you're using DataExporterEA_SHORT.mq5 output."
            )
        
        missing_optional = [col for col in optional_columns if col not in df_cols_lower]
        if missing_optional and self.verbose:
            logging.warning(f"Optional columns missing: {missing_optional}")
        
        if len(df) < 50:
            raise ValueError(f"Insufficient data: need at least 50 rows, got {len(df)}")
    
    def _fix_bb_position_if_needed(self, df: pd.DataFrame) -> pd.DataFrame:
        """Verify BB position is in correct range (0-1)."""
        if df['bb_position'].max() > 1.5 or df['bb_position'].min() < -0.5:
            if self.verbose:
                logging.warning("Recalculating bb_position...")
            df['bb_position'] = (
                (df['close'] - df['lower_band']) / 
                (df['upper_band'] - df['lower_band'])
            ).clip(0, 1)
        return df
    
    # =========================================================================
    # BINARY FEATURES - FIXED WITH fillna(0)
    # =========================================================================
    
    def _add_binary_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add binary indicator features for SHORT strategy."""
        
        # Touched upper BB (derived from bb_touch_strength if available)
        if 'bb_touch_strength' in df.columns:
            df['touched_upper_bb'] = (df['bb_touch_strength'] >= 1.0).fillna(0).astype(int)
        else:
            df['touched_upper_bb'] = (df['high'] >= df['upper_band']).fillna(0).astype(int)
        
        # RSI overbought conditions
        df['rsi_overbought'] = (df['rsi_value'] > 70).fillna(0).astype(int)
        df['rsi_extreme_overbought'] = (df['rsi_value'] > 80).fillna(0).astype(int)
        df['rsi_very_extreme'] = (df['rsi_value'] > 85).fillna(0).astype(int)
        
        # Bearish candle
        df['bearish_candle'] = (df['close'] < df['open']).fillna(0).astype(int)
        
        # Strong bearish (large body)
        body_pct = (df['close'] - df['open']).abs() / df['close'].replace(0, np.nan)
        df['strong_bearish'] = ((df['close'] < df['open']) & (body_pct > 0.005)).fillna(0).astype(int)
        
        # High BB position
        df['bb_very_high'] = (df['bb_position'] > 0.95).fillna(0).astype(int)
        df['bb_above_upper'] = (df['close'] > df['upper_band']).fillna(0).astype(int)
        
        # Volume conditions
        df['high_volume'] = (df['volume_ratio'] > 1.5).fillna(0).astype(int)
        df['extreme_volume'] = (df['volume_ratio'] > 2.0).fillna(0).astype(int)
        
        # Trend conditions (for SHORT, positive trend = exhaustion setup)
        df['strong_uptrend'] = (df['trend_strength'] > 1.0).fillna(0).astype(int)
        
        return df
    
    # =========================================================================
    # PRICE CHANGE FEATURES
    # =========================================================================
    
    def _add_price_change_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price change features."""
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_3'] = df['close'].pct_change(3)
        df['price_change_5'] = df['close'].pct_change(5)
        df['price_change_10'] = df['close'].pct_change(10)
        
        # High-to-high change (relevant for SHORT)
        df['high_change_1'] = df['high'].pct_change(1)
        df['high_change_3'] = df['high'].pct_change(3)
        
        # Range as percentage
        df['range_pct'] = (df['high'] - df['low']) / df['close'].replace(0, np.nan)
        
        return df
    
    # =========================================================================
    # LAG FEATURES
    # =========================================================================
    
    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lag features for key indicators."""
        
        # RSI lags
        for i in range(1, 6):
            df[f'rsi_lag{i}'] = df['rsi_value'].shift(i)
        
        # BB position lags
        for i in range(1, 4):
            df[f'bb_position_lag{i}'] = df['bb_position'].shift(i)
        
        # Price change lags
        for i in range(1, 4):
            df[f'price_change_lag{i}'] = df['price_change_1'].shift(i)
        
        # Volume ratio lags
        for i in range(1, 4):
            df[f'volume_ratio_lag{i}'] = df['volume_ratio'].shift(i)
        
        # BB width lags
        for i in range(1, 3):
            df[f'bb_width_lag{i}'] = df['bb_width_pct'].shift(i)
        
        # Trend strength lags
        for i in range(1, 3):
            df[f'trend_strength_lag{i}'] = df['trend_strength'].shift(i)
        
        return df
    
    # =========================================================================
    # SLOPE FEATURES
    # =========================================================================
    
    def _add_slope_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add slope (rate of change) features."""
        
        # RSI slopes
        df['rsi_slope_3'] = (df['rsi_value'] - df['rsi_value'].shift(3)) / 3
        df['rsi_slope_5'] = (df['rsi_value'] - df['rsi_value'].shift(5)) / 5
        df['rsi_slope_10'] = (df['rsi_value'] - df['rsi_value'].shift(10)) / 10
        
        # Price slopes
        df['price_slope_3'] = df['close'].pct_change(3) / 3
        df['price_slope_5'] = df['close'].pct_change(5) / 5
        df['price_slope_10'] = df['close'].pct_change(10) / 10
        
        # BB position slope
        df['bb_position_slope_3'] = (df['bb_position'] - df['bb_position'].shift(3)) / 3
        df['bb_position_slope_5'] = (df['bb_position'] - df['bb_position'].shift(5)) / 5
        
        # Volume slope
        df['volume_slope_3'] = (df['volume_ratio'] - df['volume_ratio'].shift(3)) / 3
        
        # BB width slope (squeeze/expansion)
        df['bb_width_slope_3'] = (df['bb_width_pct'] - df['bb_width_pct'].shift(3)) / 3
        df['bb_width_slope_5'] = (df['bb_width_pct'] - df['bb_width_pct'].shift(5)) / 5
        
        # Trend strength slope
        df['trend_slope_3'] = (df['trend_strength'] - df['trend_strength'].shift(3)) / 3
        
        return df
    
    # =========================================================================
    # NEW: Z-SCORE FEATURES
    # =========================================================================
    
    def _add_zscore_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add z-score features for detecting statistical extremes.
        
        Z-score = (value - rolling_mean) / rolling_std
        High positive z-score on price/RSI = statistically overbought
        """
        window = self.WINDOW_LONG
        
        # Price z-score
        price_mean = df['close'].rolling(window, min_periods=10).mean()
        price_std = df['close'].rolling(window, min_periods=10).std()
        df['price_zscore'] = (df['close'] - price_mean) / price_std.replace(0, np.nan)
        
        # RSI z-score (unusual RSI readings)
        rsi_mean = df['rsi_value'].rolling(window, min_periods=10).mean()
        rsi_std = df['rsi_value'].rolling(window, min_periods=10).std()
        df['rsi_zscore'] = (df['rsi_value'] - rsi_mean) / rsi_std.replace(0, np.nan)
        
        # Volume z-score
        vol_mean = df['volume'].rolling(window, min_periods=10).mean()
        vol_std = df['volume'].rolling(window, min_periods=10).std()
        df['volume_zscore'] = (df['volume'] - vol_mean) / vol_std.replace(0, np.nan)
        
        # BB position z-score
        bb_mean = df['bb_position'].rolling(window, min_periods=10).mean()
        bb_std = df['bb_position'].rolling(window, min_periods=10).std()
        df['bb_position_zscore'] = (df['bb_position'] - bb_mean) / bb_std.replace(0, np.nan)
        
        # ATR z-score (unusual volatility)
        atr_mean = df['atr_pct'].rolling(window, min_periods=10).mean()
        atr_std = df['atr_pct'].rolling(window, min_periods=10).std()
        df['atr_zscore'] = (df['atr_pct'] - atr_mean) / atr_std.replace(0, np.nan)
        
        # High z-score (for SHORT - detecting extreme highs)
        high_mean = df['high'].rolling(window, min_periods=10).mean()
        high_std = df['high'].rolling(window, min_periods=10).std()
        df['high_zscore'] = (df['high'] - high_mean) / high_std.replace(0, np.nan)
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW: ROLLING STATISTICS
    # =========================================================================
    
    def _add_rolling_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add rolling statistical features.
        
        - Standard deviation (volatility)
        - Skewness (distribution asymmetry)
        - Kurtosis (tail heaviness)
        """
        window = self.WINDOW_LONG
        
        # Price rolling stats
        price_std = df['close'].rolling(window, min_periods=10).std()
        df['price_rolling_std'] = price_std / df['close'].replace(0, np.nan)
        
        # RSI rolling stats
        df['rsi_rolling_std'] = df['rsi_value'].rolling(window, min_periods=10).std()
        df['rsi_rolling_max'] = df['rsi_value'].rolling(window, min_periods=10).max()
        df['rsi_rolling_min'] = df['rsi_value'].rolling(window, min_periods=10).min()
        df['rsi_range'] = df['rsi_rolling_max'] - df['rsi_rolling_min']
        
        # BB position rolling stats
        df['bb_position_rolling_std'] = df['bb_position'].rolling(window, min_periods=10).std()
        df['bb_position_rolling_max'] = df['bb_position'].rolling(window, min_periods=10).max()
        
        # Volume rolling stats
        vol_mean = df['volume'].rolling(window, min_periods=10).mean()
        vol_std = df['volume'].rolling(window, min_periods=10).std()
        df['volume_rolling_std'] = vol_std / vol_mean.replace(0, np.nan)
        
        # Skewness (positive skew = more extreme highs)
        df['price_skew_20'] = df['close'].rolling(window, min_periods=8).apply(
            lambda x: scipy_stats.skew(x) if len(x) >= 8 and x.std() > 0 else 0, raw=True
        )
        
        # Kurtosis (high kurtosis = fat tails, extreme moves)
        df['price_kurtosis_20'] = df['close'].rolling(window, min_periods=8).apply(
            lambda x: scipy_stats.kurtosis(x) if len(x) >= 8 and x.std() > 0 else 0, raw=True
        )
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW: PERCENTILE FEATURES
    # =========================================================================
    
    def _add_percentile_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add percentile rank features.
        
        Shows where current value sits relative to recent history.
        For SHORT: high percentile on price/RSI = overbought
        """
        window = self.WINDOW_LONG
        
        def calc_percentile(x):
            if len(x) < 10:
                return 0.5
            return scipy_stats.percentileofscore(x, x.iloc[-1]) / 100
        
        # Price percentile
        df['price_percentile'] = df['close'].rolling(window, min_periods=10).apply(
            calc_percentile, raw=False
        )
        
        # RSI percentile
        df['rsi_percentile'] = df['rsi_value'].rolling(window, min_periods=10).apply(
            calc_percentile, raw=False
        )
        
        # Volume percentile
        df['volume_percentile'] = df['volume'].rolling(window, min_periods=10).apply(
            calc_percentile, raw=False
        )
        
        # BB position percentile
        df['bb_position_percentile'] = df['bb_position'].rolling(window, min_periods=10).apply(
            calc_percentile, raw=False
        )
        
        # High percentile (for SHORT)
        df['high_percentile'] = df['high'].rolling(window, min_periods=10).apply(
            calc_percentile, raw=False
        )
        
        return df.fillna(0.5)
    
    # =========================================================================
    # NEW: RATE OF CHANGE (ROC) FEATURES
    # =========================================================================
    
    def _add_roc_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Rate of Change momentum features.
        
        ROC = (current - previous) / previous * 100
        Measures momentum strength
        """
        # Price ROC
        df['price_roc_3'] = ((df['close'] - df['close'].shift(3)) / df['close'].shift(3).replace(0, np.nan)) * 100
        df['price_roc_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5).replace(0, np.nan)) * 100
        df['price_roc_10'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10).replace(0, np.nan)) * 100
        
        # RSI ROC (momentum of momentum)
        df['rsi_roc_3'] = df['rsi_value'] - df['rsi_value'].shift(3)
        df['rsi_roc_5'] = df['rsi_value'] - df['rsi_value'].shift(5)
        
        # Volume ROC
        df['volume_roc_3'] = ((df['volume'] - df['volume'].shift(3)) / df['volume'].shift(3).replace(0, np.nan)) * 100
        
        # BB Width ROC (squeeze detection)
        df['bb_width_roc_5'] = ((df['bb_width_pct'] - df['bb_width_pct'].shift(5)) / 
                                df['bb_width_pct'].shift(5).replace(0, np.nan)) * 100
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW: ACCELERATION FEATURES
    # =========================================================================
    
    def _add_acceleration_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add acceleration/deceleration features.
        
        Acceleration = change in velocity (second derivative)
        Negative acceleration after positive velocity = exhaustion signal
        """
        # Price velocity (first derivative)
        df['price_velocity'] = df['close'].diff()
        
        # Price acceleration (second derivative)
        df['price_acceleration'] = df['price_velocity'].diff()
        
        # Normalized acceleration
        df['price_accel_norm'] = df['price_acceleration'] / df['close'].replace(0, np.nan)
        
        # RSI velocity and acceleration
        df['rsi_velocity'] = df['rsi_value'].diff()
        df['rsi_acceleration'] = df['rsi_velocity'].diff()
        
        # Momentum deceleration (key for SHORT)
        # Price still rising but at decreasing rate
        df['momentum_deceleration'] = (
            (df['price_velocity'] > 0) & 
            (df['price_acceleration'] < 0)
        ).fillna(0).astype(int)
        
        # RSI deceleration
        df['rsi_deceleration'] = (
            (df['rsi_velocity'] > 0) & 
            (df['rsi_acceleration'] < 0)
        ).fillna(0).astype(int)
        
        # Smoothed acceleration (less noisy)
        df['price_accel_smooth'] = df['price_acceleration'].rolling(3, min_periods=2).mean()
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW: MOMENTUM DIVERGENCE FEATURES - FIXED
    # =========================================================================
    
    def _add_momentum_divergence(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add momentum divergence features.
        
        Divergence = price and momentum indicator moving in opposite directions
        For SHORT: price higher high + RSI lower high = bearish divergence
        """
        # 10-bar divergence
        price_higher_10 = df['high'] > df['high'].shift(10)
        rsi_lower_10 = df['rsi_value'] < df['rsi_value'].shift(10)
        df['bearish_div_10'] = (price_higher_10 & rsi_lower_10).fillna(0).astype(int)
        
        # 3-bar quick divergence
        price_higher_3 = df['high'] > df['high'].shift(3)
        rsi_lower_3 = df['rsi_value'] < df['rsi_value'].shift(3)
        df['bearish_div_3'] = (price_higher_3 & rsi_lower_3).fillna(0).astype(int)
        
        # Volume divergence (price up, volume down = weak rally)
        price_up = df['close'] > df['close'].shift(5)
        volume_down = df['volume'] < df['volume'].shift(5)
        df['volume_divergence'] = (price_up & volume_down).fillna(0).astype(int)
        
        # Momentum divergence strength (continuous)
        price_change_5 = df['close'].pct_change(5)
        rsi_change_5 = df['rsi_value'].diff(5)
        df['divergence_strength'] = np.where(
            price_change_5 > 0,
            -rsi_change_5 / (price_change_5 * 100 + 0.001),
            0
        )
        df['divergence_strength'] = df['divergence_strength'].clip(-5, 5)
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW: CONSECUTIVE PATTERN FEATURES - FIXED
    # =========================================================================
    
    def _add_consecutive_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add consecutive candle pattern features.
        
        For SHORT: consecutive green candles = exhaustion setup
        """
        # Consecutive bullish candles
        bullish = (df['close'] > df['open']).fillna(0).astype(int)
        
        # Count consecutive bullish candles
        df['consecutive_bullish'] = bullish.groupby(
            (bullish != bullish.shift()).cumsum()
        ).cumsum() * bullish
        
        # Count consecutive bearish candles
        bearish = (df['close'] < df['open']).fillna(0).astype(int)
        df['consecutive_bearish'] = bearish.groupby(
            (bearish != bearish.shift()).cumsum()
        ).cumsum() * bearish
        
        # Consecutive higher highs
        higher_high = (df['high'] > df['high'].shift(1)).fillna(0).astype(int)
        df['consecutive_higher_highs'] = higher_high.groupby(
            (higher_high != higher_high.shift()).cumsum()
        ).cumsum() * higher_high
        
        # Consecutive higher closes
        higher_close = (df['close'] > df['close'].shift(1)).fillna(0).astype(int)
        df['consecutive_higher_closes'] = higher_close.groupby(
            (higher_close != higher_close.shift()).cumsum()
        ).cumsum() * higher_close
        
        # Exhaustion signal: many consecutive bullish followed by bearish
        df['bullish_exhaustion'] = (
            (df['consecutive_bullish'].shift(1) >= 3) & 
            (df['close'] < df['open'])
        ).fillna(0).astype(int)
        
        return df
    
    # =========================================================================
    # NEW: REVERSAL PATTERN FEATURES - FIXED
    # =========================================================================
    
    def _add_reversal_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add reversal pattern detection features for SHORT.
        """
        # Upper wick ratio (rejection from highs)
        total_range = df['high'] - df['low']
        upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
        df['upper_wick_ratio'] = np.where(total_range > 0, upper_wick / total_range, 0)
        
        # Shooting star pattern (small body at bottom, long upper wick)
        body = (df['close'] - df['open']).abs()
        body_bottom = df[['open', 'close']].min(axis=1)
        lower_wick = body_bottom - df['low']
        
        df['shooting_star'] = (
            (df['upper_wick_ratio'] > 0.6) &
            (body / total_range.replace(0, np.nan) < 0.3) &
            (lower_wick / total_range.replace(0, np.nan) < 0.1)
        ).fillna(0).astype(int)
        
        # Bearish engulfing
        prev_bullish = df['close'].shift(1) > df['open'].shift(1)
        curr_bearish = df['close'] < df['open']
        engulfs_prev = (df['open'] > df['close'].shift(1)) & (df['close'] < df['open'].shift(1))
        df['bearish_engulfing'] = (prev_bullish & curr_bearish & engulfs_prev).fillna(0).astype(int)
        
        # Evening star setup (3-candle pattern)
        day1_bullish = (df['close'].shift(2) - df['open'].shift(2)) > 0.003 * df['close'].shift(2)
        day2_small = (df['close'].shift(1) - df['open'].shift(1)).abs() < 0.001 * df['close'].shift(1)
        day1_mid = (df['open'].shift(2) + df['close'].shift(2)) / 2
        day3_bearish = (df['close'] < df['open']) & (df['close'] < day1_mid)
        df['evening_star'] = (day1_bullish & day2_small & day3_bearish).fillna(0).astype(int)
        
        # Double top approach (near recent high)
        rolling_max = df['high'].rolling(20, min_periods=5).max()
        df['near_double_top'] = (
            (df['high'] >= rolling_max * 0.998) &
            (df['high'] <= rolling_max)
        ).fillna(0).astype(int)
        
        return df
    
    # =========================================================================
    # NEW: BOLLINGER BAND PATTERN FEATURES - FIXED
    # =========================================================================
    
    def _add_bb_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Bollinger Band pattern features.
        """
        # BB squeeze (low volatility, potential breakout)
        bb_width_mean = df['bb_width_pct'].rolling(20, min_periods=5).mean()
        df['bb_squeeze'] = (df['bb_width_pct'] < bb_width_mean * 0.8).fillna(0).astype(int)
        
        # BB expansion (after squeeze)
        df['bb_expansion'] = (
            (df['bb_width_pct'] > df['bb_width_pct'].shift(1)) &
            (df['bb_squeeze'].shift(1) == 1)
        ).fillna(0).astype(int)
        
        # Walking the band (multiple touches = trend strength)
        df['walking_upper_band'] = (
            (df['bb_position'] > 0.9) &
            (df['bb_position'].shift(1) > 0.9) &
            (df['bb_position'].shift(2) > 0.9)
        ).fillna(0).astype(int)
        
        # BB rejection (touched and reversed)
        touched_upper = df['high'] >= df['upper_band']
        closed_below = df['close'] < df['upper_band']
        df['bb_upper_rejection'] = (touched_upper & closed_below).fillna(0).astype(int)
        
        # Distance from bands (normalized)
        bb_range = df['upper_band'] - df['lower_band']
        df['distance_from_upper'] = (df['upper_band'] - df['close']) / bb_range.replace(0, np.nan)
        df['distance_from_lower'] = (df['close'] - df['lower_band']) / bb_range.replace(0, np.nan)
        
        # Overextension (price above upper band)
        df['bb_overextended'] = ((df['close'] - df['upper_band']) / bb_range.replace(0, np.nan)).clip(0, 1)
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW: VOLUME PATTERN FEATURES - FIXED
    # =========================================================================
    
    def _add_volume_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add volume pattern features.
        """
        # Volume climax (extreme volume at price extreme)
        high_volume = df['volume_ratio'] > 2.0
        at_high = df['bb_position'] > 0.9
        df['volume_climax_top'] = (high_volume & at_high).fillna(0).astype(int)
        
        # Declining volume on rally (weak hands)
        df['volume_decline_3'] = (
            (df['volume'] < df['volume'].shift(1)) &
            (df['volume'].shift(1) < df['volume'].shift(2)) &
            (df['close'] > df['close'].shift(2))
        ).fillna(0).astype(int)
        
        # Volume spike with rejection
        volume_spike = df['volume_ratio'] > 1.5
        upper_rejection = df['upper_wick_ratio'] > 0.5
        df['volume_spike_rejection'] = (volume_spike & upper_rejection).fillna(0).astype(int)
        
        # Relative volume trend
        vol_ma5 = df['volume'].rolling(5, min_periods=3).mean()
        vol_ma20 = df['volume'].rolling(20, min_periods=5).mean()
        df['volume_trend'] = vol_ma5 / vol_ma20.replace(0, np.nan)
        
        # On-Balance Volume simplified (accumulation/distribution)
        price_direction = np.sign(df['close'].diff())
        df['obv_direction'] = (df['volume'] * price_direction).rolling(10, min_periods=3).sum()
        df['obv_divergence'] = (
            (df['close'] > df['close'].shift(10)) &
            (df['obv_direction'] < df['obv_direction'].shift(10))
        ).fillna(0).astype(int)
        
        return df.fillna(0)
    
    # =========================================================================
    # QUALITY FEATURES - FIXED
    # =========================================================================
    
    def _add_quality_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add quality indicator features for SHORT setups.
        """
        # RSI peaked (declining from high)
        df['rsi_peaked'] = (
            (df['rsi_value'] < df['rsi_value'].shift(1)) &
            (df['rsi_value'].shift(1) > 65)
        ).fillna(0).astype(int)
        
        # RSI drop size
        df['rsi_drop_size'] = (df['rsi_value'].shift(1) - df['rsi_value']).clip(lower=0)
        df['rsi_drop_large'] = (df['rsi_drop_size'] > 5).fillna(0).astype(int)
        
        # RSI was extreme
        df['rsi_was_extreme'] = (df['rsi_value'].shift(1) > 70).fillna(0).astype(int)
        
        # Strong negative RSI slope
        df['rsi_slope_strong_neg'] = (df['rsi_slope_3'] < -5).fillna(0).astype(int)
        
        # RSI momentum shift (was rising, now falling)
        rsi_was_rising = df['rsi_value'].shift(1) > df['rsi_value'].shift(2)
        rsi_now_falling = df['rsi_value'] < df['rsi_value'].shift(1)
        df['rsi_momentum_shift'] = (rsi_was_rising & rsi_now_falling).fillna(0).astype(int)
        
        # BB extreme positions
        df['bb_extreme_prev'] = (df['bb_position'].shift(1) > 0.95).fillna(0).astype(int)
        
        # Recently touched upper
        df['touched_prev_1'] = df['touched_upper_bb'].shift(1).fillna(0).astype(int)
        df['touched_prev_2'] = df['touched_upper_bb'].shift(2).fillna(0).astype(int)
        df['touched_recently'] = ((df['touched_prev_1'] == 1) | (df['touched_prev_2'] == 1)).fillna(0).astype(int)
        
        # Rejection candle (long upper wick)
        df['rejection_candle'] = (df['upper_wick_ratio'] > 0.5).fillna(0).astype(int)
        
        # Volume spike
        df['volume_spike'] = (df['volume_ratio'] > 1.3).fillna(0).astype(int)
        
        # High volume reversal
        df['high_volume_reversal'] = (
            (df['bearish_candle'] == 1) & (df['volume_ratio'] > 1.2)
        ).fillna(0).astype(int)
        
        # Context: not choppy
        df['not_choppy'] = (df['time_since_last_touch'] > 3).fillna(0).astype(int)
        
        # First touch (vs repeated) - CHECK IF COLUMN EXISTS
        if 'previous_touches' in df.columns:
            df['first_touch'] = (df['previous_touches'] <= 1).fillna(0).astype(int)
        else:
            df['first_touch'] = 0
        
        return df
    
    # =========================================================================
    # EXHAUSTION SCORE (COMPOSITE)
    # =========================================================================
    
    def _add_exhaustion_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add composite exhaustion score (0-1).
        
        Higher score = better SHORT exhaustion setup.
        """
        # BB extremity score
        bb_score = df['bb_position'].clip(0, 1)
        
        # RSI exhaustion score
        rsi_score = (
            0.25 * df['rsi_peaked'] +
            0.25 * df['rsi_drop_large'] +
            0.25 * df['rsi_was_extreme'] +
            0.25 * df['rsi_slope_strong_neg']
        ).clip(0, 1)
        
        # Momentum reversal score
        momentum_score = (
            0.4 * df['rsi_momentum_shift'] +
            0.3 * df['momentum_deceleration'] +
            0.3 * np.clip(-df['rsi_slope_3'].fillna(0) / 10, 0, 1)
        ).clip(0, 1)
        
        # Pattern confirmation score
        pattern_score = (
            0.3 * df['shooting_star'] +
            0.3 * df['bearish_engulfing'] +
            0.2 * df['bb_upper_rejection'] +
            0.2 * df['rejection_candle']
        ).clip(0, 1)
        
        # Volume confirmation score
        volume_score = (
            0.4 * df['volume_spike'] +
            0.3 * df['high_volume_reversal'] +
            0.3 * df['volume_climax_top']
        ).clip(0, 1)
        
        # Statistical extremes score - ALL TERMS HAVE .fillna(0)
        stat_score = (
            0.3 * (df['price_zscore'].fillna(0) > 2).astype(int) +
            0.3 * (df['rsi_zscore'].fillna(0) > 1.5).astype(int) +
            0.4 * (df['price_percentile'].fillna(0) > 0.9).astype(int)
        ).clip(0, 1)
        
        # Composite exhaustion score
        df['exhaustion_score'] = (
            0.20 * bb_score +
            0.20 * rsi_score +
            0.15 * momentum_score +
            0.15 * pattern_score +
            0.15 * volume_score +
            0.15 * stat_score
        ).clip(0, 1)
        
        # Exhaustion category (for quick filtering)
        exhaustion_level = pd.cut(
            df['exhaustion_score'].clip(0, 1).fillna(0),
            bins=[0, 0.3, 0.5, 0.7, 1.0],
            labels=[0, 1, 2, 3],
            include_lowest=True
        )

        df['exhaustion_level'] = exhaustion_level.astype('float').fillna(0).astype(int)

        
        return df
    
    # =========================================================================
    # FEATURE LIST
    # =========================================================================
    
    def get_feature_names(self) -> Dict[str, List[str]]:
        """Return categorized feature names."""
        return {
            'binary': [
                'touched_upper_bb', 'rsi_overbought', 'rsi_extreme_overbought',
                'rsi_very_extreme', 'bearish_candle', 'strong_bearish',
                'bb_very_high', 'bb_above_upper', 'high_volume', 'extreme_volume',
                'strong_uptrend'
            ],
            'price_change': [
                'price_change_1', 'price_change_3', 'price_change_5', 'price_change_10',
                'high_change_1', 'high_change_3', 'range_pct'
            ],
            'lags': [
                'rsi_lag1', 'rsi_lag2', 'rsi_lag3', 'rsi_lag4', 'rsi_lag5',
                'bb_position_lag1', 'bb_position_lag2', 'bb_position_lag3',
                'price_change_lag1', 'price_change_lag2', 'price_change_lag3',
                'volume_ratio_lag1', 'volume_ratio_lag2', 'volume_ratio_lag3',
                'bb_width_lag1', 'bb_width_lag2',
                'trend_strength_lag1', 'trend_strength_lag2'
            ],
            'slopes': [
                'rsi_slope_3', 'rsi_slope_5', 'rsi_slope_10',
                'price_slope_3', 'price_slope_5', 'price_slope_10',
                'bb_position_slope_3', 'bb_position_slope_5',
                'volume_slope_3', 'bb_width_slope_3', 'bb_width_slope_5',
                'trend_slope_3'
            ],
            'zscores': [
                'price_zscore', 'rsi_zscore', 'volume_zscore',
                'bb_position_zscore', 'atr_zscore', 'high_zscore'
            ],
            'rolling_stats': [
                'price_rolling_std', 'rsi_rolling_std', 'rsi_rolling_max',
                'rsi_rolling_min', 'rsi_range', 'bb_position_rolling_std',
                'bb_position_rolling_max', 'volume_rolling_std',
                'price_skew_20', 'price_kurtosis_20'
            ],
            'percentiles': [
                'price_percentile', 'rsi_percentile', 'volume_percentile',
                'bb_position_percentile', 'high_percentile'
            ],
            'momentum': [
                'price_roc_3', 'price_roc_5', 'price_roc_10',
                'rsi_roc_3', 'rsi_roc_5', 'volume_roc_3', 'bb_width_roc_5',
                'price_velocity', 'price_acceleration', 'price_accel_norm',
                'rsi_velocity', 'rsi_acceleration',
                'momentum_deceleration', 'rsi_deceleration', 'price_accel_smooth'
            ],
            'divergence': [
                'bearish_div_10', 'bearish_div_3', 'volume_divergence',
                'divergence_strength'
            ],
            'patterns': [
                'consecutive_bullish', 'consecutive_bearish',
                'consecutive_higher_highs', 'consecutive_higher_closes',
                'bullish_exhaustion', 'upper_wick_ratio', 'shooting_star',
                'bearish_engulfing', 'evening_star', 'near_double_top'
            ],
            'bb_patterns': [
                'bb_squeeze', 'bb_expansion', 'walking_upper_band',
                'bb_upper_rejection', 'distance_from_upper', 'distance_from_lower',
                'bb_overextended'
            ],
            'volume_patterns': [
                'volume_climax_top', 'volume_decline_3', 'volume_spike_rejection',
                'volume_trend', 'obv_direction', 'obv_divergence'
            ],
            'quality': [
                'rsi_peaked', 'rsi_drop_size', 'rsi_drop_large', 'rsi_was_extreme',
                'rsi_slope_strong_neg', 'rsi_momentum_shift', 'bb_extreme_prev',
                'touched_prev_1', 'touched_prev_2', 'touched_recently',
                'rejection_candle', 'volume_spike', 'high_volume_reversal',
                'not_choppy', 'first_touch'
            ],
            'composite': [
                'exhaustion_score', 'exhaustion_level'
            ]
        }
    
    def get_all_feature_names(self) -> List[str]:
        """Return flat list of all derived feature names."""
        all_features = []
        for category_features in self.get_feature_names().values():
            all_features.extend(category_features)
        return all_features


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def calculate_all_features(
    df: pd.DataFrame,
    verbose: bool = False,
    drop_na: bool = True
) -> pd.DataFrame:
    """
    Calculate all derived features from EA CSV output.
    
    Args:
        df: DataFrame from DataExporterEA_SHORT.mq5 CSV
        verbose: Print progress information
        drop_na: Drop rows with NaN values
        
    Returns:
        DataFrame with all calculated features
    """
    fe = FeatureEngineering(verbose=verbose)
    return fe.calculate_features(df, drop_na=drop_na)


# =============================================================================
# PART 2: DATA CLASSES FOR RFE
# =============================================================================

@dataclass
class FeatureRanking:
    """Feature ranking information."""
    feature_name: str
    rank: int
    selected: bool
    importance: float = 0.0


@dataclass
class RFEResult:
    """Result of RFE feature selection."""
    selected_features: List[str]
    n_features_selected: int
    n_features_original: int
    feature_rankings: List[FeatureRanking]
    optimal_n_features: Optional[int] = None
    cv_scores: Optional[List[float]] = None
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert rankings to DataFrame."""
        data = [
            {
                'feature_name': r.feature_name,
                'rank': r.rank,
                'selected': r.selected,
                'importance': r.importance
            }
            for r in self.feature_rankings
        ]
        return pd.DataFrame(data).sort_values('rank').reset_index(drop=True)
    
    def get_selected_features(self) -> List[str]:
        """Get list of selected feature names."""
        return self.selected_features.copy()


# =============================================================================
# PART 2: FEATURE UTILITIES
# =============================================================================

def get_feature_columns(
    df: pd.DataFrame,
    exclude_columns: Optional[List[str]] = None
) -> List[str]:
    """Identify feature columns from DataFrame."""
    if exclude_columns is None:
        exclude_columns = []
    
    default_exclusions = {
        'timestamp', 'pair', 'symbol',
        'open', 'high', 'low', 'close', 'volume',
        'label', 'label_reason', 'signal', 'regime',
        'lower_band', 'middle_band', 'upper_band'
    }
    
    exclude_set = set(col.lower() for col in exclude_columns)
    exclude_set.update(default_exclusions)
    
    feature_columns = [
        col for col in df.columns
        if col.lower() not in exclude_set
        and pd.api.types.is_numeric_dtype(df[col])
    ]
    
    return feature_columns


def validate_features(
    df: pd.DataFrame,
    feature_columns: List[str]
) -> Tuple[List[str], Dict[str, Any]]:
    """Validate feature columns and return valid ones."""
    report = {
        'original_count': len(feature_columns),
        'valid_count': 0,
        'issues': {},
        'dropped': []
    }
    
    valid_features = []
    
    for col in feature_columns:
        issues = []
        
        if col not in df.columns:
            issues.append('missing')
            report['issues'][col] = issues
            report['dropped'].append(col)
            continue
        
        series = df[col]
        
        nan_count = series.isna().sum()
        if nan_count > 0:
            nan_pct = nan_count / len(series) * 100
            if nan_pct > 10:
                issues.append(f'high_nan ({nan_pct:.1f}%)')
            else:
                issues.append(f'some_nan ({nan_count})')
        
        if np.isinf(series).any():
            inf_count = np.isinf(series).sum()
            issues.append(f'infinite ({inf_count})')
        
        if series.std() == 0:
            issues.append('zero_variance')
        
        critical_issues = {'missing', 'zero_variance'}
        has_critical = any(
            issue.split()[0] in critical_issues or issue.startswith('high_nan')
            for issue in issues
        )
        
        if has_critical:
            report['issues'][col] = issues
            report['dropped'].append(col)
        else:
            valid_features.append(col)
            if issues:
                report['issues'][col] = issues
    
    report['valid_count'] = len(valid_features)
    
    return valid_features, report


def prepare_features(
    df: pd.DataFrame,
    feature_columns: List[str],
    handle_nan: str = 'drop',
    handle_inf: str = 'clip'
) -> Tuple[pd.DataFrame, List[str]]:
    """Prepare feature DataFrame for model training."""
    available_features = [col for col in feature_columns if col in df.columns]
    X = df[available_features].copy()
    
    if handle_inf == 'clip':
        for col in X.columns:
            if X[col].dtype in [np.float64, np.float32]:
                max_val = np.finfo(X[col].dtype).max / 10
                X[col] = X[col].clip(-max_val, max_val)
    elif handle_inf == 'replace_nan':
        X = X.replace([np.inf, -np.inf], np.nan)
    
    if handle_nan == 'fill_mean':
        X = X.fillna(X.mean())
    elif handle_nan == 'fill_zero':
        X = X.fillna(0)
    
    return X, available_features


# =============================================================================
# PART 2: RECURSIVE FEATURE ELIMINATION
# =============================================================================

def rfe_select(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    min_features: int = 5,
    max_features: int = 15,
    cv_folds: int = 3,
    scoring: str = 'average_precision',
    use_rfecv: bool = True,
    random_state: int = 42
) -> RFEResult:
    """Perform Recursive Feature Elimination to select optimal features."""
    available_features = [col for col in feature_columns if col in X_train.columns]
    X = X_train[available_features].copy()
    y = y_train.copy()
    
    valid_mask = ~(X.isna().any(axis=1) | y.isna())
    X = X[valid_mask]
    y = y[valid_mask]
    
    if len(X) < 50:
        warnings.warn(f"Very small training set for RFE: {len(X)} rows")
    
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.mean())
    
    n_original = len(available_features)
    
    estimator = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        min_samples_leaf=20,
        random_state=random_state,
        validation_fraction=0.1,
        n_iter_no_change=10
    )
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=ConvergenceWarning)
        warnings.filterwarnings('ignore', category=UserWarning)
        
        if use_rfecv:
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
            
            selector = RFECV(
                estimator=estimator,
                step=1,
                cv=cv,
                scoring=scoring,
                min_features_to_select=min_features,
                n_jobs=-1
            )
            
            try:
                selector.fit(X, y)
                optimal_n = selector.n_features_
                cv_scores = selector.cv_results_['mean_test_score'].tolist()
            except Exception as e:
                warnings.warn(f"RFECV failed: {e}. Falling back to RFE.")
                use_rfecv = False
        
        if not use_rfecv:
            n_features_to_select = min(max_features, n_original)
            n_features_to_select = max(n_features_to_select, min_features)
            
            selector = RFE(
                estimator=estimator,
                n_features_to_select=n_features_to_select,
                step=1
            )
            
            selector.fit(X, y)
            optimal_n = n_features_to_select
            cv_scores = None
    
    if optimal_n > max_features:
        selector = RFE(
            estimator=estimator,
            n_features_to_select=max_features,
            step=1
        )
        selector.fit(X, y)
        optimal_n = max_features
    
    selected_mask = selector.support_
    rankings = selector.ranking_
    
    try:
        importances = selector.estimator_.feature_importances_
    except AttributeError:
        importances = np.zeros(sum(selected_mask))
    
    feature_rankings = []
    importance_idx = 0
    
    for i, (feat, rank, selected) in enumerate(zip(available_features, rankings, selected_mask)):
        if selected and importance_idx < len(importances):
            imp = importances[importance_idx]
            importance_idx += 1
        else:
            imp = 0.0
        
        feature_rankings.append(FeatureRanking(
            feature_name=feat,
            rank=int(rank),
            selected=bool(selected),
            importance=float(imp)
        ))
    
    feature_rankings.sort(key=lambda x: x.rank)
    selected_features = [fr.feature_name for fr in feature_rankings if fr.selected]
    
    return RFEResult(
        selected_features=selected_features,
        n_features_selected=len(selected_features),
        n_features_original=n_original,
        feature_rankings=feature_rankings,
        optimal_n_features=optimal_n,
        cv_scores=cv_scores
    )


def rfe_select_simple(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    feature_columns: List[str],
    n_features: int = 10,
    random_state: int = 42
) -> RFEResult:
    """Simple RFE without cross-validation (faster)."""
    return rfe_select(
        X_train=X_train,
        y_train=y_train,
        feature_columns=feature_columns,
        min_features=n_features,
        max_features=n_features,
        cv_folds=3,
        use_rfecv=False,
        random_state=random_state
    )


def get_consensus_features(
    fold_results: List[RFEResult],
    min_fold_frequency: float = 0.8,
    method: str = 'frequency'
) -> List[str]:
    """Get consensus features selected across multiple folds."""
    if not fold_results:
        return []
    
    n_folds = len(fold_results)
    
    if method == 'intersection':
        feature_sets = [set(r.selected_features) for r in fold_results]
        consensus = feature_sets[0]
        for fs in feature_sets[1:]:
            consensus = consensus.intersection(fs)
        return list(consensus)
    
    else:
        feature_counts = {}
        for result in fold_results:
            for feat in result.selected_features:
                feature_counts[feat] = feature_counts.get(feat, 0) + 1
        
        min_count = int(n_folds * min_fold_frequency)
        consensus = [
            feat for feat, count in feature_counts.items()
            if count >= min_count
        ]
        
        consensus.sort(key=lambda x: feature_counts[x], reverse=True)
        
        return consensus


def selected_features_to_csv(
    features: List[str],
    importances: Optional[List[float]],
    filepath: str
) -> None:
    """Save selected features to CSV file."""
    if importances is None:
        importances = [1.0 / len(features)] * len(features)
    
    if len(importances) != len(features):
        importances = [1.0 / len(features)] * len(features)
    
    df = pd.DataFrame({
        'feature_name': features,
        'rank': range(1, len(features) + 1),
        'importance': importances
    })
    
    df.to_csv(filepath, index=False)