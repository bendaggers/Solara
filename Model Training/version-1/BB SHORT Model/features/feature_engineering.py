import pandas as pd
import numpy as np
from typing import List, Dict
import warnings
warnings.filterwarnings('ignore')

class BollingerBandsFeatureEngineer:
    """
    Feature engineering for Bollinger Bands Reversal Short model
    """
    
    def __init__(self, lags: List[int] = None):
        """
        Initialize feature engineer
        
        Args:
            lags: List of lag periods (e.g., [1, 2, 3])
        """
        self.lags = lags or [1, 2, 3]
        
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
        
        # Step 4: Clean up - drop NaN rows from lagging
        df_features = df_features.dropna()
        
        return df_features
    
    def _create_base_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create base features from raw data
        """
        df = df.copy()
        
        # 1. Returns (percentage change)
        df['ret'] = df['close'].pct_change()
        
        # 2. Bollinger Band features
        df['dist_bb_upper'] = df['upper_band'] - df['close']
        df['bb_upper_touch'] = (df['high'] >= df['upper_band']).astype(int)
        
        # Check if middle band is touched/rejected
        df['bb_mid_rejection'] = ((df['high'] > df['middle_band']) & 
                                  (df['close'] < df['middle_band'])).astype(int)
        
        # 3. RSI features
        df['rsi_slope'] = df['rsi_value'].diff()
        df['rsi_overbought'] = (df['rsi_value'] > 70).astype(int)
        
        # 4. Candle shape features
        df['body_size'] = abs(df['close'] - df['open'])
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        
        # Avoid division by zero for body_size
        df['wick_ratio'] = np.where(df['body_size'] > 0, 
                                     df['upper_wick'] / df['body_size'], 0)
        
        # Close position within candle (0-1, where 0=at low, 1=at high)
        candle_range = df['high'] - df['low']
        df['close_pos_in_candle'] = np.where(candle_range > 0,
                                             (df['close'] - df['low']) / candle_range,
                                             0.5)
        
        # Upper rejection (strong upper wick)
        df['upper_rejection'] = ((df['upper_wick'] > df['body_size']) & 
                                 (df['upper_wick'] > df['lower_wick'])).astype(int)
        
        # Lower high (failed to make new high)
        df['lower_high'] = (df['high'] < df['high'].shift(1)).astype(int)
        
        # Normalized ATR (assuming atr_pct is ATR as percentage of price)
        df['atr_norm'] = df['atr_pct'] / 100  # Convert percentage to decimal
        
        # EMA 50 slope (approximate with SMA for simplicity)
        # Note: We'll calculate EMA properly if not in data
        if 'ema_50' not in df.columns:
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_50_slope'] = df['ema_50'].diff()
        df['price_below_ema50'] = (df['close'] < df['ema_50']).astype(int)
        
        # Candle vs BB width
        candle_range = df['high'] - df['low']
        bb_width = df['upper_band'] - df['lower_band']
        df['candle_vs_bb'] = np.where(bb_width > 0, candle_range / bb_width, 0)
        df['body_vs_bb'] = np.where(bb_width > 0, df['body_size'] / bb_width, 0)
        
        return df
    
    def _create_lagged_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create lagged features for each lag period
        """
        # Features to lag (from functional specs)
        lag_features = {
            # Price features
            'close': 'close',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'volume': 'volume',
            'ret': 'ret',
            
            # BB features
            'bb_position': 'bb_position',
            'bb_width_pct': 'bb_width_pct',
            'dist_bb_upper': 'dist_bb_upper',
            'bb_upper_touch': 'bb_upper_touch',
            'bb_mid_rejection': 'bb_mid_rejection',
            
            # RSI features
            'rsi_value': 'rsi_value',
            'rsi_slope': 'rsi_slope',
            'rsi_overbought': 'rsi_overbought',
            
            # Candle features
            'body_size': 'body_size',
            'upper_wick': 'upper_wick',
            'lower_wick': 'lower_wick',
            'wick_ratio': 'wick_ratio',
            'close_pos_in_candle': 'close_pos_in_candle',
            'upper_rejection': 'upper_rejection',
            'lower_high': 'lower_high',
            'atr_norm': 'atr_norm',
            'ema_50_slope': 'ema_50_slope',
            'price_below_ema50': 'price_below_ema50',
            'candle_vs_bb': 'candle_vs_bb',
            'body_vs_bb': 'body_vs_bb'
        }
        
        # Create lagged features
        for base_name, col_name in lag_features.items():
            if col_name not in df.columns:
                print(f"Warning: {col_name} not found in dataframe")
                continue
                
            for lag in self.lags:
                lag_col_name = f"{base_name}_lag{lag}"
                df[lag_col_name] = df[col_name].shift(lag)
        
        return df
    
    def _create_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create derived features from lagged features
        """
        # RSI slope over 3 periods
        if 'rsi_value_lag1' in df.columns and 'rsi_value_lag3' in df.columns:
            df['RSI_slope_3'] = df['rsi_value_lag1'] - df['rsi_value_lag3']
        
        # Price slope over 3 periods
        if 'close_lag1' in df.columns and 'close_lag3' in df.columns:
            df['price_slope_3'] = df['close_lag1'] - df['close_lag3']
        
        # Upper rejection score
        if all(col in df.columns for col in ['upper_wick_lag1', 'body_size_lag1', 'bb_upper_touch_lag1']):
            # Avoid division by zero
            safe_body = np.where(df['body_size_lag1'] > 0, 
                                 df['body_size_lag1'], 1)
            df['upper_rejection_score'] = (df['upper_wick_lag1'] / safe_body) * df['bb_upper_touch_lag1']
        
        # Reversal signal
        conditions = []
        if 'RSI_slope_3' in df.columns:
            conditions.append(df['RSI_slope_3'] < 0)
        if 'price_slope_3' in df.columns:
            conditions.append(df['price_slope_3'] < 0)
        if 'bb_upper_touch_lag1' in df.columns:
            conditions.append(df['bb_upper_touch_lag1'] == 1)
        
        if conditions:
            df['reversal_signal'] = np.logical_and.reduce(conditions).astype(int)
        
        return df
    
    def get_feature_columns(self) -> List[str]:
        """
        Get list of all feature columns created
        """
        feature_cols = []
        
        # Lagged features
        base_features = ['close', 'open', 'high', 'low', 'volume', 'ret',
                        'bb_position', 'bb_width_pct', 'dist_bb_upper', 
                        'bb_upper_touch', 'bb_mid_rejection',
                        'rsi_value', 'rsi_slope', 'rsi_overbought',
                        'body_size', 'upper_wick', 'lower_wick', 'wick_ratio',
                        'close_pos_in_candle', 'upper_rejection', 'lower_high',
                        'atr_norm', 'ema_50_slope', 'price_below_ema50',
                        'candle_vs_bb', 'body_vs_bb']
        
        for base in base_features:
            for lag in self.lags:
                feature_cols.append(f"{base}_lag{lag}")
        
        # Derived features
        derived = ['RSI_slope_3', 'price_slope_3', 'upper_rejection_score', 'reversal_signal']
        feature_cols.extend(derived)
        
        return feature_cols