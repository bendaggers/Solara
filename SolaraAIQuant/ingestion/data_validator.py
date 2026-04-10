"""
Solara AI Quant - Data Validator

Validates market data before processing.
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

from config import ingestion_config

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    df: Optional[pd.DataFrame]
    errors: List[str]
    warnings: List[str]
    rows_before: int
    rows_after: int
    symbols_found: List[str]


class DataValidator:
    """
    Validates market data for quality and completeness.
    
    Validation checks:
    1. Required columns present
    2. No null values in critical columns
    3. OHLC relationships valid (high >= low)
    4. Minimum bars per symbol
    5. Timestamps ascending
    """
    
    def __init__(self):
        self.required_columns = list(ingestion_config.required_columns)
        self.min_bars = ingestion_config.min_bars_per_symbol
        self.drop_invalid_ohlc = ingestion_config.drop_invalid_ohlc
        self.drop_null_symbol = ingestion_config.drop_null_symbol
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """
        Validate DataFrame and clean data.
        
        Args:
            df: Input DataFrame
            
        Returns:
            ValidationResult with cleaned DataFrame
        """
        errors = []
        warnings = []
        rows_before = len(df)
        
        if df is None or df.empty:
            return ValidationResult(
                is_valid=False,
                df=None,
                errors=["DataFrame is empty or None"],
                warnings=[],
                rows_before=0,
                rows_after=0,
                symbols_found=[]
            )
        
        df = df.copy()
        
        if 'pair' in df.columns and 'symbol' not in df.columns:
            df = df.rename(columns={'pair': 'symbol'})
        
        # 1. Check required columns
        missing_cols = self._check_required_columns(df)
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            return ValidationResult(
                is_valid=False,
                df=None,
                errors=errors,
                warnings=warnings,
                rows_before=rows_before,
                rows_after=0,
                symbols_found=[]
            )
        
        # 2. Drop null symbols
        if self.drop_null_symbol and 'symbol' in df.columns:
            null_symbols = df['symbol'].isna().sum()
            if null_symbols > 0:
                warnings.append(f"Dropped {null_symbols} rows with null symbol")
                df = df.dropna(subset=['symbol'])
        
        # 3. Drop invalid OHLC
        if self.drop_invalid_ohlc:
            df, invalid_count = self._fix_ohlc(df)
            if invalid_count > 0:
                warnings.append(f"Dropped {invalid_count} rows with invalid OHLC")
        
        # 4. Drop null in OHLC
        ohlc_cols = ['open', 'high', 'low', 'close']
        existing_ohlc = [c for c in ohlc_cols if c in df.columns]
        if existing_ohlc:
            null_ohlc = df[existing_ohlc].isna().any(axis=1).sum()
            if null_ohlc > 0:
                warnings.append(f"Dropped {null_ohlc} rows with null OHLC")
                df = df.dropna(subset=existing_ohlc)
        
        # 5. Check minimum bars per symbol
        if 'symbol' in df.columns:
            df, excluded = self._filter_min_bars(df)
            if excluded:
                warnings.append(f"Excluded symbols with < {self.min_bars} bars: {excluded}")
        
        # 6. Sort by timestamp
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Get symbols found
        symbols_found = []
        if 'symbol' in df.columns:
            symbols_found = df['symbol'].unique().tolist()
        
        rows_after = len(df)
        
        if rows_after == 0:
            errors.append("No valid data rows after validation")
            return ValidationResult(
                is_valid=False,
                df=None,
                errors=errors,
                warnings=warnings,
                rows_before=rows_before,
                rows_after=0,
                symbols_found=[]
            )
        
        logger.info(f"Validation: {rows_before} → {rows_after} rows, {len(symbols_found)} symbols")
        
        return ValidationResult(
            is_valid=True,
            df=df,
            errors=errors,
            warnings=warnings,
            rows_before=rows_before,
            rows_after=rows_after,
            symbols_found=symbols_found
        )
    
    def _check_required_columns(self, df: pd.DataFrame) -> List[str]:
        """Check for missing required columns."""
        # Normalize column names
        df_cols = set(df.columns.str.lower())
        required = set(c.lower() for c in self.required_columns)
        
        missing = required - df_cols
        return list(missing)
    
    def _fix_ohlc(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """Fix or remove invalid OHLC rows."""
        if 'high' not in df.columns or 'low' not in df.columns:
            return df, 0
        
        # high must be >= low
        invalid_mask = df['high'] < df['low']
        invalid_count = invalid_mask.sum()
        
        if invalid_count > 0:
            df = df[~invalid_mask]
        
        return df, invalid_count
    
    def _filter_min_bars(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Filter out symbols with too few bars."""
        if 'symbol' not in df.columns:
            return df, []
        
        symbol_counts = df['symbol'].value_counts()
        excluded_symbols = symbol_counts[symbol_counts < self.min_bars].index.tolist()
        
        if excluded_symbols:
            df = df[~df['symbol'].isin(excluded_symbols)]
        
        return df, excluded_symbols
    
    def quick_check(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Quick validation check without cleaning.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if df is None or df.empty:
            return False, "DataFrame is empty"
        
        missing = self._check_required_columns(df)
        if missing:
            return False, f"Missing columns: {missing}"
        
        return True, ""
