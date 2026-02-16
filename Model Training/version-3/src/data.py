"""
Data ingestion, preprocessing, and regime tagging.

This module handles the first stages of the pipeline:
1. Load CSV into DataFrame
2. Validate schema
3. Preprocess (parse timestamps, sort, clean)
4. Tag market regimes (for diagnostics)

All functions operate on and return pandas DataFrames.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


# =============================================================================
# EXCEPTIONS
# =============================================================================

class DataIngestionError(Exception):
    """Raised when data ingestion fails."""
    pass


class SchemaValidationError(Exception):
    """Raised when data schema validation fails."""
    pass


class DataIntegrityError(Exception):
    """Raised when data integrity checks fail."""
    pass


class InsufficientDataError(Exception):
    """Raised when there's not enough data."""
    pass


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DataStats:
    """Statistics about the loaded/processed data."""
    total_rows: int
    date_range: Tuple[str, str]
    n_features: int
    feature_names: List[str]
    rows_dropped: int = 0
    regime_counts: Optional[Dict[str, int]] = None


# =============================================================================
# INGESTION
# =============================================================================

def ingest(
    csv_path: str,
    required_columns: List[str],
    min_rows: int = 5000
) -> Tuple[pd.DataFrame, DataStats]:
    """
    Load CSV file into DataFrame and validate schema.
    
    Args:
        csv_path: Path to the input CSV file
        required_columns: List of columns that must be present
        min_rows: Minimum number of rows required
        
    Returns:
        Tuple of (DataFrame, DataStats)
        
    Raises:
        DataIngestionError: If file cannot be loaded
        SchemaValidationError: If required columns are missing
        InsufficientDataError: If not enough rows
    """
    path = Path(csv_path)
    
    # Check file exists
    if not path.exists():
        raise DataIngestionError(f"File not found: {csv_path}")
    
    if not path.suffix.lower() == '.csv':
        raise DataIngestionError(f"Expected CSV file, got: {path.suffix}")
    
    # Load CSV
    try:
        df = pd.read_csv(csv_path, sep=None, engine='python')  # Auto-detect separator
    except Exception as e:
        raise DataIngestionError(f"Failed to read CSV: {e}")
    
    # Check for empty file
    if df.empty:
        raise DataIngestionError("CSV file is empty")
    
    # Normalize column names (lowercase, strip whitespace)
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # Validate required columns
    missing_columns = [col for col in required_columns if col.lower() not in df.columns]
    if missing_columns:
        raise SchemaValidationError(
            f"Missing required columns: {missing_columns}. "
            f"Available columns: {df.columns.tolist()}"
        )
    
    # Check minimum rows
    if len(df) < min_rows:
        raise InsufficientDataError(
            f"Insufficient data: {len(df)} rows, minimum required: {min_rows}"
        )
    
    # Check for duplicate column names
    if df.columns.duplicated().any():
        duplicates = df.columns[df.columns.duplicated()].tolist()
        raise SchemaValidationError(f"Duplicate column names found: {duplicates}")
    
    # Compute stats
    stats = DataStats(
        total_rows=len(df),
        date_range=("unknown", "unknown"),  # Will be updated after timestamp parsing
        n_features=len(df.columns),
        feature_names=df.columns.tolist()
    )
    
    return df, stats


# =============================================================================
# PREPROCESSING
# =============================================================================

def preprocess(
    df: pd.DataFrame,
    timestamp_column: str,
    timestamp_format: str,
    ohlcv_columns: List[str]
) -> Tuple[pd.DataFrame, DataStats]:
    """
    Preprocess DataFrame: parse timestamps, sort, validate, clean.
    
    Args:
        df: Raw DataFrame from ingestion
        timestamp_column: Name of timestamp column
        timestamp_format: Format string for parsing timestamps
        ohlcv_columns: List of OHLCV column names
        
    Returns:
        Tuple of (preprocessed DataFrame, DataStats)
        
    Raises:
        DataIntegrityError: If data integrity checks fail
    """
    df = df.copy()
    rows_before = len(df)
    
    # --- Parse timestamp ---
    try:
        df[timestamp_column] = pd.to_datetime(
            df[timestamp_column], 
            format=timestamp_format
        )
    except Exception as e:
        raise DataIntegrityError(f"Failed to parse timestamp column: {e}")
    
    # --- Sort by timestamp ---
    df = df.sort_values(timestamp_column).reset_index(drop=True)
    
    # --- Check for duplicate timestamps ---
    duplicate_timestamps = df[timestamp_column].duplicated()
    if duplicate_timestamps.any():
        n_duplicates = duplicate_timestamps.sum()
        raise DataIntegrityError(
            f"Found {n_duplicates} duplicate timestamps. "
            "Each candle must have a unique timestamp."
        )
    
    # --- Validate OHLCV columns are numeric ---
    for col in ohlcv_columns:
        if col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except Exception as e:
                    raise DataIntegrityError(f"Column '{col}' is not numeric: {e}")
    
    # --- Drop rows with NaN in OHLCV ---
    ohlcv_present = [col for col in ohlcv_columns if col in df.columns]
    rows_with_nan = df[ohlcv_present].isna().any(axis=1)
    n_nan_rows = rows_with_nan.sum()
    
    if n_nan_rows > 0:
        df = df[~rows_with_nan].reset_index(drop=True)
    
    rows_after = len(df)
    rows_dropped = rows_before - rows_after
    
    # --- Validate OHLC relationships ---
    if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        invalid_ohlc = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        )
        if invalid_ohlc.any():
            n_invalid = invalid_ohlc.sum()
            # Just warn, don't fail - some data sources have quirks
            import warnings
            warnings.warn(f"Found {n_invalid} rows with invalid OHLC relationships")
    
    # --- Get date range ---
    date_range = (
        df[timestamp_column].min().strftime('%Y-%m-%d'),
        df[timestamp_column].max().strftime('%Y-%m-%d')
    )
    
    # --- Identify feature columns ---
    # Features are all numeric columns except excluded ones
    excluded = {timestamp_column, 'pair', 'symbol'}
    feature_columns = [
        col for col in df.columns 
        if col not in excluded and pd.api.types.is_numeric_dtype(df[col])
    ]
    
    stats = DataStats(
        total_rows=len(df),
        date_range=date_range,
        n_features=len(feature_columns),
        feature_names=feature_columns,
        rows_dropped=rows_dropped
    )
    
    return df, stats


# =============================================================================
# REGIME TAGGING
# =============================================================================

def calculate_adx(
    df: pd.DataFrame,
    high_col: str = 'high',
    low_col: str = 'low',
    close_col: str = 'close',
    period: int = 14
) -> pd.Series:
    """
    Calculate Average Directional Index (ADX).
    
    Args:
        df: DataFrame with OHLC data
        high_col: Name of high column
        low_col: Name of low column
        close_col: Name of close column
        period: ADX period
        
    Returns:
        Series with ADX values
    """
    high = df[high_col]
    low = df[low_col]
    close = df[close_col]
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Smoothed values (Wilder's smoothing)
    atr = pd.Series(tr).ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / atr
    
    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return adx


def calculate_atr(
    df: pd.DataFrame,
    high_col: str = 'high',
    low_col: str = 'low',
    close_col: str = 'close',
    period: int = 14
) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    Args:
        df: DataFrame with OHLC data
        high_col: Name of high column
        low_col: Name of low column
        close_col: Name of close column
        period: ATR period
        
    Returns:
        Series with ATR values
    """
    high = df[high_col]
    low = df[low_col]
    close = df[close_col]
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    
    return atr


def calculate_atr_percentile(
    atr: pd.Series,
    window: int = 100
) -> pd.Series:
    """
    Calculate rolling percentile rank of ATR.
    
    Args:
        atr: Series with ATR values
        window: Rolling window size
        
    Returns:
        Series with ATR percentile values (0-100)
    """
    def percentile_rank(x):
        if len(x) < 2:
            return 50.0
        rank = (x.values[:-1] < x.values[-1]).sum()
        return 100.0 * rank / (len(x) - 1)
    
    atr_pctl = atr.rolling(window=window, min_periods=20).apply(
        percentile_rank, raw=False
    )
    
    return atr_pctl


def tag_regimes(
    df: pd.DataFrame,
    adx_period: int = 14,
    atr_period: int = 14,
    atr_percentile_window: int = 100,
    trending_adx_threshold: float = 25.0,
    volatile_atr_percentile: float = 70.0
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Tag each candle with a market regime for diagnostic purposes.
    
    Regimes:
    - trending: ADX > threshold (strong directional movement)
    - volatile: ADX <= threshold AND ATR percentile >= volatile threshold
    - ranging: ADX <= threshold AND ATR percentile < volatile threshold
    
    Args:
        df: Preprocessed DataFrame with OHLC data
        adx_period: Period for ADX calculation
        atr_period: Period for ATR calculation
        atr_percentile_window: Window for ATR percentile calculation
        trending_adx_threshold: ADX threshold for trending regime
        volatile_atr_percentile: ATR percentile threshold for volatile regime
        
    Returns:
        Tuple of (DataFrame with regime column, regime counts dict)
    """
    df = df.copy()
    
    # Calculate indicators if not present
    if 'adx' not in df.columns:
        df['_adx'] = calculate_adx(df, period=adx_period)
    else:
        df['_adx'] = df['adx']
    
    if 'atr_14' not in df.columns:
        df['_atr'] = calculate_atr(df, period=atr_period)
    else:
        df['_atr'] = df['atr_14']
    
    # Calculate ATR percentile
    df['_atr_percentile'] = calculate_atr_percentile(
        df['_atr'], 
        window=atr_percentile_window
    )
    
    # Assign regimes
    conditions = [
        df['_adx'] > trending_adx_threshold,  # Trending
        (df['_adx'] <= trending_adx_threshold) & (df['_atr_percentile'] >= volatile_atr_percentile),  # Volatile
    ]
    choices = ['trending', 'volatile']
    
    df['regime'] = np.select(conditions, choices, default='ranging')
    
    # Clean up temporary columns
    df = df.drop(columns=['_adx', '_atr', '_atr_percentile'])
    
    # Count regimes
    regime_counts = df['regime'].value_counts().to_dict()
    
    # Ensure all regimes are represented
    for regime in ['trending', 'ranging', 'volatile']:
        if regime not in regime_counts:
            regime_counts[regime] = 0
    
    return df, regime_counts


# =============================================================================
# FEATURE UTILITIES
# =============================================================================

def get_feature_columns(
    df: pd.DataFrame,
    exclude_columns: List[str]
) -> List[str]:
    """
    Get list of feature columns (numeric columns excluding specified).
    
    Args:
        df: DataFrame
        exclude_columns: Columns to exclude from features
        
    Returns:
        List of feature column names
    """
    exclude_set = set(col.lower() for col in exclude_columns)
    
    feature_columns = [
        col for col in df.columns
        if col.lower() not in exclude_set
        and pd.api.types.is_numeric_dtype(df[col])
    ]
    
    return feature_columns


def validate_feature_columns(
    df: pd.DataFrame,
    feature_columns: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Validate feature columns have no NaN values.
    
    Args:
        df: DataFrame
        feature_columns: List of feature column names
        
    Returns:
        Tuple of (valid columns, columns with NaN)
    """
    valid_columns = []
    nan_columns = []
    
    for col in feature_columns:
        if col in df.columns:
            if df[col].isna().any():
                nan_columns.append(col)
            else:
                valid_columns.append(col)
    
    return valid_columns, nan_columns


# =============================================================================
# MAIN DATA LOADING FUNCTION
# =============================================================================

def load_and_prepare_data(
    csv_path: str,
    config: Dict[str, Any]
) -> Tuple[pd.DataFrame, DataStats]:
    """
    Complete data loading pipeline: ingest → preprocess → tag regimes.
    
    This is the main entry point for data loading.
    
    Args:
        csv_path: Path to input CSV
        config: Configuration dictionary with schema and regime settings
        
    Returns:
        Tuple of (prepared DataFrame, DataStats)
    """
    # Extract config
    schema = config.get('schema', {})
    regime_config = config.get('regime', {})
    
    timestamp_column = schema.get('timestamp_column', 'timestamp')
    timestamp_format = schema.get('timestamp_format', '%Y.%m.%d %H:%M:%S')
    ohlcv_columns = schema.get('ohlcv_columns', ['open', 'high', 'low', 'close', 'volume'])
    
    # Build required columns list
    required_columns = [timestamp_column] + ohlcv_columns
    
    # Get signal columns
    signal_columns = schema.get('signal_columns', {})
    if signal_columns:
        required_columns.extend(signal_columns.values())
    
    # Make lowercase for comparison
    required_columns = [col.lower() for col in required_columns]
    
    # Step 1: Ingest
    df, stats = ingest(
        csv_path=csv_path,
        required_columns=required_columns,
        min_rows=config.get('min_rows', 5000)
    )
    
    # Step 2: Preprocess
    df, stats = preprocess(
        df=df,
        timestamp_column=timestamp_column,
        timestamp_format=timestamp_format,
        ohlcv_columns=ohlcv_columns
    )
    
    # Step 3: Tag regimes
    df, regime_counts = tag_regimes(
        df=df,
        adx_period=regime_config.get('adx_period', 14),
        atr_period=regime_config.get('atr_period', 14),
        atr_percentile_window=regime_config.get('atr_percentile_window', 100),
        trending_adx_threshold=regime_config.get('trending_adx_threshold', 25),
        volatile_atr_percentile=regime_config.get('volatile_atr_percentile', 70)
    )
    
    stats.regime_counts = regime_counts
    
    return df, stats


# =============================================================================
# DATA VALIDATION UTILITIES
# =============================================================================

def check_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Run data quality checks and return report.
    
    Args:
        df: DataFrame to check
        
    Returns:
        Dictionary with quality metrics
    """
    report = {
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'memory_mb': df.memory_usage(deep=True).sum() / 1024 / 1024,
        'nan_counts': {},
        'inf_counts': {},
        'column_types': {}
    }
    
    for col in df.columns:
        # NaN counts
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            report['nan_counts'][col] = nan_count
        
        # Inf counts (for numeric columns)
        if pd.api.types.is_numeric_dtype(df[col]):
            inf_count = np.isinf(df[col]).sum()
            if inf_count > 0:
                report['inf_counts'][col] = inf_count
        
        # Column types
        report['column_types'][col] = str(df[col].dtype)
    
    return report


def get_data_summary(df: pd.DataFrame, timestamp_column: str = 'timestamp') -> Dict[str, Any]:
    """
    Get summary statistics for the data.
    
    Args:
        df: DataFrame
        timestamp_column: Name of timestamp column
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        'n_rows': len(df),
        'n_columns': len(df.columns),
        'columns': df.columns.tolist()
    }
    
    if timestamp_column in df.columns:
        summary['date_start'] = df[timestamp_column].min().isoformat()
        summary['date_end'] = df[timestamp_column].max().isoformat()
        
        # Calculate time gaps
        time_diffs = df[timestamp_column].diff().dropna()
        summary['typical_interval'] = str(time_diffs.mode().iloc[0] if len(time_diffs) > 0 else 'unknown')
    
    if 'regime' in df.columns:
        summary['regime_distribution'] = df['regime'].value_counts().to_dict()
    
    return summary