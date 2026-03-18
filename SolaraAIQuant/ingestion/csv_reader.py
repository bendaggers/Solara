"""
Solara AI Quant - CSV Reader

Reads and parses CSV files exported by MT5 EA.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import logging

from config import ingestion_config

logger = logging.getLogger(__name__)


class CSVReader:
    """
    Reads market data CSV files from MT5 EA.
    
    Handles:
    - UTF-8 encoding with fallbacks
    - Timestamp parsing
    - Missing value handling
    - Column validation
    """
    
    def __init__(self):
        self.required_columns = ingestion_config.required_columns
        self.timestamp_format = ingestion_config.timestamp_format
    
    def read(
        self, 
        file_path: Path,
        symbol_filter: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        Read CSV file into DataFrame.
        
        Args:
            file_path: Path to CSV file
            symbol_filter: Filter to specific symbol (optional)
            
        Returns:
            Tuple of (DataFrame, error_message)
            If successful, error_message is None
        """
        # Check file exists
        if not file_path.exists():
            return None, f"File not found: {file_path}"
        
        # Check file not empty
        if file_path.stat().st_size == 0:
            return None, f"File is empty: {file_path}"
        
        try:
            # Try UTF-8 first, then fallback to latin1
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='latin1')
            
            if df.empty:
                return None, "CSV file has no data rows"
            
            # Normalize column names
            df.columns = df.columns.str.strip().str.lower()
            
            # Filter by symbol if specified
            if symbol_filter and 'symbol' in df.columns:
                df = df[df['symbol'] == symbol_filter]
                if df.empty:
                    return None, f"No data for symbol: {symbol_filter}"
            
            logger.debug(f"Read {len(df)} rows from {file_path.name}")
            return df, None
            
        except pd.errors.EmptyDataError:
            return None, "CSV file is empty or malformed"
        except Exception as e:
            return None, f"Error reading CSV: {str(e)}"
    
    def parse_timestamp(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse timestamp column to datetime.
        
        Args:
            df: DataFrame with 'timestamp' column
            
        Returns:
            DataFrame with parsed timestamps
        """
        if 'timestamp' not in df.columns:
            logger.warning("No timestamp column found")
            return df
        
        try:
            # Try multiple formats
            formats_to_try = [
                self.timestamp_format,
                '%Y.%m.%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%d.%m.%Y %H:%M:%S',
            ]
            
            for fmt in formats_to_try:
                try:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format=fmt)
                    logger.debug(f"Parsed timestamps with format: {fmt}")
                    return df
                except (ValueError, TypeError):
                    continue
            
            # Last resort: let pandas infer
            df['timestamp'] = pd.to_datetime(df['timestamp'], infer_datetime_format=True)
            logger.debug("Parsed timestamps with inferred format")
            
        except Exception as e:
            logger.error(f"Failed to parse timestamps: {e}")
        
        return df
    
    def read_and_parse(
        self,
        file_path: Path,
        symbol_filter: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        Read CSV and parse timestamps in one call.
        
        Args:
            file_path: Path to CSV file
            symbol_filter: Filter to specific symbol (optional)
            
        Returns:
            Tuple of (DataFrame, error_message)
        """
        df, error = self.read(file_path, symbol_filter)
        
        if error:
            return None, error
        
        df = self.parse_timestamp(df)
        
        return df, None
