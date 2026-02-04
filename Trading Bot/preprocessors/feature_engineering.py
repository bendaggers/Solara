"""
FeatureEngineer (PRD) - Compatible with UniversalPreprocessor
Based on BollingerBandsFeatureEngineer training logic
"""

import pandas as pd
import numpy as np
from typing import List, Optional
import warnings
warnings.filterwarnings('ignore')

class FeatureEngineer:
    """
    Feature engineering for Bollinger Bands Reversal Short model
    Compatible with UniversalPreprocessor
    """
    
    def __init__(self, lags: Optional[List[int]] = None):
        """
        Initialize feature engineer
        
        Args:
            lags: List of lag periods (e.g., [1, 2, 3])
        """

        
        self.lags = lags or [1, 2, 3]
        
        # The 13 features required by the model
        self.required_model_features = [
            "candle_body_pct",
            "ret_lag1",
            "rsi_slope_lag2", 
            "ret",
            "body_size",
            "RSI_slope_3",
            "rsi_slope_lag3",
            "ret_lag2",
            "price_momentum",
            "rsi_slope",
            "dist_bb_upper_lag3",
            "rsi_slope_lag1",
            "rsi_value"
        ]
    
    def create_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create all features from raw data
        
        Args:
            df: DataFrame with raw OHLCV + indicators
            
        Returns:
            DataFrame with all features created
        """
        # Make a copy to avoid modifying original
        df_features = df.copy()
        
        # Step 1: Create base features needed for lagging
        df_features = self._create_base_features(df_features)
        
        # Step 2: Create lagged features
        df_features = self._create_lagged_features(df_features)
        
        # Step 3: Create derived features
        df_features = self._create_derived_features(df_features)
        
        # Step 4: Ensure required features exist
        df_features = self._ensure_required_features(df_features)
        
        # Step 5: Clean up - drop NaN rows from lagging
        df_features = df_features.dropna()
        
        return df_features


    def _create_base_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create base features from raw data
        ONLY create features that don't already exist in the input
        """
        df = df.copy()
        
        # List of features that might already exist in input
        existing_features_in_input = [
            'candle_body_pct', 'price_momentum', 'rsi_value',
            'ret', 'dist_bb_upper', 'body_size'
        ]
        
        # Track what we're creating
        created_features = []
        
        # 1. Returns (percentage change) - Required: 'ret'
        if 'ret' not in df.columns:
            df['ret'] = df['close'].pct_change()
            created_features.append('ret')
        
        # 2. Bollinger Band features - Required: 'dist_bb_upper'
        if 'dist_bb_upper' not in df.columns:
            df['dist_bb_upper'] = df['upper_band'] - df['close']
            created_features.append('dist_bb_upper')
        
        # 3. RSI features - 'rsi_value' comes from input, 'rsi_slope' we calculate
        # Don't touch rsi_value - it's already in input
        if 'rsi_slope' not in df.columns:
            df['rsi_slope'] = df['rsi_value'].diff()
            created_features.append('rsi_slope')
        
        # 4. Candle shape features
        # body_size - only calculate if not exists
        if 'body_size' not in df.columns:
            df['body_size'] = abs(df['close'] - df['open'])
            created_features.append('body_size')
        
        # Wicks - always calculate (these are new features)
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        created_features.extend(['upper_wick', 'lower_wick'])
        
        # wick_ratio - always calculate (new feature)
        df['wick_ratio'] = np.where(df['body_size'] > 0, 
                                    df['upper_wick'] / df['body_size'], 0)
        created_features.append('wick_ratio')
        
        # candle_body_pct - ONLY calculate if not already in input
        # DO NOT recalculate - trust the input value!
        if 'candle_body_pct' not in df.columns:
            candle_range = df['high'] - df['low']
            df['candle_body_pct'] = np.where(candle_range > 0,
                                            df['body_size'] / candle_range,
                                            0.5)
            created_features.append('candle_body_pct')
        
        # Rest of the features (create only if not exist)
        # ... (similar pattern for other features)
        
        print(f"📊 Created {len(created_features)} new features")
        return df


    def _create_lagged_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create lagged features for each lag period
        """
        # Features to lag - focus on ones needed for required features
        lag_features = {
            # Required features with lags
            'ret': 'ret',
            'rsi_slope': 'rsi_slope',
            'dist_bb_upper': 'dist_bb_upper',
            
            # Additional useful features
            'close': 'close',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'volume': 'volume',
            'rsi_value': 'rsi_value',
            'body_size': 'body_size',
            'candle_body_pct': 'candle_body_pct',
            'bb_upper_touch': 'bb_upper_touch',
            'bb_mid_rejection': 'bb_mid_rejection',
            'upper_wick': 'upper_wick',
            'lower_wick': 'lower_wick'
        }
        
        # Create lagged features
        for base_name, col_name in lag_features.items():
            if col_name not in df.columns:
                continue
                
            for lag in self.lags:
                lag_col_name = f"{base_name}_lag{lag}"
                df[lag_col_name] = df[col_name].shift(lag)
        
        return df


    def _create_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create derived features from lagged features
        """
        # RSI slope over 3 periods - REQUIRED: 'RSI_slope_3'
        if 'RSI_slope_3' not in df.columns:
            if 'rsi_value_lag1' in df.columns and 'rsi_value_lag3' in df.columns:
                df['RSI_slope_3'] = df['rsi_value_lag1'] - df['rsi_value_lag3']
            else:
                # Fallback calculation
                df['RSI_slope_3'] = df['rsi_value'].diff(periods=3)
        
        # Price slope over 3 periods - used for 'price_momentum'
        # NOTE: price_momentum already exists in input
        if 'price_slope_3' not in df.columns:
            if 'close_lag1' in df.columns and 'close_lag3' in df.columns:
                df['price_slope_3'] = df['close_lag1'] - df['close_lag3']
            else:
                # Fallback calculation
                df['price_slope_3'] = df['close'].diff(periods=3)
        
        # Only create price_momentum if it doesn't exist
        if 'price_momentum' not in df.columns:
            if 'price_slope_3' in df.columns:
                df['price_momentum'] = df['price_slope_3']
            else:
                df['price_momentum'] = 0.0
        
        # Upper rejection score (not required but useful)
        if 'upper_rejection_score' not in df.columns:
            if all(col in df.columns for col in ['upper_wick_lag1', 'body_size_lag1', 'bb_upper_touch_lag1']):
                # Avoid division by zero
                safe_body = np.where(df['body_size_lag1'] > 0, 
                                    df['body_size_lag1'], 1)
                df['upper_rejection_score'] = (df['upper_wick_lag1'] / safe_body) * df['bb_upper_touch_lag1']
            else:
                df['upper_rejection_score'] = 0.0
        
        # Reversal signal (not required but useful)
        if 'reversal_signal' not in df.columns:
            conditions = []
            if 'RSI_slope_3' in df.columns:
                conditions.append(df['RSI_slope_3'] < 0)
            if 'price_slope_3' in df.columns:
                conditions.append(df['price_slope_3'] < 0)
            if 'bb_upper_touch_lag1' in df.columns:
                conditions.append(df['bb_upper_touch_lag1'] == 1)
            
            if conditions:
                df['reversal_signal'] = np.logical_and.reduce(conditions).astype(int)
            else:
                df['reversal_signal'] = 0
        
        return df


    def _ensure_required_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure all required features exist in the DataFrame
        """
        for feature in self.required_model_features:
            if feature not in df.columns:
                # Provide intelligent defaults for missing required features
                if feature == 'price_momentum' and 'price_slope_3' in df.columns:
                    df['price_momentum'] = df['price_slope_3']
                elif feature == 'candle_body_pct' and 'wick_ratio' in df.columns:
                    # Use wick_ratio as proxy if candle_body_pct not calculated
                    df['candle_body_pct'] = 1 - df['wick_ratio'].abs()
                else:
                    # Fill with 0 for other missing features
                    df[feature] = 0.0
        
        return df


    def extract_model_features(self, df_features: pd.DataFrame) -> pd.DataFrame:
        """
        Extract only the required features for the model
        
        Args:
            df_features: DataFrame with all features created
            
        Returns:
            DataFrame with only the 13 required model features
        """
        # Create result DataFrame
        result_df = pd.DataFrame(index=df_features.index)
        
        # For each required feature, get it from df_features
        for feature in self.required_model_features:
            if feature in df_features.columns:
                # Use the value from df_features (could be from input or calculated)
                result_df[feature] = df_features[feature].fillna(0)
            else:
                # Feature not found at all
                print(f"⚠️  Feature '{feature}' not found in DataFrame")
                result_df[feature] = 0.0
        
        return result_df


    def get_required_features(self) -> List[str]:
        """
        Get the list of required model features
        """
        return self.required_model_features.copy()
    
    def get_all_feature_columns(self) -> List[str]:
        """
        Get list of all feature columns created (for reference)
        """
        # This would need to be called after create_all_features
        # For now, return the categories of features created
        return [
            "Base features: ret, dist_bb_upper, rsi_slope, body_size, candle_body_pct",
            "Lagged features: ret_lag[1-3], rsi_slope_lag[1-3], etc.",
            "Derived features: RSI_slope_3, price_momentum, price_slope_3",
            "Additional: bb_upper_touch, upper_rejection, atr_norm, etc."
        ]