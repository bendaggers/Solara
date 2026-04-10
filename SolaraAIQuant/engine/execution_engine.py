"""
Solara AI Quant - Execution Engine

Runs ML models in parallel using a thread pool.
Each model runs its own feature engineering before prediction.

Architecture:
- ThreadPoolExecutor with configurable max workers (default 8)
- Each model thread: loads feature engineer → computes features → runs predictor
- Per-model feature engineering isolates each model's feature space completely
- Timeout enforcement per model
- Results collected into ModelResultSet
"""

import time
import importlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
import traceback

from config import execution_config
from .registry import ModelConfig, ModelRegistry, model_registry
from .model_health import ModelHealthTracker, model_health_tracker, RunStatus

logger = logging.getLogger(__name__)


@dataclass
class ModelResult:
    """Result from a single model execution."""
    model_name: str
    magic: int
    status: RunStatus
    predictions: List[Dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_message: Optional[str] = None

    @property
    def has_predictions(self) -> bool:
        return len(self.predictions) > 0


@dataclass
class ModelResultSet:
    """Collection of results from all models in a cycle."""
    timeframe: str
    start_time: datetime
    end_time: Optional[datetime] = None
    results: List[ModelResult] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    @property
    def total_models(self) -> int:
        return len(self.results)

    @property
    def successful_models(self) -> int:
        return sum(1 for r in self.results if r.status == RunStatus.SUCCESS)

    @property
    def failed_models(self) -> int:
        return sum(
            1 for r in self.results
            if r.status in (RunStatus.FAILED, RunStatus.TIMEOUT)
        )

    @property
    def total_predictions(self) -> int:
        return sum(len(r.predictions) for r in self.results)

    def get_all_predictions(self) -> List[Dict]:
        predictions = []
        for result in self.results:
            predictions.extend(result.predictions)
        return predictions


class ExecutionEngine:
    """
    Executes ML models in parallel with per-model feature engineering.

    Flow per model thread:
      1. Load (or cache) the model's feature engineer
      2. Run feature engineer on the merged base DataFrame
      3. Validate output features match what predictor expects
      4. Run predictor.predict()
      5. Record health

    If a model has no feature_engineering_class set, falls back to
    the pre-computed shared DataFrame from Stage 4 (legacy behaviour).
    """

    def __init__(
        self,
        max_workers: int = None,
        registry: ModelRegistry = None,
        health_tracker: ModelHealthTracker = None,
    ):
        self.max_workers = max_workers or execution_config.max_concurrent_models
        self.registry    = registry or model_registry
        self.health_tracker = health_tracker or model_health_tracker

        # Cache loaded predictor instances (keyed by model name)
        self._predictor_cache: Dict[str, Any] = {}
        # Cache loaded feature engineer instances (keyed by model name)
        self._feature_engineer_cache: Dict[str, Any] = {}

    def execute_for_timeframe(
        self,
        timeframe: str,
        df_merged,           # merged base DataFrame (after Stage 3 tf_merger)
        feature_columns: List[str],  # columns available (for legacy fallback check)
    ) -> ModelResultSet:
        """
        Execute all enabled models for a timeframe.

        Args:
            timeframe:       Timeframe being processed (e.g. "H4")
            df_merged:       Merged base DataFrame from Stage 3.
                             Each model's feature engineer runs on this.
            feature_columns: Available column names (for legacy fallback models).

        Returns:
            ModelResultSet with all results
        """
        result_set = ModelResultSet(
            timeframe=timeframe,
            start_time=datetime.utcnow()
        )

        models = self.registry.get_models_for_timeframe(timeframe)
        if not models:
            logger.info(f"No enabled models for timeframe {timeframe}")
            result_set.end_time = datetime.utcnow()
            return result_set

        # Filter to healthy models
        healthy_models = []
        for model in models:
            if self.health_tracker.is_model_healthy(model.name):
                healthy_models.append(model)
            else:
                logger.warning(f"Skipping auto-disabled model: {model.name}")
                result_set.results.append(ModelResult(
                    model_name=model.name,
                    magic=model.magic,
                    status=RunStatus.SKIPPED,
                    error_message="Auto-disabled due to consecutive failures"
                ))

        if not healthy_models:
            logger.warning(f"No healthy models for timeframe {timeframe}")
            result_set.end_time = datetime.utcnow()
            return result_set

        logger.info(f"Executing {len(healthy_models)} models for {timeframe}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_model = {
                executor.submit(
                    self._execute_single_model,
                    model,
                    df_merged,
                    feature_columns,
                ): model
                for model in healthy_models
            }

            for future in as_completed(future_to_model):
                model = future_to_model[future]
                try:
                    result = future.result(timeout=model.timeout)
                    result_set.results.append(result)

                except TimeoutError:
                    logger.error(
                        f"Model '{model.name}' timed out after {model.timeout}s"
                    )
                    result_set.results.append(ModelResult(
                        model_name=model.name,
                        magic=model.magic,
                        status=RunStatus.TIMEOUT,
                        error_message=f"Timeout after {model.timeout}s"
                    ))
                    self.health_tracker.record_run(
                        model.name, model.magic, RunStatus.TIMEOUT,
                        duration_seconds=model.timeout,
                        error_message=f"Timeout after {model.timeout}s"
                    )

                except Exception as e:
                    logger.exception(f"Model '{model.name}' raised exception: {e}")
                    result_set.results.append(ModelResult(
                        model_name=model.name,
                        magic=model.magic,
                        status=RunStatus.FAILED,
                        error_message=str(e)
                    ))
                    self.health_tracker.record_run(
                        model.name, model.magic, RunStatus.FAILED,
                        error_message=str(e)
                    )

        result_set.end_time = datetime.utcnow()
        logger.info(
            f"Execution complete: "
            f"{result_set.successful_models}/{result_set.total_models} successful, "
            f"{result_set.total_predictions} predictions, "
            f"{result_set.duration_seconds:.2f}s"
        )
        return result_set

    def _execute_single_model(
        self,
        model_config: ModelConfig,
        df_merged,
        feature_columns: List[str],
    ) -> ModelResult:
        """
        Execute a single model.

        Steps:
          1. Load predictor
          2. Run model's feature engineer (if configured) OR use df_merged as-is
          3. Validate features
          4. Run prediction
          5. Record health

        Args:
            model_config:    Model configuration (registry entry)
            df_merged:       Merged base DataFrame (after tf_merger Stage 3)
            feature_columns: Available columns in df_merged (for legacy check)
        """
        start_time = time.time()

        try:
            # ── Step 1: Load predictor ─────────────────────────────────────
            predictor = self._get_predictor(model_config)
            if predictor is None:
                return ModelResult(
                    model_name=model_config.name,
                    magic=model_config.magic,
                    status=RunStatus.FAILED,
                    duration_seconds=time.time() - start_time,
                    error_message="Failed to load predictor class"
                )

            # ── Step 2: Feature engineering ───────────────────────────────
            if model_config.has_custom_feature_engineer:
                # Per-model feature engineering path
                feature_engineer = self._get_feature_engineer(model_config)

                if feature_engineer is None:
                    return ModelResult(
                        model_name=model_config.name,
                        magic=model_config.magic,
                        status=RunStatus.FAILED,
                        duration_seconds=time.time() - start_time,
                        error_message=(
                            f"Failed to load feature engineer: "
                            f"{model_config.feature_engineering_class}"
                        )
                    )

                # safe_compute validates input, runs compute(), validates output
                df_featured = feature_engineer.safe_compute(df_merged)

                if df_featured is None:
                    return ModelResult(
                        model_name=model_config.name,
                        magic=model_config.magic,
                        status=RunStatus.SKIPPED,
                        duration_seconds=time.time() - start_time,
                        error_message="Feature engineering failed (see logs for details)"
                    )

                available_cols = list(df_featured.columns)
                logger.debug(
                    f"'{model_config.name}': feature engineer produced "
                    f"{len(df_featured.columns)} columns"
                )

            else:
                # Legacy path: use the shared pre-computed DataFrame as-is
                df_featured    = df_merged
                available_cols = feature_columns
                logger.debug(
                    f"'{model_config.name}': using shared feature DataFrame "
                    f"(no feature_engineering_class set)"
                )

            # ── Step 3: Validate features predictor needs ──────────────────
            required = predictor.get_required_features()
            missing  = set(required) - set(available_cols)

            if missing:
                logger.warning(
                    f"'{model_config.name}': missing features for predictor: {missing}"
                )
                return ModelResult(
                    model_name=model_config.name,
                    magic=model_config.magic,
                    status=RunStatus.SKIPPED,
                    duration_seconds=time.time() - start_time,
                    error_message=f"Missing predictor features: {sorted(missing)[:5]}…"
                )

            # ── Step 3b: Trim to exactly the columns the model needs ────────
            # Keeps column order from required list (matches training order).
            # Any extra columns from the feature engineer or base DataFrame
            # are dropped — the model never sees them.
            # 'symbol' and 'timestamp' are always kept as metadata so
            # predictors can identify which row belongs to which symbol.
            meta_cols = [
                c for c in ('symbol', 'timestamp')
                if c in df_featured.columns and c not in required
            ]
            df_featured = df_featured[meta_cols + required]
            logger.debug(
                f"'{model_config.name}': trimmed df to "
                f"{len(required)} model columns + {len(meta_cols)} meta columns"
            )

            # ── Step 4: Run prediction ─────────────────────────────────────
            predictions = predictor.predict(df_featured, model_config)
            duration    = time.time() - start_time

            status = RunStatus.EMPTY if not predictions else RunStatus.SUCCESS

            # ── Step 5: Record health ──────────────────────────────────────
            self.health_tracker.record_run(
                model_config.name,
                model_config.magic,
                status,
                duration_seconds=duration
            )

            return ModelResult(
                model_name=model_config.name,
                magic=model_config.magic,
                status=status,
                predictions=predictions or [],
                duration_seconds=duration
            )

        except Exception as e:
            duration  = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Model '{model_config.name}' failed: {error_msg}")
            logger.debug(traceback.format_exc())
            self.health_tracker.record_run(
                model_config.name,
                model_config.magic,
                RunStatus.FAILED,
                duration_seconds=duration,
                error_message=error_msg
            )
            return ModelResult(
                model_name=model_config.name,
                magic=model_config.magic,
                status=RunStatus.FAILED,
                duration_seconds=duration,
                error_message=error_msg
            )

    def _get_predictor(self, model_config: ModelConfig):
        """Load or retrieve cached predictor instance."""
        cache_key = model_config.name
        if cache_key in self._predictor_cache:
            return self._predictor_cache[cache_key]

        try:
            module_path, class_name = model_config.class_path.rsplit('.', 1)
            module          = importlib.import_module(module_path)
            predictor_class = getattr(module, class_name)
            predictor       = predictor_class(model_config)
            self._predictor_cache[cache_key] = predictor
            logger.debug(f"Loaded predictor: {model_config.class_path}")
            return predictor
        except ImportError as e:
            logger.error(f"Cannot import predictor module: {e}")
        except AttributeError as e:
            logger.error(f"Predictor class not found: {e}")
        except Exception as e:
            logger.error(f"Error loading predictor: {e}")
        return None

    def _get_feature_engineer(self, model_config: ModelConfig):
        """Load or retrieve cached feature engineer instance."""
        cache_key = model_config.name
        if cache_key in self._feature_engineer_cache:
            return self._feature_engineer_cache[cache_key]

        instance = model_config.load_feature_engineer()
        if instance is not None:
            self._feature_engineer_cache[cache_key] = instance
        return instance

    def clear_caches(self):
        """Clear predictor and feature engineer caches (for hot reload)."""
        self._predictor_cache.clear()
        self._feature_engineer_cache.clear()
        logger.info("Execution engine caches cleared")


# Global instance
execution_engine = ExecutionEngine()
