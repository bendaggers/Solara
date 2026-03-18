"""
engine/execution_engine.py — Model Execution Engine
=====================================================
Core of the SAQ processing pipeline.
Dispatches models via priority queue → ThreadPoolExecutor batches.
Collects results, tracks health, returns ModelResultSet.
"""
import time
import importlib
import structlog
from queue import PriorityQueue
from concurrent.futures import as_completed
import pandas as pd

from engine.model_registry import ModelRegistry, ModelRegistryEntry
from engine.worker_pool import WorkerPool
from engine.result_collector import ModelResult, ModelResultSet, RunStatus
from engine.model_health import ModelHealthTracker
from features.feature_validator import FeatureValidator
import config

log = structlog.get_logger(__name__)


def _run_model(
    entry: ModelRegistryEntry,
    featured_df: pd.DataFrame,
    batch_number: int,
) -> ModelResult:
    """
    Execute a single model. Called inside a worker thread.
    All exceptions are caught here — fault isolation guaranteed.
    """
    started = time.monotonic()
    try:
        module_path, class_name = entry.class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        predictor_class = getattr(module, class_name)
        predictor = predictor_class(entry=entry)

        signals = predictor.predict(featured_df.copy())

        elapsed = time.monotonic() - started
        status = RunStatus.SUCCESS if signals else RunStatus.EMPTY

        return ModelResult(
            model_name=entry.name,
            magic=entry.magic,
            timeframe=entry.timeframe,
            status=status,
            signals=signals,
            elapsed_seconds=round(elapsed, 3),
            batch_number=batch_number,
        )

    except Exception as e:
        elapsed = time.monotonic() - started
        log.error(
            "model_execution_failed",
            model=entry.name,
            error=str(e),
            exc_info=True,
        )
        return ModelResult(
            model_name=entry.name,
            magic=entry.magic,
            timeframe=entry.timeframe,
            status=RunStatus.FAILED,
            elapsed_seconds=round(elapsed, 3),
            error_message=str(e),
            batch_number=batch_number,
        )


class ExecutionEngine:
    """Dispatches models in priority-ordered batches via ThreadPoolExecutor."""

    def __init__(self, registry: ModelRegistry, feat_validator: FeatureValidator) -> None:
        self._registry = registry
        self._feat_validator = FeatureValidator()
        self._health = ModelHealthTracker(registry=registry)

    def run(self, timeframe: str, featured_df: pd.DataFrame) -> ModelResultSet:
        """
        Run all enabled models for the given timeframe.

        Args:
            timeframe:   Which pipeline triggered (M5/M15/H1/H4).
            featured_df: Pre-computed features shared to all models.

        Returns:
            ModelResultSet with all results (success, failure, timeout, empty).
        """
        result_set = ModelResultSet(timeframe=timeframe)
        models = self._registry.get_enabled(timeframe)

        if not models:
            log.info("no_models_for_timeframe", timeframe=timeframe)
            return result_set

        # Feature version validation — exclude incompatible models before queue
        validated_models = []
        for entry in models:
            ok, _ = self._feat_validator.validate_model(
                model_name=entry.name,
                feature_version=entry.feature_version,
                featured_df=featured_df,
            )
            if ok:
                validated_models.append(entry)

        if not validated_models:
            log.error("no_valid_models_after_feature_check", timeframe=timeframe)
            return result_set

        # Build priority queue
        queue: PriorityQueue = PriorityQueue()
        for entry in validated_models:
            queue.put((entry.priority, entry.name, entry))

        batch_number = 0
        with WorkerPool(max_workers=config.MAX_CONCURRENT_MODELS, timeframe=timeframe) as pool:
            while not queue.empty():
                batch_number += 1
                batch: list[ModelRegistryEntry] = []
                while len(batch) < config.MAX_CONCURRENT_MODELS and not queue.empty():
                    _, _, entry = queue.get()
                    batch.append(entry)

                log.debug(
                    "batch_dispatched",
                    timeframe=timeframe,
                    batch=batch_number,
                    models=[e.name for e in batch],
                )

                futures = {
                    pool.submit(_run_model, entry, featured_df, batch_number): entry
                    for entry in batch
                }

                for future in as_completed(futures):
                    entry = futures[future]
                    try:
                        result: ModelResult = future.result(timeout=entry.timeout)
                    except TimeoutError:
                        result = ModelResult(
                            model_name=entry.name,
                            magic=entry.magic,
                            timeframe=timeframe,
                            status=RunStatus.TIMEOUT,
                            error_message=f"Exceeded {entry.timeout}s timeout",
                            batch_number=batch_number,
                        )
                        log.warning(
                            "model_timeout",
                            model=entry.name,
                            timeout=entry.timeout,
                        )

                    result_set.results.append(result)
                    self._health.record(result)

        log.info(
            "engine_cycle_complete",
            timeframe=timeframe,
            total=len(result_set.results),
            success=len(result_set.successful()),
            total_signals=len(result_set.all_signals()),
        )
        return result_set
