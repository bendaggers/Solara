"""
Solara AI Quant - Pipeline Runner

Orchestrates the full processing pipeline when a CSV file changes:
1. Data ingestion (read CSV)
2. Data validation
3. Multi-TF merge (per model config — replaces hardcoded H4/D1 merge)
4. Feature engineering
5. Model execution
6. Signal aggregation
7. Risk check       (TODO)
8. Trade execution  (TODO)
"""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

from config import feature_config
from ingestion import CSVReader, DataValidator
from features import feature_engineer
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

    Only fires if at least one model is registered for the trigger TF.
    Multi-TF merging is driven entirely by each model's merge_timeframes
    field — no hardcoded TF logic here.
    """

    def __init__(self):
        self.csv_reader = CSVReader()
        self.data_validator = DataValidator()

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

        # ── Early exit: no models for this TF
        from engine.registry import model_registry
        models_for_tf = model_registry.get_models_for_timeframe(timeframe.value)
        if not models_for_tf:
            logger.debug(
                f"No enabled models for {timeframe.value} — skipping pipeline"
            )
            return PipelineResult(
                timeframe=timeframe.value,
                success=True,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=0,
                rows_processed=0,
                symbols_found=[],
                models_run=0,
                signals_generated=0,
                trades_executed=0,
            )

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  PIPELINE START: {timeframe.value}")
        logger.info(f"  File: {file_path.name}")
        logger.info(f"  Models: {len(models_for_tf)} enabled")
        logger.info(f"  Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

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
            trades_executed=0,
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

            # Stage 3: MULTI-TF MERGE
            # Each model declares which extra TFs it needs via merge_timeframes.
            # We take the union across all triggered models and merge once.
            df = self._stage_merge(df, timeframe, models_for_tf)

            # Stage 4: FEATURES
            has_secondary_data = any(
                col.endswith('_close')
                for col in df.columns
                if '_' in col and not col.startswith('prev')
            )
            df = self._stage_features(df, include_d1=has_secondary_data)

            # Stage 5: MODELS
            result_set = self._stage_models(df, timeframe)
            result.models_run = result_set.total_models if result_set else 0

            # Stage 6: SIGNALS
            signals = self._stage_signals(result_set)
            result.signals_generated = len(signals)

            # Stage 7: RISK
            approved_signals = self._stage_risk(signals)

            # Stage 8: EXECUTE
            trades = self._stage_execute(approved_signals)
            result.trades_executed = len(trades)

            result.success = True

        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            result.error_message = str(e)

        return self._finalize_result(result)

    def _finalize_result(self, result: PipelineResult) -> PipelineResult:
        result.end_time = datetime.now()
        result.duration_seconds = (
            result.end_time - result.start_time
        ).total_seconds()

        status = "✓ SUCCESS" if result.success else "✗ FAILED"

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  PIPELINE {status}")
        logger.info(f"  Duration: {result.duration_seconds:.2f}s")
        logger.info(f"  Rows: {result.rows_processed}")
        logger.info(f"  Models: {result.models_run}")
        logger.info(f"  Signals: {result.signals_generated}")
        logger.info(f"  Trades: {result.trades_executed}")
        if result.error_message:
            logger.info(f"  Error: {result.error_message}")
        logger.info("=" * 60)
        logger.info("")

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
            logger.info(
                f"       Valid: {result.rows_after} rows, "
                f"{len(result.symbols_found)} symbols"
            )
        else:
            logger.error(f"       Failed: {result.errors}")
        if result.warnings:
            for w in result.warnings:
                logger.warning(f"       Warning: {w}")
        return result

    def _stage_merge(self, df, timeframe: Timeframe, models) -> object:
        """
        Stage 3: Merge additional TF data per model requirements.

        Takes the union of merge_timeframes across all triggered models
        and merges them all into the base DataFrame in one pass.
        """
        from features.tf_merger import merge_timeframes_for_models

        merged_df, merged_tfs = merge_timeframes_for_models(
            base_df=df,
            base_tf=timeframe.value,
            models=models,
        )

        if merged_tfs:
            logger.info(f"  [3/8] MERGE: Merged {merged_tfs} into {timeframe.value}")
            added = [c for c in merged_df.columns if c not in df.columns]
            logger.info(f"       Added {len(added)} columns")
        else:
            logger.info(f"  [3/8] MERGE: No extra TFs required — skipped")

        return merged_df

    def _stage_features(self, df, include_d1: bool = False):
        """Stage 4: Compute features."""
        logger.info(f"  [4/8] FEATURES: Computing indicators...")
        df = feature_engineer.compute_all_features(df, include_d1=include_d1)
        logger.info(f"       Computed: {len(df.columns)} total columns")
        return df

    def _stage_models(self, df, timeframe: Timeframe):
        """Stage 5: Run ML models via the execution engine."""
        logger.info(f"  [5/8] MODELS: Running predictions...")

        from engine.execution_engine import ExecutionEngine
        from engine.registry import model_registry

        engine = ExecutionEngine(registry=model_registry)
        result_set = engine.execute_for_timeframe(
            timeframe=timeframe.value,
            df_features=df,
            feature_columns=list(df.columns),
        )

        logger.info(
            f"       {result_set.successful_models}/{result_set.total_models} "
            f"models succeeded, {result_set.total_predictions} predictions"
        )
        return result_set

    def _stage_signals(self, result_set) -> List:
        """Stage 6: Aggregate predictions into validated signals."""
        logger.info(f"  [6/8] SIGNALS: Aggregating...")

        if result_set is None or result_set.total_predictions == 0:
            logger.info(f"       No predictions to aggregate")
            return []

        from signals.aggregator import SignalAggregator
        aggregator = SignalAggregator()
        valid_signals = aggregator.aggregate(result_set)

        if valid_signals:
            for sig in valid_signals:
                logger.info(
                    f"       ► {sig.symbol} {sig.direction.value} "
                    f"conf={sig.combined_confidence:.3f} "
                    f"model={sig.contributing_models}"
                )
        else:
            logger.info(f"       No valid signals after conflict check")

        logger.info(
            f"       {len(valid_signals)} valid / "
            f"{result_set.total_predictions} total predictions"
        )
        return valid_signals

    def _stage_risk(self, signals: List) -> List:
        """Stage 7: Apply risk management. (TODO)"""
        logger.info(f"  [7/8] RISK: Checking rules...")
        if not signals:
            logger.info(f"       No signals to check")
            return []
        logger.info(f"       {len(signals)} signal(s) pending — (not implemented yet)")
        return []

    def _stage_execute(self, approved_signals: List) -> List:
        """Stage 8: Execute trades. (TODO)"""
        logger.info(f"  [8/8] EXECUTE: Placing trades...")
        if not approved_signals:
            logger.info(f"       No approved signals to execute")
            return []
        logger.info(f"       (not implemented yet)")
        return []


# Global instance
pipeline_runner = PipelineRunner()
