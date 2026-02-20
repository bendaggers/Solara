"""
FeatureCalculator - Unified feature calculation for Solara Trading System.

This class calculates features using the EXACT same formulas as:
1. MarketDataExporter.mq5 (for base features from CSV)
2. features.py FeatureEngineering class (for derived features)

CRITICAL: Feature calculations must match training EXACTLY or model predictions
will be meaningless. This class ensures consistency between training and inference.

Usage:
    calculator = FeatureCalculator()
    
    # From raw OHLCV data (calculates everything)
    df_features = calculator.calculate_from_ohlcv(df_ohlcv)
    
    # From MarketDataExporter CSV (already has base features)
    df_features = calculator.calculate_from_ea_csv(df_ea)
    
    # Get only the 7 model features
    model_features = calculator.get_model_features(df_features)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import warnings


@dataclass
class FeatureConfig:
    """Configuration for feature calculation - matches MarketDataExporter.mq5"""
    # Bollinger Bands
    bb_period: int = 20
    bb_deviation: float = 2.0
    
    # RSI
    rsi_period: int = 14
    
    # ATR
    atr_period: int = 14
    
    # Trend (SMA)
    sma_short: int = 50
    sma_long: int = 200
    
    # Volume
    volume_sma_period: int = 20
    
    # Touch lookback
    touch_lookback: int = 20
    
    # Support/Resistance
    support_lookback: int = 20


class FeatureCalculator:
    """
    Calculates all features needed for the Solara ML model.
    
    Formulas are copied EXACTLY from:
    - MarketDataExporter.mq5 for base indicators
    - features.py for derived features
    
    The 7 selected model features are:
    1. bb_width_pct       - Bollinger Band width as % of middle band
    2. trend_strength     - (SMA50 - SMA200) / close * 100
    3. time_since_last_touch - Bars since price touched UPPER BB
    4. rsi_value          - Standard RSI(14)
    5. volume_ratio       - Volume / SMA(Volume, 20)
    6. atr_pct            - ATR / close * 100
    7. support_distance_pct - (close - recent_low) / close
    """
    
    # The 7 features selected by RFE during training
    MODEL_FEATURES = [
        'bb_width_pct',
        'trend_strength', 
        'time_since_last_touch',
        'rsi_value',
        'volume_ratio',
        'atr_pct',
        'support_distance_pct'
    ]
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize calculator with configuration.
        
        Args:
            config: Feature calculation parameters (defaults match MarketDataExporter.mq5)
        """
        self.config = config or FeatureConfig()
    
    # =========================================================================
    # MAIN ENTRY POINTS
    # =========================================================================
    
    def calculate_from_ohlcv(
        self,
        df: pd.DataFrame,
        include_all_features: bool = False
    ) -> pd.DataFrame:
        """
        Calculate all features from raw OHLCV data.
        
        Use this when you have raw price data and need to calculate everything.
        
        Args:
            df: DataFrame with columns: open, high, low, close, volume
            include_all_features: If True, calculate all 50+ features; else just model features
            
        Returns:
            DataFrame with calculated features
        """
        df = df.copy()
        
        # Ensure column names are lowercase
        df.columns = df.columns.str.lower()
        
        # Validate required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # Step 1: Calculate base indicators (what MarketDataExporter.mq5 does)
        df = self._calculate_bollinger_bands(df)
        df = self._calculate_rsi(df)
        df = self._calculate_atr(df)
        df = self._calculate_sma_trend(df)
        df = self._calculate_volume_features(df)
        
        # Step 2: Calculate derived features (from base indicators)
        df = self._calculate_bb_features(df)
        df = self._calculate_touch_features(df)
        df = self._calculate_support_distance(df)
        
        # Step 3: Calculate additional features if requested
        if include_all_features:
            df = self._calculate_all_derived_features(df)
        
        return df
    
    def calculate_from_ea_csv(
        self,
        df: pd.DataFrame,
        fix_support_distance: bool = True
    ) -> pd.DataFrame:
        """
        Calculate features from MarketDataExporter CSV output.
        
        The EA CSV already has most features, but:
        - support_distance_pct is always 0 (bug in EA)
        - time_since_last_touch checks LOWER band (we need UPPER for SHORT)
        
        Args:
            df: DataFrame from MarketDataExporter CSV
            fix_support_distance: Recalculate support_distance_pct (recommended)
            
        Returns:
            DataFrame with corrected features
        """
        df = df.copy()
        
        # Ensure column names are lowercase
        df.columns = df.columns.str.lower()
        
        # Fix support_distance_pct (EA always sets to 0)
        if fix_support_distance and 'close' in df.columns and 'low' in df.columns:
            df = self._calculate_support_distance(df)
        
        # Fix time_since_last_touch for SHORT strategy (check UPPER band, not lower)
        if 'high' in df.columns and 'upper_band' in df.columns:
            df = self._calculate_time_since_upper_touch(df)
        
        return df
    
    def get_model_features(
        self,
        df: pd.DataFrame,
        validate: bool = True
    ) -> pd.DataFrame:
        """
        Extract only the 7 features needed by the model.
        
        Args:
            df: DataFrame with all calculated features
            validate: Check for NaN/Inf values
            
        Returns:
            DataFrame with only MODEL_FEATURES columns
        """
        # Check all required features exist
        missing = [f for f in self.MODEL_FEATURES if f not in df.columns]
        if missing:
            raise ValueError(f"Missing model features: {missing}")
        
        result = df[self.MODEL_FEATURES].copy()
        
        if validate:
            # Check for NaN
            nan_counts = result.isna().sum()
            if nan_counts.any():
                warnings.warn(f"NaN values found in features:\n{nan_counts[nan_counts > 0]}")
            
            # Check for Inf
            inf_counts = np.isinf(result.select_dtypes(include=[np.number])).sum()
            if inf_counts.any():
                warnings.warn(f"Infinite values found in features:\n{inf_counts[inf_counts > 0]}")
        
        return result
    
    def get_feature_array(
        self,
        df: pd.DataFrame,
        row_index: int = -1
    ) -> np.ndarray:
        """
        Get feature values as numpy array for ONNX inference.
        
        Args:
            df: DataFrame with features
            row_index: Which row to get (-1 for last row)
            
        Returns:
            numpy array of shape (1, 7) with float32 values
        """
        features_df = self.get_model_features(df, validate=False)
        
        if row_index == -1:
            row = features_df.iloc[-1]
        else:
            row = features_df.iloc[row_index]
        
        # Convert to float32 array (ONNX requires float32)
        values = row.values.astype(np.float32)
        
        # Replace NaN/Inf with 0
        values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
        
        return values.reshape(1, -1)
    
    # =========================================================================
    # BOLLINGER BANDS (from MarketDataExporter.mq5)
    # =========================================================================
    
    def _calculate_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Bollinger Bands.
        
        Formula (from MarketDataExporter.mq5 lines 380-395):
            middle = SMA(close, 20)
            std = StdDev(close, 20)
            upper = middle + 2 * std
            lower = middle - 2 * std
        """
        period = self.config.bb_period
        deviation = self.config.bb_deviation
        
        # Middle band = SMA
        df['middle_band'] = df['close'].rolling(window=period).mean()
        
        # Standard deviation
        rolling_std = df['close'].rolling(window=period).std()
        
        # Upper and lower bands
        df['upper_band'] = df['middle_band'] + (deviation * rolling_std)
        df['lower_band'] = df['middle_band'] - (deviation * rolling_std)
        
        return df
    
    def _calculate_bb_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate BB-derived features.
        
        bb_position (from MarketDataExporter.mq5 line 458):
            bb_position = (close - lower) / (upper - lower)
            Range: 0.0 (at lower) to 1.0 (at upper)
        
        bb_width_pct (from MarketDataExporter.mq5 line 459):
            bb_width_pct = ((upper - lower) / middle) * 100
        """
        # BB Position (0-1 scale)
        bb_range = df['upper_band'] - df['lower_band']
        df['bb_position'] = np.where(
            bb_range != 0,
            (df['close'] - df['lower_band']) / bb_range,
            0.5
        )
        # Clip to valid range
        df['bb_position'] = df['bb_position'].clip(0, 1)
        
        # BB Width as percentage of middle band
        df['bb_width_pct'] = np.where(
            df['middle_band'] != 0,
            ((df['upper_band'] - df['lower_band']) / df['middle_band']) * 100,
            0
        )
        
        return df
    
    # =========================================================================
    # RSI (from MarketDataExporter.mq5)
    # =========================================================================
    
    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate RSI using Wilder's smoothing method.
        
        Formula (from MarketDataExporter.mq5 lines 397-418):
            change = close[i] - close[i-1]
            gain = change if change > 0 else 0
            loss = -change if change < 0 else 0
            
            Initial:
                avg_gain = sum(gains[:period]) / period
                avg_loss = sum(losses[:period]) / period
            
            Subsequent (Wilder smoothing):
                avg_gain = (avg_gain * (period-1) + gain) / period
                avg_loss = (avg_loss * (period-1) + loss) / period
            
            RS = avg_gain / avg_loss
            RSI = 100 - (100 / (1 + RS))
        """
        period = self.config.rsi_period
        
        # Price changes
        delta = df['close'].diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = (-delta).where(delta < 0, 0.0)
        
        # First average (simple average for first 'period' values)
        first_avg_gain = gains.iloc[:period].mean()
        first_avg_loss = losses.iloc[:period].mean()
        
        # Initialize arrays
        avg_gains = np.zeros(len(df))
        avg_losses = np.zeros(len(df))
        
        # Set initial values
        avg_gains[period - 1] = first_avg_gain
        avg_losses[period - 1] = first_avg_loss
        
        # Wilder's smoothing for subsequent values
        for i in range(period, len(df)):
            avg_gains[i] = (avg_gains[i-1] * (period - 1) + gains.iloc[i]) / period
            avg_losses[i] = (avg_losses[i-1] * (period - 1) + losses.iloc[i]) / period
        
        # Calculate RS and RSI
        rs = np.where(avg_losses != 0, avg_gains / avg_losses, 100)
        rsi = 100 - (100 / (1 + rs))
        
        # Handle edge cases
        rsi = np.where(avg_losses == 0, 100, rsi)
        
        df['rsi_value'] = rsi
        
        # Fill initial NaN values
        df['rsi_value'] = df['rsi_value'].fillna(50)
        
        return df
    
    # =========================================================================
    # ATR (from MarketDataExporter.mq5)
    # =========================================================================
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Average True Range.
        
        Formula (from MarketDataExporter.mq5 lines 433-449):
            TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
            ATR = Wilder's smoothed average of TR
        
        atr_pct (from MarketDataExporter.mq5 line 479):
            atr_pct = (ATR / close) * 100
        """
        period = self.config.atr_period
        
        # True Range components
        high_low = df['high'] - df['low']
        high_close_prev = (df['high'] - df['close'].shift(1)).abs()
        low_close_prev = (df['low'] - df['close'].shift(1)).abs()
        
        # True Range = max of all three
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        
        # Wilder's smoothed ATR
        atr = np.zeros(len(df))
        atr[0] = tr.iloc[0]
        
        for i in range(1, len(df)):
            if i < period:
                # Simple average for initial values
                atr[i] = (atr[i-1] * i + tr.iloc[i]) / (i + 1)
            else:
                # Wilder's smoothing
                atr[i] = (atr[i-1] * (period - 1) + tr.iloc[i]) / period
        
        df['atr'] = atr
        
        # ATR as percentage of close price
        df['atr_pct'] = np.where(
            df['close'] != 0,
            (df['atr'] / df['close']) * 100,
            0
        )
        
        return df
    
    # =========================================================================
    # TREND STRENGTH (from MarketDataExporter.mq5)
    # =========================================================================
    
    def _calculate_sma_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate trend strength from SMA crossover.
        
        Formula (from MarketDataExporter.mq5 lines 419-432, 480):
            sma_short = SMA(close, 50)
            sma_long = SMA(close, 200)
            trend_strength = ((sma_short - sma_long) / close) * 100
        
        Positive = bullish trend
        Negative = bearish trend
        """
        # Calculate SMAs
        df['sma_short'] = df['close'].rolling(window=self.config.sma_short).mean()
        df['sma_long'] = df['close'].rolling(window=self.config.sma_long).mean()
        
        # Trend strength as percentage
        df['trend_strength'] = np.where(
            df['close'] != 0,
            ((df['sma_short'] - df['sma_long']) / df['close']) * 100,
            0
        )
        
        # Fill NaN (from initial period)
        df['trend_strength'] = df['trend_strength'].fillna(0)
        
        return df
    
    # =========================================================================
    # VOLUME FEATURES (from MarketDataExporter.mq5)
    # =========================================================================
    
    def _calculate_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate volume ratio.
        
        Formula (from MarketDataExporter.mq5 lines 420-426, 471):
            volume_sma = SMA(volume, 20)
            volume_ratio = volume / volume_sma
        
        > 1.0 = above average volume
        < 1.0 = below average volume
        """
        period = self.config.volume_sma_period
        
        # Volume SMA
        volume_sma = df['volume'].rolling(window=period).mean()
        
        # Volume ratio
        df['volume_ratio'] = np.where(
            volume_sma != 0,
            df['volume'] / volume_sma,
            1.0
        )
        
        # Fill NaN
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
        
        return df
    
    # =========================================================================
    # TOUCH FEATURES (FIXED for SHORT strategy)
    # =========================================================================
    
    def _calculate_touch_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate time since last touch of UPPER Bollinger Band.
        
        IMPORTANT: For SHORT strategy, we care about UPPER band touches!
        The original EA checks LOWER band - this is WRONG for shorts.
        
        Formula:
            touched_upper = high >= upper_band
            time_since_last_touch = bars since last touched_upper == True
        """
        # Check if high touched or exceeded upper band
        df['touched_upper_bb'] = (df['high'] >= df['upper_band']).astype(int)
        
        # Calculate time since last touch
        time_since = np.zeros(len(df))
        last_touch_idx = -1
        
        for i in range(len(df)):
            if df['touched_upper_bb'].iloc[i] == 1:
                time_since[i] = 0
                last_touch_idx = i
            elif last_touch_idx >= 0:
                time_since[i] = i - last_touch_idx
            else:
                time_since[i] = 999  # No previous touch
        
        df['time_since_last_touch'] = time_since
        
        # Cap at reasonable value
        df['time_since_last_touch'] = df['time_since_last_touch'].clip(upper=100)
        
        # Previous touches in lookback period
        lookback = self.config.touch_lookback
        df['previous_touches'] = df['touched_upper_bb'].rolling(window=lookback).sum()
        df['previous_touches'] = df['previous_touches'].fillna(0).astype(int)
        
        return df
    
    def _calculate_time_since_upper_touch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recalculate time_since_last_touch for UPPER band.
        
        Use this to fix the EA's incorrect calculation.
        """
        return self._calculate_touch_features(df)
    
    # =========================================================================
    # SUPPORT DISTANCE (FIXED - EA always returns 0)
    # =========================================================================
    
    def _calculate_support_distance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate distance from recent support (lowest low).
        
        Formula (should have been in MarketDataExporter.mq5 but always 0):
            recent_low = min(low[-20:])  # Lowest low in last 20 bars
            support_distance_pct = (close - recent_low) / close
        
        Higher value = price is further from support (more room to fall)
        Lower value = price is near support (less room to fall)
        """
        lookback = self.config.support_lookback
        
        # Rolling minimum of low prices
        recent_low = df['low'].rolling(window=lookback).min()
        
        # Distance from support as percentage of close
        df['support_distance_pct'] = np.where(
            df['close'] != 0,
            (df['close'] - recent_low) / df['close'],
            0
        )
        
        # Fill NaN from initial period
        df['support_distance_pct'] = df['support_distance_pct'].fillna(0)
        
        return df
    
    # =========================================================================
    # ALL DERIVED FEATURES (from features.py)
    # =========================================================================
    
    def _calculate_all_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all additional features from features.py.
        
        These are used during training but may not be selected by RFE.
        """
        # Binary features
        df['rsi_overbought'] = (df['rsi_value'] > 70).astype(int)
        df['rsi_extreme_overbought'] = (df['rsi_value'] > 80).astype(int)
        df['bearish_candle'] = (df['close'] < df['open']).astype(int)
        
        # Candle features
        df['upper_wick'] = np.where(
            df['open'] != 0,
            (df['high'] - df[['open', 'close']].max(axis=1)) / df['open'],
            0
        )
        df['lower_wick'] = np.where(
            df['open'] != 0,
            (df[['open', 'close']].min(axis=1) - df['low']) / df['open'],
            0
        )
        
        # Price change features
        df['price_change_1'] = df['close'].pct_change(1)
        df['price_change_5'] = df['close'].pct_change(5)
        
        # Lag features
        for i in range(1, 6):
            df[f'rsi_lag{i}'] = df['rsi_value'].shift(i)
        
        for i in range(1, 4):
            df[f'bb_position_lag{i}'] = df['bb_position'].shift(i)
            df[f'volume_ratio_lag{i}'] = df['volume_ratio'].shift(i)
        
        # Slope features
        df['rsi_slope_3'] = (df['rsi_value'] - df['rsi_value'].shift(3)) / 3
        df['rsi_slope_5'] = (df['rsi_value'] - df['rsi_value'].shift(5)) / 5
        df['bb_position_slope_3'] = (df['bb_position'] - df['bb_position'].shift(3)) / 3
        
        # Quality features
        df['rsi_peaked'] = (df['rsi_value'] < df['rsi_value'].shift(1)).astype(int)
        df['bb_very_high'] = (df['bb_position'] > 0.95).astype(int)
        df['volume_spike'] = (df['volume_ratio'] > 1.3).astype(int)
        df['rejection_candle'] = (df['upper_wick'] > 0.003).astype(int)
        
        return df
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    def validate_features(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Validate calculated features.
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'issues': [],
            'feature_stats': {}
        }
        
        for feat in self.MODEL_FEATURES:
            if feat not in df.columns:
                results['valid'] = False
                results['issues'].append(f"Missing feature: {feat}")
                continue
            
            series = df[feat]
            stats = {
                'min': float(series.min()),
                'max': float(series.max()),
                'mean': float(series.mean()),
                'nan_count': int(series.isna().sum()),
                'inf_count': int(np.isinf(series).sum())
            }
            results['feature_stats'][feat] = stats
            
            if stats['nan_count'] > 0:
                results['issues'].append(f"{feat}: {stats['nan_count']} NaN values")
            if stats['inf_count'] > 0:
                results['valid'] = False
                results['issues'].append(f"{feat}: {stats['inf_count']} Inf values")
        
        return results
    
    def print_feature_summary(self, df: pd.DataFrame):
        """Print summary of calculated features."""
        print("\n" + "="*60)
        print("FEATURE SUMMARY")
        print("="*60)
        
        for feat in self.MODEL_FEATURES:
            if feat in df.columns:
                series = df[feat]
                print(f"\n{feat}:")
                print(f"  Range: {series.min():.4f} to {series.max():.4f}")
                print(f"  Mean:  {series.mean():.4f}")
                print(f"  NaN:   {series.isna().sum()}")
            else:
                print(f"\n{feat}: MISSING!")
        
        print("\n" + "="*60)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def calculate_features_for_model(
    df: pd.DataFrame,
    from_ea_csv: bool = False
) -> pd.DataFrame:
    """
    Quick function to calculate features for model inference.
    
    Args:
        df: Input DataFrame (OHLCV or EA CSV)
        from_ea_csv: True if input is from MarketDataExporter
        
    Returns:
        DataFrame with model features
    """
    calculator = FeatureCalculator()
    
    if from_ea_csv:
        df = calculator.calculate_from_ea_csv(df)
    else:
        df = calculator.calculate_from_ohlcv(df)
    
    return calculator.get_model_features(df)


def get_feature_vector(
    df: pd.DataFrame,
    row_index: int = -1,
    from_ea_csv: bool = False
) -> np.ndarray:
    """
    Get single feature vector for ONNX inference.
    
    Args:
        df: Input DataFrame
        row_index: Which row (-1 for last)
        from_ea_csv: True if input is from MarketDataExporter
        
    Returns:
        numpy array of shape (1, 7) with float32 values
    """
    calculator = FeatureCalculator()
    
    if from_ea_csv:
        df = calculator.calculate_from_ea_csv(df)
    else:
        df = calculator.calculate_from_ohlcv(df)
    
    return calculator.get_feature_array(df, row_index)


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Test with sample data
    print("Testing FeatureCalculator...")
    
    # Create sample OHLCV data
    np.random.seed(42)
    n = 250  # Need at least 200 for SMA_long
    
    # Simulate price movement
    price_changes = np.random.randn(n) * 0.001
    close = 1.1000 + np.cumsum(price_changes)
    
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='4H'),
        'open': close + np.random.randn(n) * 0.0005,
        'high': close + np.abs(np.random.randn(n) * 0.001),
        'low': close - np.abs(np.random.randn(n) * 0.001),
        'close': close,
        'volume': np.random.randint(1000, 10000, n)
    })
    
    # Calculate features
    calculator = FeatureCalculator()
    df_features = calculator.calculate_from_ohlcv(df)
    
    # Print summary
    calculator.print_feature_summary(df_features)
    
    # Validate
    validation = calculator.validate_features(df_features)
    print(f"\nValidation: {'✅ PASSED' if validation['valid'] else '❌ FAILED'}")
    if validation['issues']:
        for issue in validation['issues']:
            print(f"  - {issue}")
    
    # Get feature vector for last row
    features = calculator.get_feature_array(df_features)
    print(f"\nFeature vector shape: {features.shape}")
    print(f"Feature values: {features}")
    
    print("\n✅ FeatureCalculator test complete!")