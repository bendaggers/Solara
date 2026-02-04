"""
Universal Preprocessor - Clean Version
With timestamp conversion utilities
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Union
import warnings
warnings.filterwarnings('ignore')


# ================== UniversalPreprocessor ==================
class UniversalPreprocessor:
    """
    Universal Preprocessor - Only preprocessing methods
    Includes timestamp conversion utilities
    """
    
    def __init__(self, add_original_cols: bool = True, lags: Optional[List[int]] = None):
        """
        Initialize preprocessor with built-in FeatureEngineer
        
        Parameters:
        -----------
        add_original_cols : bool, default=True
            Whether to include original columns in output
        lags : List[int], optional
            Lag periods for feature engineering (default: [1, 2, 3])
        """
        # FIXED: Import FeatureEngineer correctly
        # Make sure feature_engineering.py is in the same directory
        try:
            from feature_engineering import FeatureEngineer
            self.feature_engineer = FeatureEngineer(lags=lags)
        except ImportError as e:
            # If feature_engineering.py is not in same directory, try relative import
            try:
                from .feature_engineering import FeatureEngineer
                self.feature_engineer = FeatureEngineer(lags=lags)
            except ImportError:
                raise ImportError(
                    "Cannot import FeatureEngineer. Make sure 'feature_engineering.py' "
                    "is in the same directory as 'universal_preprocessor.py' or in the Python path."
                ) from e
        
        self.add_original_cols = add_original_cols

    def get_latest_candle_per_pair(self, df: pd.DataFrame, timestamp_col: str = 'timestamp') -> pd.DataFrame:
        """
        Trim DataFrame to keep only the latest candle for each pair.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input DataFrame with multiple candles per pair
        timestamp_col : str, default='timestamp'
            Name of timestamp column
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with only the latest candle for each pair
        """
        if df.empty:
            return df
        
        # Ensure we have a timestamp column
        if timestamp_col not in df.columns:
            # Try to find alternative timestamp column
            timestamp_cols = [col for col in df.columns if 'time' in col.lower()]
            if timestamp_cols:
                timestamp_col = timestamp_cols[0]
            else:
                # If no timestamp column, just take the last row for each pair
                print("⚠️  No timestamp column found. Using last row for each pair.")
                if 'pair' in df.columns:
                    return df.groupby('pair').tail(1)
                elif 'symbol' in df.columns:
                    return df.groupby('symbol').tail(1)
                else:
                    print("⚠️  No pair/symbol column found. Returning all rows.")
                    return df
        
        # Identify the pair/symbol column
        pair_col = None
        if 'pair' in df.columns:
            pair_col = 'pair'
        elif 'symbol' in df.columns:
            pair_col = 'symbol'
        
        if pair_col:
            # Ensure timestamp is datetime
            if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
                df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
            
            # Sort by timestamp descending
            df_sorted = df.sort_values(timestamp_col, ascending=False)
            
            # Get the latest candle for each pair
            latest_candles = df_sorted.drop_duplicates(subset=[pair_col], keep='first')
            
            # Sort by pair for consistency
            latest_candles = latest_candles.sort_values(pair_col)
            
            # print(f"✅ Trimmed to latest candle per pair: {len(latest_candles)} rows (was {len(df)} rows)")
            
            return latest_candles
        else:
            print("⚠️  No pair/symbol column found. Returning DataFrame unchanged.")
            return df
 


    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process DataFrame and return processed DataFrame
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input DataFrame with required columns
        
        Returns:
        --------
        pd.DataFrame
            Processed DataFrame with ONLY the 13 model features
        """
        if df.empty:
            return pd.DataFrame()
        
        print("🔧 Starting data preprocessing...")
        
        try:
            # Validate and prepare input DataFrame
            df_processed = self._validate_and_prepare_dataframe(df)
            
            # Convert timestamp if present
            if 'timestamp' in df_processed.columns:
                df_processed = self.convert_timestamp_column(df_processed, 'timestamp')
            
            # Create features using feature engineer
            df_features = self.feature_engineer.create_all_features(df_processed)
            
            if df_features.empty:
                print("⚠️  No features created - returning empty DataFrame")
                return pd.DataFrame()
            
            # ===== IMPORTANT: Extract ONLY the 13 model features =====
            df_model_features = self.feature_engineer.extract_model_features(df_features)
            
            # Add essential metadata columns (symbol, timestamp, price)
            if 'pair' in df_processed.columns:
                df_model_features['symbol'] = df_processed['pair']
            elif 'symbol' in df_processed.columns:
                df_model_features['symbol'] = df_processed['symbol']
            
            if 'timestamp' in df_processed.columns:
                df_model_features['timestamp'] = df_processed['timestamp']
            
            if 'close' in df_processed.columns:
                df_model_features['price'] = df_processed['close']
                df_model_features['close'] = df_processed['close']
            
            # ===== ADD THIS AS THE LAST STEP =====
            print("✂️  Trimming to latest candles per pair...")
            df_model_features = self.get_latest_candle_per_pair(df_model_features, timestamp_col='timestamp')
            # ===== END ADDITION =====
            
            print(f"✅ Data preprocessing completed: {len(df_model_features)} rows, {len(df_model_features.columns)} features")
            
            return df_model_features
            
        except Exception as e:
            print(f"❌ Error in preprocessing: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame() 

    
    def _validate_and_prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate input and add missing columns with defaults
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input DataFrame
        
        Returns:
        --------
        pd.DataFrame
            Validated and prepared DataFrame
        """
        df = df.copy()
        
        # Define required columns for the model
        required_cols = ['close', 'open', 'high', 'low', 'upper_band', 
                        'lower_band', 'middle_band', 'rsi_value']
        
        # Check for required columns
        missing_required = [col for col in required_cols if col not in df.columns]
        
        if missing_required:
            raise ValueError(f"Missing required columns: {missing_required}")
        
        # Add optional columns if missing
        optional_cols = {
            'volume': 0.0,
            'atr_pct': 0.0,
            'pair': f"SYMBOL_{df.index[0]}" if not df.empty else "UNKNOWN"
        }
        
        for col, default_val in optional_cols.items():
            if col not in df.columns:
                if col == 'pair' and 'symbol' in df.columns:
                    df['pair'] = df['symbol']
                else:
                    df[col] = default_val
        
        # Convert numeric columns to appropriate dtypes
        numeric_cols = ['close', 'open', 'high', 'low', 'upper_band', 
                       'lower_band', 'middle_band', 'rsi_value', 'volume', 'atr_pct']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Ensure EMA column exists (needed by feature engineer)
        if 'ema_50' not in df.columns:
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        return df
    
    def get_required_features(self) -> List[str]:
        """
        Get the list of required model features
        
        Returns:
        --------
        List[str]
            List of required feature names
        """
        return self.feature_engineer.get_required_features()
    
    def get_feature_engineer(self):
        """
        Get the feature engineer instance
        
        Returns:
        --------
        FeatureEngineer
            The feature engineer instance
        """
        return self.feature_engineer
    
    @staticmethod
    def convert_timestamp_format(timestamp_str: str, 
                                 input_format: str = "%Y.%m.%d %H:%M:%S",
                                 output_format: Optional[str] = None) -> Union[datetime, str]:
        """
        Convert timestamp string from one format to another
        
        Parameters:
        -----------
        timestamp_str : str
            Timestamp string to convert
        input_format : str
            Format of input string (default: "2024.01.19 04:00:00")
        output_format : str, optional
            Format for output string. If None, returns datetime object
        
        Returns:
        --------
        Union[datetime, str]
            Converted datetime object or formatted string
        """
        try:
            dt = datetime.strptime(timestamp_str, input_format)
            
            if output_format is None:
                return dt
            else:
                return dt.strftime(output_format)
                
        except ValueError:
            return pd.NaT
    
    def convert_timestamp_column(self, 
                                 df: pd.DataFrame, 
                                 column_name: str = 'timestamp',
                                 input_format: str = "%Y.%m.%d %H:%M:%S",
                                 output_format: Optional[str] = None,
                                 inplace: bool = False,
                                 keep_original: bool = True) -> pd.DataFrame:
        """
        Convert timestamp column in DataFrame
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input DataFrame
        column_name : str, default='timestamp'
            Name of timestamp column
        input_format : str
            Format of timestamp strings (default: "2024.01.19 04:00:00")
        output_format : str, optional
            Output format. Options:
            - None: Convert to datetime objects
            - "%Y-%m-%d %H:%M:%S": ISO format string
            - "%Y%m%d_%H%M%S": Compact format
            - "unix": Unix timestamp
            - "date": Date only
            - "time": Time only
        inplace : bool, default=False
            If True, modify DataFrame in place
        keep_original : bool, default=True
            If True, keep original column with '_str' suffix
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with converted timestamp column
        """
        if not inplace:
            df = df.copy()
        
        if column_name not in df.columns:
            return df
        
        # Save original column if requested
        if keep_original:
            df[f'{column_name}_str'] = df[column_name]
        
        # Convert based on output_format
        if output_format == 'unix':
            # Convert to Unix timestamp
            df[column_name] = pd.to_datetime(df[column_name], format=input_format, errors='coerce')
            df[column_name] = df[column_name].astype('int64') // 10**9
            
        elif output_format == 'date':
            # Extract date part only
            df[column_name] = pd.to_datetime(df[column_name], format=input_format, errors='coerce').dt.date
            
        elif output_format == 'time':
            # Extract time part only
            df[column_name] = pd.to_datetime(df[column_name], format=input_format, errors='coerce').dt.time
            
        elif output_format is None:
            # Convert to datetime object
            df[column_name] = pd.to_datetime(df[column_name], format=input_format, errors='coerce')
            
        else:
            # Convert to custom format string
            def convert_to_format(x):
                try:
                    dt = datetime.strptime(str(x), input_format)
                    return dt.strftime(output_format)
                except (ValueError, TypeError):
                    return pd.NaT
            
            df[column_name] = df[column_name].apply(convert_to_format)
        
        return df
    
    def extract_datetime_components(self, 
                                    df: pd.DataFrame, 
                                    timestamp_column: str = 'timestamp',
                                    input_format: str = "%Y.%m.%d %H:%M:%S",
                                    components: List[str] = None) -> pd.DataFrame:
        """
        Extract datetime components (year, month, day, hour, minute, etc.)
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input DataFrame
        timestamp_column : str, default='timestamp'
            Name of timestamp column
        input_format : str
            Format of timestamp strings
        components : List[str], optional
            Components to extract. Options:
            ['year', 'month', 'day', 'hour', 'minute', 'second', 
             'dayofweek', 'week', 'quarter', 'dayofyear']
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with extracted datetime components
        """
        df = df.copy()
        
        if timestamp_column not in df.columns:
            return df
        
        # Default components
        if components is None:
            components = ['year', 'month', 'day', 'hour', 'minute', 'dayofweek']
        
        # Convert to datetime first
        df_temp = self.convert_timestamp_column(
            df, 
            column_name=timestamp_column,
            input_format=input_format,
            output_format=None,
            inplace=False,
            keep_original=False
        )
        
        # Extract components
        for component in components:
            if component == 'year':
                df[f'{timestamp_column}_year'] = df_temp[timestamp_column].dt.year
            elif component == 'month':
                df[f'{timestamp_column}_month'] = df_temp[timestamp_column].dt.month
            elif component == 'day':
                df[f'{timestamp_column}_day'] = df_temp[timestamp_column].dt.day
            elif component == 'hour':
                df[f'{timestamp_column}_hour'] = df_temp[timestamp_column].dt.hour
            elif component == 'minute':
                df[f'{timestamp_column}_minute'] = df_temp[timestamp_column].dt.minute
            elif component == 'second':
                df[f'{timestamp_column}_second'] = df_temp[timestamp_column].dt.second
            elif component == 'dayofweek':
                df[f'{timestamp_column}_dayofweek'] = df_temp[timestamp_column].dt.dayofweek
            elif component == 'week':
                df[f'{timestamp_column}_week'] = df_temp[timestamp_column].dt.isocalendar().week
            elif component == 'quarter':
                df[f'{timestamp_column}_quarter'] = df_temp[timestamp_column].dt.quarter
            elif component == 'dayofyear':
                df[f'{timestamp_column}_dayofyear'] = df_temp[timestamp_column].dt.dayofyear
        
        return df
    
    def validate_timestamps_sequential(self, 
                                       df: pd.DataFrame, 
                                       timestamp_column: str = 'timestamp',
                                       input_format: str = "%Y.%m.%d %H:%M:%S",
                                       expected_interval: str = '1min') -> Dict:
        """
        Validate that timestamps are sequential with consistent intervals
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input DataFrame
        timestamp_column : str, default='timestamp'
            Name of timestamp column
        input_format : str
            Format of timestamp strings
        expected_interval : str
            Expected time interval (e.g., '1min', '5min', '1H', '1D')
        
        Returns:
        --------
        Dict
            Validation results with issues and statistics
        """
        if timestamp_column not in df.columns:
            return {'error': f"Column '{timestamp_column}' not found"}
        
        df_temp = df.copy()
        df_temp = self.convert_timestamp_column(
            df_temp, 
            column_name=timestamp_column,
            input_format=input_format,
            output_format=None,
            inplace=False,
            keep_original=False
        )
        
        # Sort by timestamp
        df_temp = df_temp.sort_values(timestamp_column)
        
        # Calculate time differences
        time_diffs = df_temp[timestamp_column].diff().dropna()
        
        # Convert expected interval to timedelta
        interval_map = {
            '1min': pd.Timedelta(minutes=1),
            '5min': pd.Timedelta(minutes=5),
            '15min': pd.Timedelta(minutes=15),
            '1H': pd.Timedelta(hours=1),
            '4H': pd.Timedelta(hours=4),
            '1D': pd.Timedelta(days=1),
        }
        
        expected_td = interval_map.get(expected_interval, pd.Timedelta(minutes=1))
        
        # Analyze differences
        results = {
            'total_rows': len(df_temp),
            'missing_timestamps': df_temp[timestamp_column].isnull().sum(),
            'duplicate_timestamps': df_temp[timestamp_column].duplicated().sum(),
            'expected_interval': str(expected_td),
            'actual_min_interval': str(time_diffs.min()),
            'actual_max_interval': str(time_diffs.max()),
            'actual_median_interval': str(time_diffs.median()),
            'gaps_count': (time_diffs != expected_td).sum(),
            'missing_periods': [],
            'out_of_sequence': []
        }
        
        # Find gaps
        if results['gaps_count'] > 0:
            gap_indices = np.where(time_diffs != expected_td)[0]
            for idx in gap_indices[:10]:  # Show first 10 gaps
                results['missing_periods'].append({
                    'position': int(idx),
                    'actual_gap': str(time_diffs.iloc[idx]),
                    'expected_gap': str(expected_td),
                    'before_timestamp': str(df_temp.iloc[idx][timestamp_column]),
                    'after_timestamp': str(df_temp.iloc[idx+1][timestamp_column])
                })
        
        # Check for out-of-sequence timestamps
        out_of_seq = (time_diffs < pd.Timedelta(0)).sum()
        results['out_of_sequence_count'] = int(out_of_seq)
        
        return results
    
    def process_batch(self, dataframes: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Process multiple DataFrames in batch
        
        Parameters:
        -----------
        dataframes : Dict[str, pd.DataFrame]
            Dictionary of DataFrames with symbols as keys
        
        Returns:
        --------
        Dict[str, pd.DataFrame]
            Dictionary of processed DataFrames
        """
        results = {}
        
        print("🔧 Starting batch processing...")
        
        for symbol, df in dataframes.items():
            # Add symbol column if not present
            if 'symbol' not in df.columns and 'pair' not in df.columns:
                df = df.copy()
                df['symbol'] = symbol
                df['pair'] = symbol
            
            processed_df = self.process(df)
            
            if not processed_df.empty:
                results[symbol] = processed_df
        
        print(f"✅ Batch processing completed: {len(results)} symbols processed")
        return results
    
    def get_processed_features_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Get only the features DataFrame without original columns
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input DataFrame
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with only model features
        """
        # Temporarily set add_original_cols to False
        original_setting = self.add_original_cols
        self.add_original_cols = False
        
        try:
            features_df = self.process(df)
            return features_df
        finally:
            # Restore original setting
            self.add_original_cols = original_setting



