"""
Solara AI Quant - H4/D1 Data Merger

Merges D1 (daily) data into H4 data WITHOUT data leakage.

CRITICAL: This is the most important code for MTF analysis.
Any bug here invalidates all results.

RULE: For each H4 candle, use ONLY the most recent
      COMPLETED D1 candle (previous day).
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
from pathlib import Path
import logging

from config import feature_config

logger = logging.getLogger(__name__)


class H4D1Merger:
    """
    Merges D1 data into H4 data without lookahead bias.
    
    Key principle:
    - H4 candle at 2024-01-15 08:00 should use D1 from 2024-01-14
    - D1 candle closes at 00:00 of the NEXT day
    - So D1 dated 2024-01-14 is available from 2024-01-15 00:00
    """
    
    def __init__(self, d1_lookback_shift: int = 1):
        """
        Args:
            d1_lookback_shift: Days to shift D1 data back (default 1 = previous day)
        """
        self.d1_lookback_shift = d1_lookback_shift
    
    def merge(
        self,
        df_h4: pd.DataFrame,
        df_d1: pd.DataFrame,
        validate: bool = True
    ) -> pd.DataFrame:
        """
        Merge D1 data into H4 data WITHOUT data leakage.
        
        Args:
            df_h4: H4 DataFrame with 'timestamp' column
            df_d1: D1 DataFrame with 'timestamp' column
            validate: If True, run leakage validation
            
        Returns:
            Merged DataFrame with D1 columns prefixed 'd1_'
            
        Raises:
            ValueError: If data leakage is detected
        """
        logger.info(f"Merging H4 ({len(df_h4)} rows) with D1 ({len(df_d1)} rows)")
        
        df_h4 = df_h4.copy()
        df_d1 = df_d1.copy()
        
        # 1. Ensure timestamps are datetime
        df_h4['timestamp'] = pd.to_datetime(df_h4['timestamp'])
        df_d1['timestamp'] = pd.to_datetime(df_d1['timestamp'])
        
        # 2. Get DATE of each H4 candle (normalized to midnight)
        df_h4['_h4_date'] = df_h4['timestamp'].dt.normalize()
        
        # 3. D1 data becomes available AFTER the day closes
        #    So a D1 candle dated Jan 15 is available starting Jan 16 00:00
        #    We shift the "available from" date by +1 day
        df_d1['_d1_close_date'] = df_d1['timestamp'].dt.normalize()
        df_d1['_d1_available_from'] = df_d1['_d1_close_date'] + pd.Timedelta(days=self.d1_lookback_shift)
        
        # 4. Rename D1 columns with 'd1_' prefix
        d1_cols_to_rename = [c for c in df_d1.columns 
                             if c not in ['timestamp', '_d1_close_date', '_d1_available_from']]
        rename_map = {c: f'd1_{c}' for c in d1_cols_to_rename}
        rename_map['timestamp'] = 'd1_timestamp'
        df_d1 = df_d1.rename(columns=rename_map)
        
        # 5. Sort both dataframes by time
        df_h4 = df_h4.sort_values('timestamp').reset_index(drop=True)
        df_d1 = df_d1.sort_values('_d1_available_from').reset_index(drop=True)
        
        # 6. Merge using merge_asof
        #    For each H4 row, find the most recent D1 where available_from <= h4_date
        df_merged = pd.merge_asof(
            df_h4,
            df_d1.drop(columns=['_d1_close_date']),
            left_on='_h4_date',
            right_on='_d1_available_from',
            direction='backward'  # Use most recent PAST D1
        )
        
        # 7. Clean up helper columns
        df_merged = df_merged.drop(columns=['_h4_date', '_d1_available_from'], errors='ignore')
        
        # 8. Count rows without D1 data (first few days)
        missing_d1 = df_merged['d1_timestamp'].isna().sum()
        if missing_d1 > 0:
            logger.info(f"  {missing_d1} H4 rows have no D1 data (start of dataset)")
        
        # 9. Validate no leakage
        if validate:
            is_valid, violations = self.validate_no_leakage(df_merged)
            if not is_valid:
                raise ValueError(
                    f"DATA LEAKAGE DETECTED: {len(violations)} rows have future D1 data!\n"
                    f"First violations:\n{violations.head(5)}"
                )
        
        logger.info(f"  Merge complete: {len(df_merged)} rows with {sum(1 for c in df_merged.columns if c.startswith('d1_'))} D1 columns")
        
        return df_merged
    
    def validate_no_leakage(self, df_merged: pd.DataFrame) -> Tuple[bool, pd.DataFrame]:
        """
        Validate that no D1 data comes from same day or future.
        
        RULE: d1_timestamp.date() must be < timestamp.date()
              (D1 date must be strictly BEFORE H4 date)
        
        Returns:
            (is_valid, violations_df)
        """
        # Skip rows without D1 data
        df = df_merged[df_merged['d1_timestamp'].notna()].copy()
        
        if len(df) == 0:
            logger.warning("No rows with D1 data to validate")
            return True, pd.DataFrame()
        
        h4_date = pd.to_datetime(df['timestamp']).dt.date
        d1_date = pd.to_datetime(df['d1_timestamp']).dt.date
        
        # D1 date must be strictly before H4 date
        violations = df[d1_date >= h4_date]
        
        is_valid = len(violations) == 0
        
        if is_valid:
            logger.info("  ✓ Leakage validation PASSED")
        else:
            logger.error(f"  ✗ Leakage validation FAILED: {len(violations)} violations")
        
        return is_valid, violations[['timestamp', 'd1_timestamp']]
    
    def get_merge_stats(self, df_merged: pd.DataFrame) -> dict:
        """Get statistics about the merge."""
        d1_cols = [c for c in df_merged.columns if c.startswith('d1_')]
        
        return {
            'total_h4_rows': len(df_merged),
            'h4_date_range': f"{df_merged['timestamp'].min()} to {df_merged['timestamp'].max()}",
            'd1_columns_added': len(d1_cols),
            'rows_with_d1_data': df_merged['d1_timestamp'].notna().sum(),
            'rows_without_d1_data': df_merged['d1_timestamp'].isna().sum(),
            'd1_lookback_shift': self.d1_lookback_shift
        }


def load_and_merge_h4_d1(
    h4_path: Path,
    d1_path: Path,
    validate_leakage: bool = True
) -> pd.DataFrame:
    """
    Convenience function to load H4/D1 CSVs and merge them.
    
    Args:
        h4_path: Path to H4 CSV
        d1_path: Path to D1 CSV
        validate_leakage: Validate no data leakage
        
    Returns:
        Merged DataFrame
    """
    from .csv_reader import CSVReader
    
    reader = CSVReader()
    
    # Load H4
    df_h4, error = reader.read_and_parse(h4_path)
    if error:
        raise ValueError(f"Error loading H4: {error}")
    
    # Load D1
    df_d1, error = reader.read_and_parse(d1_path)
    if error:
        raise ValueError(f"Error loading D1: {error}")
    
    # Merge
    merger = H4D1Merger(d1_lookback_shift=feature_config.d1_lookback_shift)
    df_merged = merger.merge(df_h4, df_d1, validate=validate_leakage)
    
    return df_merged
