"""
Solara AI Quant - Pipeline Runner

Orchestrates the full processing pipeline when a CSV file changes:
1. Data ingestion (read CSV)
2. Data validation
3. H4/D1 merge (if applicable)
4. Feature engineering
5. Model execution
6. Signal aggregation
7. Risk check
8. Trade execution

This is the core orchestration layer between file events and model execution.
"""

import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from config import (
    ingestion_config, feature_config, MQL5_FILES_DIR, TIMEFRAMES
)
from ingestion import CSVReader, DataValidator
from features import H4D1Merger, feature_engineer
from .cycle_lock import Timeframe

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""
    timeframe: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    rows_processed: int
    symbols_found: List[str]
    models_run: int
    signals_generated: int
    trades_executed: int
    error_message: Optional[str] = None


class PipelineRunner:
    """
    Runs the full processing pipeline for a timeframe.
    
    The pipeline is triggered when a CSV file is modified.
    It processes the data through all stages and executes trades.
    
    Pipeline stages:
    1. INGEST: Read CSV file
    2. VALIDATE: Check data quality
    3. MERGE: Merge D1 data (for H4+ timeframes)
    4. FEATURES: Compute technical indicators
    5. MODELS: Run ML models for predictions
    6. SIGNALS: Aggregate and filter signals
    7. RISK: Apply risk management rules
    8. EXECUTE: Place trades via MT5
    """
    
    def __init__(self):
        self.csv_reader = CSVReader()
        self.data_validator = DataValidator()
        self.h4d1_merger = H4D1Merger(d1_lookback_shift=feature_config.d1_lookback_shift)
        
        # D1 data cache (loaded once, reused for H4)
        self._d1_cache: Optional[Any] = None
        self._d1_cache_time: Optional[datetime] = None
        self._d1_cache_ttl_seconds = 3600  # 1 hour
    
    def run(self, file_path: Path, timeframe: Timeframe) -> PipelineResult:
        """
        Run the full pipeline for a file change event.
        
        Args:
            file_path: Path to the changed CSV file
            timeframe: Timeframe being processed
            
        Returns:
            PipelineResult with execution details
        """
        start_time = datetime.now()
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"  PIPELINE START: {timeframe.value}")
        logger.info(f"  File: {file_path.name}")
        logger.info(f"  Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")
        
        result = PipelineResult(
            timeframe=timeframe.value,
            success=False,
            start_time=start_time,
            end_time=start_time,
            duration_seconds=0,
            rows_processed=0,
            symbols_found=[],
            models_run=0,
            signals_generated=0,
            trades_executed=0
        )
        
        try:
            # Stage 1: INGEST
            df, error = self._stage_ingest(file_path)
            if error:
                result.error_message = f"Ingest failed: {error}"
                return self._finalize_result(result)
            
            # Stage 2: VALIDATE
            validation = self._stage_validate(df)
            if not validation.is_valid:
                result.error_message = f"Validation failed: {validation.errors}"
                return self._finalize_result(result)
            
            df = validation.df
            result.rows_processed = len(df)
            result.symbols_found = validation.symbols_found
            
            # Stage 3: MERGE (D1 data for H4+ timeframes)
            if timeframe in [Timeframe.H4, Timeframe.H1]:
                df, error = self._stage_merge_d1(df, timeframe)
                if error:
                    logger.warning(f"D1 merge warning: {error}")
                    # Continue without D1 data - not fatal
            
            # Stage 4: FEATURES
            df = self._stage_features(df, include_d1=(timeframe in [Timeframe.H4, Timeframe.H1]))
            
            # Stage 5: MODELS
            # (Placeholder - will be implemented in engine module)
            model_results = self._stage_models(df, timeframe)
            result.models_run = len(model_results)
            
            # Stage 6: SIGNALS
            # (Placeholder - will be implemented in signals module)
            signals = self._stage_signals(model_results)
            result.signals_generated = len(signals)
            
            # Stage 7: RISK
            # (Placeholder - will be implemented in execution module)
            approved_signals = self._stage_risk(signals)
            
            # Stage 8: EXECUTE
            # (Placeholder - will be implemented in execution module)
            trades = self._stage_execute(approved_signals)
            result.trades_executed = len(trades)
            
            result.success = True
            
        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            result.error_message = str(e)
        
        return self._finalize_result(result)
    
    def _finalize_result(self, result: PipelineResult) -> PipelineResult:
        """Finalize result with timing and logging."""
        result.end_time = datetime.now()
        result.duration_seconds = (result.end_time - result.start_time).total_seconds()
        
        status = "✓ SUCCESS" if result.success else "✗ FAILED"
        
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"  PIPELINE {status}")
        logger.info(f"  Duration: {result.duration_seconds:.2f}s")
        logger.info(f"  Rows: {result.rows_processed}")
        logger.info(f"  Models: {result.models_run}")
        logger.info(f"  Signals: {result.signals_generated}")
        logger.info(f"  Trades: {result.trades_executed}")
        if result.error_message:
            logger.info(f"  Error: {result.error_message}")
        logger.info(f"{'='*60}")
        logger.info(f"")
        
        return result
    
    # =========================================================================
    # Pipeline Stages
    # =========================================================================
    
    def _stage_ingest(self, file_path: Path):
        """Stage 1: Read CSV file."""
        logger.info(f"  [1/8] INGEST: Reading {file_path.name}...")
        
        df, error = self.csv_reader.read_and_parse(file_path)
        
        if error:
            logger.error(f"       Failed: {error}")
            return None, error
        
        logger.info(f"       Read {len(df)} rows")
        return df, None
    
    def _stage_validate(self, df):
        """Stage 2: Validate data quality."""
        logger.info(f"  [2/8] VALIDATE: Checking data quality...")
        
        result = self.data_validator.validate(df)
        
        if result.is_valid:
            logger.info(f"       Valid: {result.rows_after} rows, {len(result.symbols_found)} symbols")
        else:
            logger.error(f"       Failed: {result.errors}")
        
        if result.warnings:
            for warning in result.warnings:
                logger.warning(f"       Warning: {warning}")
        
        return result
    
    def _stage_merge_d1(self, df_h4, timeframe: Timeframe):
        """Stage 3: Merge D1 data."""
        logger.info(f"  [3/8] MERGE: Loading D1 data...")
        
        # Load D1 data (with caching)
        df_d1 = self._get_d1_data()
        
        if df_d1 is None:
            return df_h4, "D1 data not available"
        
        try:
            df_merged = self.h4d1_merger.merge(df_h4, df_d1, validate=True)
            
            d1_cols = sum(1 for c in df_merged.columns if c.startswith('d1_'))
            logger.info(f"       Merged: {d1_cols} D1 columns added")
            
            return df_merged, None
            
        except ValueError as e:
            logger.error(f"       Merge failed: {e}")
            return df_h4, str(e)
    
    def _get_d1_data(self):
        """Get D1 data with caching."""
        # Check cache validity
        if self._d1_cache is not None and self._d1_cache_time is not None:
            age = (datetime.now() - self._d1_cache_time).total_seconds()
            if age < self._d1_cache_ttl_seconds:
                logger.debug(f"       Using cached D1 data (age: {age:.0f}s)")
                return self._d1_cache
        
        # Load D1 data
        d1_config = TIMEFRAMES.get('D1')
        if not d1_config:
            return None
        
        d1_path = MQL5_FILES_DIR / d1_config['csv_file']
        
        if not d1_path.exists():
            logger.warning(f"       D1 file not found: {d1_path}")
            return None
        
        df_d1, error = self.csv_reader.read_and_parse(d1_path)
        
        if error:
            logger.warning(f"       D1 read error: {error}")
            return None
        
        # Update cache
        self._d1_cache = df_d1
        self._d1_cache_time = datetime.now()
        
        logger.info(f"       Loaded D1: {len(df_d1)} rows")
        return df_d1
    
    def _stage_features(self, df, include_d1: bool = True):
        """Stage 4: Compute features."""
        logger.info(f"  [4/8] FEATURES: Computing indicators...")
        
        df = feature_engineer.compute_all_features(df, include_d1=include_d1)
        
        feature_count = len(df.columns)
        logger.info(f"       Computed: {feature_count} total columns")
        
        return df
    
    def _stage_models(self, df, timeframe: Timeframe) -> List[Dict]:
        """
        Stage 5: Run ML models.
        
        TODO: Implement when engine module is ready.
        Will:
        - Load enabled models for this timeframe
        - Dispatch to worker pool
        - Collect predictions
        """
        logger.info(f"  [5/8] MODELS: Running predictions...")
        logger.info(f"       (Not implemented yet)")
        return []
    
    def _stage_signals(self, model_results: List[Dict]) -> List[Dict]:
        """
        Stage 6: Aggregate signals.
        
        TODO: Implement when signals module is ready.
        Will:
        - Convert model outputs to signals
        - Apply conflict detection
        - Filter by confidence threshold
        """
        logger.info(f"  [6/8] SIGNALS: Aggregating...")
        logger.info(f"       (Not implemented yet)")
        return []
    
    def _stage_risk(self, signals: List[Dict]) -> List[Dict]:
        """
        Stage 7: Apply risk management.
        
        TODO: Implement when execution module is ready.
        Will:
        - Check drawdown limit
        - Check daily trade count
        - Check position limits
        - Calculate lot size
        """
        logger.info(f"  [7/8] RISK: Checking rules...")
        logger.info(f"       (Not implemented yet)")
        return []
    
    def _stage_execute(self, approved_signals: List[Dict]) -> List[Dict]:
        """
        Stage 8: Execute trades.
        
        TODO: Implement when execution module is ready.
        Will:
        - Place orders via MT5
        - Handle retries
        - Log results
        """
        logger.info(f"  [8/8] EXECUTE: Placing trades...")
        logger.info(f"       (Not implemented yet)")
        return []
    
    def clear_d1_cache(self):
        """Clear the D1 data cache."""
        self._d1_cache = None
        self._d1_cache_time = None
        logger.info("D1 cache cleared")


# Global instance
pipeline_runner = PipelineRunner()
