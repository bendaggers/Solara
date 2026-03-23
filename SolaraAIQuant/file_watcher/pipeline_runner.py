"""
Solara AI Quant - Pipeline Runner

Orchestrates the full processing pipeline when a CSV file changes.
Uses saq_log.render_pipeline_block() so each timeframe's status
updates IN PLACE — no repeated scrolling output.
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
from logger import saq_log

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
    Multi-TF merging is driven by each model's merge_timeframes field.
    """

    def __init__(self):
        self.csv_reader = CSVReader()
        self.data_validator = DataValidator()

    def run(self, file_path: Path, timeframe: Timeframe) -> PipelineResult:
        start_time = datetime.now()

        # Early exit — no models for this TF
        from engine.registry import model_registry
        models_for_tf = model_registry.get_models_for_timeframe(timeframe.value)
        if not models_for_tf:
            logger.debug(f"No enabled models for {timeframe.value} — skipping")
            return PipelineResult(
                timeframe=timeframe.value, success=True,
                start_time=start_time, end_time=datetime.now(),
                duration_seconds=0, rows_processed=0,
                symbols_found=[], models_run=0,
                signals_generated=0, trades_executed=0,
            )

        # Stage state accumulator — built up as stages complete
        stages  = []
        signals = []

        result = PipelineResult(
            timeframe=timeframe.value, success=False,
            start_time=start_time, end_time=start_time,
            duration_seconds=0, rows_processed=0,
            symbols_found=[], models_run=0,
            signals_generated=0, trades_executed=0,
        )

        try:
            # ── Stage 1: INGEST ───────────────────────────────────────────────
            df, error = self._stage_ingest(file_path)
            if error:
                stages.append(dict(step=1, name="ingest", status="error", detail=error))
                result.error_message = f"Ingest failed: {error}"
                return self._finalize(result, stages, signals, start_time)

            # ── Stage 2: VALIDATE ─────────────────────────────────────────────
            validation = self._stage_validate(df)
            if not validation.is_valid:
                stages.append(dict(step=1, name="ingest",   status="ok",
                    detail=f"{len(df)} rows"))
                stages.append(dict(step=2, name="validate", status="error",
                    detail=" · ".join(str(e) for e in validation.errors)))
                result.error_message = f"Validation failed: {validation.errors}"
                return self._finalize(result, stages, signals, start_time)

            df = validation.df
            result.rows_processed = len(df)
            result.symbols_found  = validation.symbols_found

            stages.append(dict(step=1, name="ingest",   status="ok",
                detail=f"{len(df)} rows · {len(validation.symbols_found)} symbols"))
            stages.append(dict(step=2, name="validate", status="ok",
                detail=f"{validation.rows_before} → {validation.rows_after} rows · all clean"))

            # ── Stage 3: MULTI-TF MERGE ───────────────────────────────────────
            df, merge_detail, merge_status = self._stage_merge(
                df, timeframe, models_for_tf
            )
            stages.append(dict(step=3, name="merge", status=merge_status,
                detail=merge_detail))

            # ── Stage 4: FEATURES ─────────────────────────────────────────────
            has_secondary = any(
                c.endswith("_close")
                for c in df.columns
                if "_" in c and not c.startswith("prev")
            )
            df = feature_engineer.compute_all_features(df, include_d1=has_secondary)
            stages.append(dict(step=4, name="features", status="ok",
                detail=f"{len(df.columns)} columns computed"))

            # ── Stage 5: MODELS ───────────────────────────────────────────────
            result_set = self._stage_models(df, timeframe)
            result.models_run = result_set.total_models if result_set else 0

            if result_set and result_set.successful_models > 0:
                model_status = "ok"
            elif result_set and result_set.total_models > 0:
                model_status = "error"
            else:
                model_status = "skip"

            stages.append(dict(step=5, name="models", status=model_status,
                detail=(
                    f"{result_set.successful_models}/{result_set.total_models} ran · "
                    f"{result_set.total_predictions} predictions · "
                    f"{result_set.duration_seconds:.2f}s"
                ) if result_set else "no result"))

            # ── Stage 6: SIGNALS ──────────────────────────────────────────────
            valid_signals = self._stage_signals(result_set)
            result.signals_generated = len(valid_signals)

            if valid_signals:
                stages.append(dict(step=6, name="signals", status="ok",
                    detail=f"{len(valid_signals)} valid from "
                           f"{result_set.total_predictions if result_set else 0} predictions"))
                for sig in valid_signals:
                    features = sig.raw_signal.features or {}
                    rsi = features.get("rsi_value", 0)
                    mtf = features.get("mtf_confluence_score", 0)
                    signals.append(dict(
                        symbol=sig.symbol,
                        direction=sig.direction.value,
                        confidence=sig.combined_confidence,
                        detail=f"RSI {rsi:.1f} · MTF {mtf:.2f}" if rsi else "",
                    ))
            else:
                no_pred = (result_set.total_predictions == 0) if result_set else True
                stages.append(dict(step=6, name="signals", status="skip",
                    detail="no predictions" if no_pred
                    else "none passed conflict check"))

            # ── Stage 7: RISK ─────────────────────────────────────────────────
            approved = self._stage_risk(valid_signals)
            stages.append(dict(step=7, name="risk", status="skip",
                detail=f"{len(valid_signals)} pending — not implemented yet"
                if valid_signals else "skipped"))

            # ── Stage 8: EXECUTE ──────────────────────────────────────────────
            trades = self._stage_execute(approved)
            result.trades_executed = len(trades)
            stages.append(dict(step=8, name="execute", status="skip",
                detail="MT5 not connected (dev mode)"
                if not trades else f"{len(trades)} trades placed"))

            result.success = True

        except Exception as e:
            logger.exception(f"Pipeline crashed in {timeframe.value}: {e}")
            stages.append(dict(step=0, name="crash", status="error",
                detail=str(e)[:80]))
            result.error_message = str(e)

        return self._finalize(result, stages, signals, start_time)

    def _finalize(
        self,
        result: PipelineResult,
        stages: list,
        signals: list,
        start_time: datetime,
    ) -> PipelineResult:
        result.end_time = datetime.now()
        result.duration_seconds = (
            result.end_time - result.start_time
        ).total_seconds()

        if not result.success:
            outcome = "failed"
            detail  = (result.error_message or "")[:60]
        elif result.signals_generated > 0:
            n       = result.signals_generated
            outcome = f"{n} signal{'s' if n > 1 else ''}"
            syms    = " · ".join(s['symbol'] for s in signals[:4])
            detail  = syms
        else:
            outcome = "no signal"
            detail  = "market not aligned"

        # Render the block in-place for this timeframe
        saq_log.render_pipeline_block(
            timeframe=result.timeframe,
            stages=stages,
            signals=signals,
            outcome=outcome,
            elapsed=result.duration_seconds,
            footer_detail=detail,
        )
        saq_log.watching()
        return result

    # =========================================================================
    # Stage implementations
    # =========================================================================

    def _stage_ingest(self, file_path: Path):
        df, error = self.csv_reader.read_and_parse(file_path)
        if error:
            logger.error(f"Ingest failed: {error}")
            return None, error
        return df, None

    def _stage_validate(self, df):
        return self.data_validator.validate(df)

    def _stage_merge(self, df, timeframe: Timeframe, models) -> tuple:
        from features.tf_merger import merge_timeframes_for_models

        merged_df, merged_tfs = merge_timeframes_for_models(
            base_df=df, base_tf=timeframe.value, models=models
        )

        if merged_tfs:
            added = len([c for c in merged_df.columns if c not in df.columns])
            return merged_df, f"+{added} {'/'.join(merged_tfs)} columns merged", "ok"

        needed = []
        for m in models:
            for tf in m.get_merge_timeframe_strings():
                if tf.upper() != timeframe.value.upper() and tf not in needed:
                    needed.append(tf)

        if needed:
            return merged_df, f"{'/'.join(needed)} CSV not found — skipped", "warn"
        return merged_df, "no extra TFs required", "ok"

    def _stage_models(self, df, timeframe: Timeframe):
        from engine.execution_engine import ExecutionEngine
        from engine.registry import model_registry

        engine = ExecutionEngine(registry=model_registry)
        return engine.execute_for_timeframe(
            timeframe=timeframe.value,
            df_features=df,
            feature_columns=list(df.columns),
        )

    def _stage_signals(self, result_set) -> List:
        if result_set is None or result_set.total_predictions == 0:
            return []
        from signals.aggregator import SignalAggregator
        return SignalAggregator().aggregate(result_set)

    def _stage_risk(self, signals: List) -> List:
        return []

    def _stage_execute(self, approved: List) -> List:
        return []


pipeline_runner = PipelineRunner()
