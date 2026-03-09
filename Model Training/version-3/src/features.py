"""
Feature engineering and selection - COMPREHENSIVE SHORT STRATEGY.

VERSION: 4.0 - ENHANCED WITH SESSION, REGIME, AND ADVANCED FEATURES

PIPELINE:
=========
1. DataExporterEA_SHORT.mq5 calculates BASE features from raw OHLCV
2. This module calculates DERIVED + STATISTICAL + MOMENTUM + SESSION + REGIME features

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

STATISTICAL FEATURES:
─────────────────────
• Rolling statistics (std, skewness, kurtosis)
• Z-scores (price, RSI, volume)
• Percentile ranks
• Volatility measures

MOMENTUM FEATURES:
──────────────────
• Rate of Change (ROC)
• Momentum oscillators
• Acceleration/deceleration
• Trend exhaustion indicators

PATTERN FEATURES:
─────────────────
• Consecutive candle patterns
• Reversal pattern detection
• Volume profile analysis
• BB squeeze detection

NEW IN V4.0 - SESSION & TIME:
─────────────────────────────
• Session flags (London, NY, Asian, Overlap)
• Hour of day (sin/cos encoded)
• Day of week
• Time-based volatility patterns

NEW IN V4.0 - REGIME AWARENESS:
───────────────────────────────
• Market regime classification (trending/ranging/volatile)
• Regime-specific indicators
• ADX-based trend detection

NEW IN V4.0 - MEAN REVERSION:
─────────────────────────────
• Distance from moving averages
• Overextension indicators
• Reversion probability signals

NEW IN V4.0 - ADVANCED VOLATILITY:
──────────────────────────────────
• ATR percentile rank
• Volatility regime classification
• Squeeze/expansion detection
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass
import warnings
import logging
import os
from scipy import stats as scipy_stats

# Suppress CUDA/GPU compilation warnings
os.environ['LIGHTGBM_VERBOSITY'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')

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
    
    VERSION 4.0 - Enhanced with Session, Regime, Mean Reversion
    
    Calculates DERIVED features from EA CSV output including:
    - Lag features
    - Slope features
    - Statistical features (z-scores, percentiles, rolling stats)
    - Momentum features (ROC, acceleration)
    - Pattern features (consecutive candles, reversals)
    - Quality indicators
    - Exhaustion score
    - SESSION features (London, NY, Asian, Overlap)
    - TIME features (hour, day of week)
    - REGIME features (trending, ranging, volatile)
    - MEAN REVERSION features
    - ADVANCED VOLATILITY features
    """
    
    # Rolling window sizes
    WINDOW_SHORT = 5
    WINDOW_MEDIUM = 10
    WINDOW_LONG = 20
    WINDOW_EXTENDED = 50
    WINDOW_VOLATILITY = 100
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        if verbose:
            logging.basicConfig(level=logging.INFO)
    
    def calculate_features(
        self, 
        df: pd.DataFrame,
        drop_na: bool = True,
        min_periods: int = 30  # Increased for extended rolling stats
    ) -> pd.DataFrame:
        """
        Calculate all DERIVED features from EA CSV output.
        
        Args:
            df: DataFrame from DataExporterEA_SHORT.mq5 CSV output
            drop_na: If True, drop rows with NaN. If False, forward fill.
            min_periods: Number of initial rows to drop (default 30 for rolling stats)
                
        Returns:
            DataFrame with original data and all calculated features
        """
        self._validate_input(df)
        
        if self.verbose:
            logging.info(f"Input shape: {df.shape}")
            logging.info("Calculating comprehensive features for SHORT strategy (V4.0)")
        
        df_features = df.copy()
        df_features.columns = df_features.columns.str.lower()
        
        # Fix BB position if needed
        df_features = self._fix_bb_position_if_needed(df_features)
        
        # === ORIGINAL DERIVED FEATURES ===
        df_features = self._add_binary_features(df_features)
        df_features = self._add_price_change_features(df_features)
        df_features = self._add_lag_features(df_features)
        df_features = self._add_slope_features(df_features)
        
        # === STATISTICAL FEATURES ===
        df_features = self._add_zscore_features(df_features)
        df_features = self._add_rolling_statistics(df_features)
        df_features = self._add_percentile_features(df_features)
        
        # === MOMENTUM FEATURES ===
        df_features = self._add_roc_features(df_features)
        df_features = self._add_acceleration_features(df_features)
        df_features = self._add_momentum_divergence(df_features)
        
        # === PATTERN FEATURES ===
        df_features = self._add_consecutive_patterns(df_features)
        df_features = self._add_reversal_patterns(df_features)
        df_features = self._add_bb_patterns(df_features)
        df_features = self._add_volume_patterns(df_features)
        
        # === NEW V4.0: SESSION & TIME FEATURES ===
        df_features = self._add_session_features(df_features)
        df_features = self._add_time_features(df_features)
        
        # === NEW V4.0: REGIME AWARENESS ===
        df_features = self._add_regime_features(df_features)
        
        # === NEW V4.0: MEAN REVERSION ===
        df_features = self._add_mean_reversion_features(df_features)
        
        # === NEW V4.0: ADVANCED VOLATILITY ===
        df_features = self._add_advanced_volatility_features(df_features)
        
        # === NEW V4.0: MACD FEATURES ===
        df_features = self._add_macd_features(df_features)
        
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
                           'prev_was_rally', 'previous_touches', 'session',
                           'timestamp']
        
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
    # BINARY FEATURES
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
        
        # RSI slopes - CRITICAL FOR MOMENTUM DIRECTION
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
    # Z-SCORE FEATURES
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
    # ROLLING STATISTICS
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
    # PERCENTILE FEATURES
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
    # RATE OF CHANGE (ROC) FEATURES
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
    # ACCELERATION FEATURES
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
    # MOMENTUM DIVERGENCE FEATURES
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
    # CONSECUTIVE PATTERN FEATURES
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
    # REVERSAL PATTERN FEATURES
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
    # BOLLINGER BAND PATTERN FEATURES
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
        
        # NEW: BB squeeze strength (percentile of width)
        df['bb_squeeze_pct'] = df['bb_width_pct'].rolling(50, min_periods=20).apply(
            lambda x: scipy_stats.percentileofscore(x, x.iloc[-1]) / 100 if len(x) >= 20 else 0.5,
            raw=False
        ).fillna(0.5)
        
        return df.fillna(0)
    
    # =========================================================================
    # VOLUME PATTERN FEATURES
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
    # NEW V4.0: SESSION FEATURES
    # =========================================================================
    
    def _add_session_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add trading session features.
        
        Sessions (UTC times, adjust for your broker):
        - Asian:   00:00 - 08:00 UTC
        - London:  08:00 - 16:00 UTC
        - NY:      13:00 - 21:00 UTC
        - Overlap: 13:00 - 16:00 UTC (highest volatility)
        """
        # Try to extract hour from timestamp
        if 'timestamp' in df.columns:
            try:
                # Try to parse timestamp
                if df['timestamp'].dtype == 'object':
                    # Try common formats
                    for fmt in ['%Y.%m.%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']:
                        try:
                            df['_datetime'] = pd.to_datetime(df['timestamp'], format=fmt)
                            break
                        except:
                            continue
                    else:
                        df['_datetime'] = pd.to_datetime(df['timestamp'])
                else:
                    df['_datetime'] = pd.to_datetime(df['timestamp'])
                
                df['hour'] = df['_datetime'].dt.hour
                df['day_of_week'] = df['_datetime'].dt.dayofweek
                df.drop('_datetime', axis=1, inplace=True)
            except Exception as e:
                if self.verbose:
                    logging.warning(f"Could not parse timestamp: {e}. Using index-based features.")
                df['hour'] = (df.index % 24).astype(int)
                df['day_of_week'] = ((df.index // 24) % 5).astype(int)
        else:
            # Create synthetic hour/day based on index
            df['hour'] = (df.index % 24).astype(int)
            df['day_of_week'] = ((df.index // 24) % 5).astype(int)
        
        # Session flags (assuming UTC - adjust offsets for your broker)
        df['is_asian_session'] = ((df['hour'] >= 0) & (df['hour'] < 8)).astype(int)
        df['is_london_session'] = ((df['hour'] >= 8) & (df['hour'] < 16)).astype(int)
        df['is_ny_session'] = ((df['hour'] >= 13) & (df['hour'] < 21)).astype(int)
        df['is_overlap_session'] = ((df['hour'] >= 13) & (df['hour'] < 16)).astype(int)
        
        # Session volatility (overlap typically highest)
        df['session_volatility_weight'] = np.where(
            df['is_overlap_session'] == 1, 1.0,
            np.where(df['is_london_session'] == 1, 0.8,
            np.where(df['is_ny_session'] == 1, 0.7,
            0.4))  # Asian session lowest
        )
        
        # Early/late session
        df['is_session_start'] = ((df['hour'] == 8) | (df['hour'] == 13)).astype(int)
        df['is_session_end'] = ((df['hour'] == 15) | (df['hour'] == 20)).astype(int)
        
        # Day of week features
        df['is_monday'] = (df['day_of_week'] == 0).astype(int)
        df['is_friday'] = (df['day_of_week'] == 4).astype(int)
        df['is_midweek'] = ((df['day_of_week'] >= 1) & (df['day_of_week'] <= 3)).astype(int)
        
        return df
    
    # =========================================================================
    # NEW V4.0: TIME FEATURES (CYCLICAL ENCODING)
    # =========================================================================
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add cyclical time features using sin/cos encoding.
        
        This preserves the cyclical nature of time (23:00 is close to 00:00).
        """
        # Hour sin/cos encoding (24-hour cycle)
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        
        # Day of week sin/cos encoding (5-day cycle for forex)
        df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 5)
        df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 5)
        
        return df
    
    # =========================================================================
    # NEW V4.0: REGIME FEATURES
    # =========================================================================
    
    def _add_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add market regime classification features.
        
        Regimes:
        - Trending: Strong directional movement (high ADX-like measure)
        - Ranging: Low volatility, price oscillating
        - Volatile: High volatility, no clear direction
        """
        window = self.WINDOW_LONG
        
        # Calculate ADX-like trend strength
        # True Range
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Directional movement
        up_move = df['high'] - df['high'].shift(1)
        down_move = df['low'].shift(1) - df['low']
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smooth with EMA
        atr_14 = pd.Series(tr).ewm(span=14, adjust=False).mean()
        plus_di = 100 * pd.Series(plus_dm).ewm(span=14, adjust=False).mean() / atr_14.replace(0, np.nan)
        minus_di = 100 * pd.Series(minus_dm).ewm(span=14, adjust=False).mean() / atr_14.replace(0, np.nan)
        
        # ADX calculation
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        df['adx'] = dx.ewm(span=14, adjust=False).mean().fillna(0)
        
        # Trend direction
        df['plus_di'] = plus_di.fillna(0)
        df['minus_di'] = minus_di.fillna(0)
        df['trend_direction'] = np.sign(df['plus_di'] - df['minus_di'])
        
        # Regime classification
        # Trending: ADX > 25
        df['is_trending'] = (df['adx'] > 25).astype(int)
        
        # Ranging: ADX < 20 and low ATR
        atr_percentile = df['atr_pct'].rolling(100, min_periods=20).apply(
            lambda x: scipy_stats.percentileofscore(x, x.iloc[-1]) / 100 if len(x) >= 20 else 0.5,
            raw=False
        ).fillna(0.5)
        df['atr_percentile'] = atr_percentile
        df['is_ranging'] = ((df['adx'] < 20) & (atr_percentile < 0.5)).astype(int)
        
        # Volatile: High ATR percentile
        df['is_volatile'] = (atr_percentile > 0.7).astype(int)
        
        # Regime score (continuous)
        df['regime_trend_score'] = (df['adx'] / 50).clip(0, 1)  # 0 = ranging, 1 = strong trend
        df['regime_volatility_score'] = atr_percentile
        
        # Trending UP specifically (for SHORT - want to fade uptrends)
        df['is_trending_up'] = ((df['is_trending'] == 1) & (df['trend_direction'] > 0)).astype(int)
        df['is_trending_down'] = ((df['is_trending'] == 1) & (df['trend_direction'] < 0)).astype(int)
        
        return df
    
    # =========================================================================
    # NEW V4.0: MEAN REVERSION FEATURES
    # =========================================================================
    
    def _add_mean_reversion_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add mean reversion features.
        
        These measure how far price has deviated from "normal" levels.
        High values suggest potential reversion.
        """
        # Moving averages
        df['ma_10'] = df['close'].rolling(10, min_periods=5).mean()
        df['ma_20'] = df['close'].rolling(20, min_periods=10).mean()
        df['ma_50'] = df['close'].rolling(50, min_periods=25).mean()
        
        # Distance from MAs (normalized)
        df['dist_from_ma10'] = (df['close'] - df['ma_10']) / df['ma_10'].replace(0, np.nan)
        df['dist_from_ma20'] = (df['close'] - df['ma_20']) / df['ma_20'].replace(0, np.nan)
        df['dist_from_ma50'] = (df['close'] - df['ma_50']) / df['ma_50'].replace(0, np.nan)
        
        # Overextension score (how far above MA)
        df['overextension_10'] = df['dist_from_ma10'].clip(0, None)
        df['overextension_20'] = df['dist_from_ma20'].clip(0, None)
        
        # MA slope (trend direction)
        df['ma20_slope'] = (df['ma_20'] - df['ma_20'].shift(5)) / df['ma_20'].shift(5).replace(0, np.nan)
        df['ma50_slope'] = (df['ma_50'] - df['ma_50'].shift(10)) / df['ma_50'].shift(10).replace(0, np.nan)
        
        # Price above MA flags
        df['price_above_ma10'] = (df['close'] > df['ma_10']).astype(int)
        df['price_above_ma20'] = (df['close'] > df['ma_20']).astype(int)
        df['price_above_ma50'] = (df['close'] > df['ma_50']).astype(int)
        
        # All MAs aligned bullish (setup for SHORT)
        df['all_ma_bullish'] = (
            (df['price_above_ma10'] == 1) &
            (df['price_above_ma20'] == 1) &
            (df['price_above_ma50'] == 1)
        ).astype(int)
        
        # Extreme overextension (potential reversion)
        df['extreme_overextension'] = (
            (df['dist_from_ma20'] > df['dist_from_ma20'].rolling(50, min_periods=20).quantile(0.95))
        ).fillna(0).astype(int)
        
        # Mean reversion probability score
        df['mean_reversion_score'] = (
            0.3 * df['overextension_20'].clip(0, 0.05) / 0.05 +
            0.3 * (df['price_zscore'].clip(0, 3) / 3) +
            0.2 * df['rsi_overbought'] +
            0.2 * (df['bb_position'].clip(0.8, 1) - 0.8) / 0.2
        ).clip(0, 1)
        
        # Drop intermediate columns
        df.drop(['ma_10', 'ma_20', 'ma_50'], axis=1, inplace=True)
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW V4.0: ADVANCED VOLATILITY FEATURES
    # =========================================================================
    
    def _add_advanced_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add advanced volatility features.
        
        These help identify volatility regimes and potential breakouts.
        """
        # ATR percentile (already calculated in regime features, but add more)
        window = self.WINDOW_VOLATILITY
        
        # Range percentile
        df['range_percentile'] = df['range_pct'].rolling(window, min_periods=20).apply(
            lambda x: scipy_stats.percentileofscore(x, x.iloc[-1]) / 100 if len(x) >= 20 else 0.5,
            raw=False
        ).fillna(0.5)
        
        # Volatility contraction (potential breakout)
        df['volatility_contraction'] = (
            (df['atr_percentile'] < 0.3) &
            (df['bb_squeeze_pct'] < 0.3)
        ).astype(int)
        
        # Volatility expansion
        df['volatility_expansion'] = (
            (df['atr_percentile'] > 0.7) &
            (df['atr_percentile'] > df['atr_percentile'].shift(1))
        ).astype(int)
        
        # Historical volatility (20-period standard deviation)
        returns = df['close'].pct_change()
        df['historical_vol'] = returns.rolling(20, min_periods=10).std() * np.sqrt(252)  # Annualized
        
        # Volatility ratio (current vs historical)
        vol_mean = df['historical_vol'].rolling(50, min_periods=20).mean()
        df['volatility_ratio'] = df['historical_vol'] / vol_mean.replace(0, np.nan)
        
        # Intrabar volatility (range / close)
        df['intrabar_vol'] = df['range_pct']
        df['intrabar_vol_percentile'] = df['range_percentile']
        
        # Volatility clustering (high vol tends to follow high vol)
        df['vol_cluster'] = df['historical_vol'].rolling(5, min_periods=3).mean() / \
                           df['historical_vol'].rolling(20, min_periods=10).mean().replace(0, np.nan)
        
        return df.fillna(0)
    
    # =========================================================================
    # NEW V4.0: MACD FEATURES
    # =========================================================================
    
    def _add_macd_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add MACD-based features.
        
        MACD = EMA(12) - EMA(26)
        Signal = EMA(9) of MACD
        Histogram = MACD - Signal
        """
        # Calculate MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        
        df['macd_line'] = ema_12 - ema_26
        df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd_line'] - df['macd_signal']
        
        # Normalized MACD (percentage of price)
        df['macd_normalized'] = df['macd_line'] / df['close'].replace(0, np.nan) * 100
        df['macd_hist_normalized'] = df['macd_histogram'] / df['close'].replace(0, np.nan) * 100
        
        # MACD crossovers
        df['macd_cross_down'] = (
            (df['macd_line'] < df['macd_signal']) &
            (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))
        ).astype(int)
        
        df['macd_cross_up'] = (
            (df['macd_line'] > df['macd_signal']) &
            (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
        ).astype(int)
        
        # MACD above/below zero
        df['macd_above_zero'] = (df['macd_line'] > 0).astype(int)
        df['macd_below_zero'] = (df['macd_line'] < 0).astype(int)
        
        # Histogram direction
        df['macd_hist_rising'] = (df['macd_histogram'] > df['macd_histogram'].shift(1)).astype(int)
        df['macd_hist_falling'] = (df['macd_histogram'] < df['macd_histogram'].shift(1)).astype(int)
        
        # MACD divergence with price (bearish for SHORT)
        price_higher = df['high'] > df['high'].shift(10)
        macd_lower = df['macd_line'] < df['macd_line'].shift(10)
        df['macd_bearish_div'] = (price_higher & macd_lower).astype(int)
        
        # MACD momentum (slope)
        df['macd_slope'] = (df['macd_line'] - df['macd_line'].shift(3)) / 3
        df['macd_hist_slope'] = (df['macd_histogram'] - df['macd_histogram'].shift(3)) / 3
        
        return df.fillna(0)
    
    # =========================================================================
    # QUALITY FEATURES
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
        
        # First touch (vs repeated)
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
        
        # Statistical extremes score
        stat_score = (
            0.3 * (df['price_zscore'].fillna(0) > 2).astype(int) +
            0.3 * (df['rsi_zscore'].fillna(0) > 1.5).astype(int) +
            0.4 * (df['price_percentile'].fillna(0) > 0.9).astype(int)
        ).clip(0, 1)
        
        # NEW: Regime score (trending up = good for SHORT fade)
        regime_score = (
            0.5 * df['is_trending_up'] +
            0.5 * df['mean_reversion_score']
        ).clip(0, 1)
        
        # Composite exhaustion score
        df['exhaustion_score'] = (
            0.15 * bb_score +
            0.15 * rsi_score +
            0.15 * momentum_score +
            0.15 * pattern_score +
            0.10 * volume_score +
            0.15 * stat_score +
            0.15 * regime_score
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
                'bb_position_percentile', 'high_percentile', 'atr_percentile',
                'range_percentile'
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
                'bb_overextended', 'bb_squeeze_pct'
            ],
            'volume_patterns': [
                'volume_climax_top', 'volume_decline_3', 'volume_spike_rejection',
                'volume_trend', 'obv_direction', 'obv_divergence'
            ],
            'session': [
                'hour', 'day_of_week',
                'is_asian_session', 'is_london_session', 'is_ny_session', 'is_overlap_session',
                'session_volatility_weight', 'is_session_start', 'is_session_end',
                'is_monday', 'is_friday', 'is_midweek',
                'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos'
            ],
            'regime': [
                'adx', 'plus_di', 'minus_di', 'trend_direction',
                'is_trending', 'is_ranging', 'is_volatile',
                'regime_trend_score', 'regime_volatility_score',
                'is_trending_up', 'is_trending_down'
            ],
            'mean_reversion': [
                'dist_from_ma10', 'dist_from_ma20', 'dist_from_ma50',
                'overextension_10', 'overextension_20',
                'ma20_slope', 'ma50_slope',
                'price_above_ma10', 'price_above_ma20', 'price_above_ma50',
                'all_ma_bullish', 'extreme_overextension', 'mean_reversion_score'
            ],
            'volatility': [
                'volatility_contraction', 'volatility_expansion',
                'historical_vol', 'volatility_ratio',
                'intrabar_vol', 'intrabar_vol_percentile', 'vol_cluster'
            ],
            'macd': [
                'macd_line', 'macd_signal', 'macd_histogram',
                'macd_normalized', 'macd_hist_normalized',
                'macd_cross_down', 'macd_cross_up',
                'macd_above_zero', 'macd_below_zero',
                'macd_hist_rising', 'macd_hist_falling',
                'macd_bearish_div', 'macd_slope', 'macd_hist_slope'
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
    random_state: int = 42,
    step: int = 1
) -> RFEResult:
    """
    Perform Recursive Feature Elimination to select optimal features.
    
    OPTIMIZED: Uses LightGBM instead of GradientBoosting (5-10x faster).
    """
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
    
    # Use LightGBM for faster RFE
    try:
        import lightgbm as lgb
        estimator = lgb.LGBMClassifier(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.1,
            min_child_samples=20,
            random_state=random_state,
            verbose=-1,
            n_jobs=1,
            device='cpu',
            force_col_wise=True
        )
    except ImportError:
        estimator = GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            min_samples_leaf=20,
            random_state=random_state,
            validation_fraction=0.1,
            n_iter_no_change=5
        )
    
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=ConvergenceWarning)
        warnings.filterwarnings('ignore', category=UserWarning)
        warnings.filterwarnings('ignore')
        
        if use_rfecv:
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
            
            selector = RFECV(
                estimator=estimator,
                step=step,
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
                step=step
            )
            
            selector.fit(X, y)
            optimal_n = n_features_to_select
            cv_scores = None
    
    if optimal_n > max_features:
        selector = RFE(
            estimator=estimator,
            n_features_to_select=max_features,
            step=step
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
