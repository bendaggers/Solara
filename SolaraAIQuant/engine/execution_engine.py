"""
Solara AI Quant - Execution Engine

Runs ML models in parallel using a thread pool.
Collects predictions and handles timeouts/failures.

Architecture:
- ThreadPoolExecutor with configurable max workers (default 8)
- Each model runs in its own thread
- Timeout enforcement per model
- Results collected into ModelResultSet
"""

import time
import importlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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
        return sum(1 for r in self.results 
                   if r.status in (RunStatus.FAILED, RunStatus.TIMEOUT))
    
    @property
    def total_predictions(self) -> int:
        return sum(len(r.predictions) for r in self.results)
    
    def get_all_predictions(self) -> List[Dict]:
        """Get all predictions from all models."""
        predictions = []
        for result in self.results:
            predictions.extend(result.predictions)
        return predictions


class ExecutionEngine:
    """
    Executes ML models in parallel.
    
    Features:
    - Thread pool for concurrent execution
    - Timeout enforcement
    - Health tracking and auto-disable
    - Feature version validation
    - Predictor class loading
    """
    
    def __init__(
        self,
        max_workers: int = None,
        registry: ModelRegistry = None,
        health_tracker: ModelHealthTracker = None
    ):
        self.max_workers = max_workers or execution_config.max_concurrent_models
        self.registry = registry or model_registry
        self.health_tracker = health_tracker or model_health_tracker
        
        # Cache for loaded predictor classes
        self._predictor_cache: Dict[str, Any] = {}
    
    def execute_for_timeframe(
        self,
        timeframe: str,
        df_features,
        feature_columns: List[str]
    ) -> ModelResultSet:
        """
        Execute all enabled models for a timeframe.
        
        Args:
            timeframe: Timeframe being processed (e.g., "H4")
            df_features: DataFrame with computed features
            feature_columns: List of available feature columns
            
        Returns:
            ModelResultSet with all results
        """
        result_set = ModelResultSet(
            timeframe=timeframe,
            start_time=datetime.utcnow()
        )
        
        # Get models for this timeframe
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
        
        # Execute models in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs
            future_to_model = {
                executor.submit(
                    self._execute_single_model,
                    model,
                    df_features,
                    feature_columns
                ): model
                for model in healthy_models
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_model):
                model = future_to_model[future]
                
                try:
                    result = future.result(timeout=model.timeout)
                    result_set.results.append(result)
                    
                except TimeoutError:
                    logger.error(f"Model '{model.name}' timed out after {model.timeout}s")
                    result = ModelResult(
                        model_name=model.name,
                        magic=model.magic,
                        status=RunStatus.TIMEOUT,
                        error_message=f"Timeout after {model.timeout}s"
                    )
                    result_set.results.append(result)
                    
                    # Record timeout
                    self.health_tracker.record_run(
                        model.name, model.magic, RunStatus.TIMEOUT,
                        duration_seconds=model.timeout,
                        error_message=f"Timeout after {model.timeout}s"
                    )
                    
                except Exception as e:
                    logger.exception(f"Model '{model.name}' raised exception: {e}")
                    result = ModelResult(
                        model_name=model.name,
                        magic=model.magic,
                        status=RunStatus.FAILED,
                        error_message=str(e)
                    )
                    result_set.results.append(result)
                    
                    # Record failure
                    self.health_tracker.record_run(
                        model.name, model.magic, RunStatus.FAILED,
                        error_message=str(e)
                    )
        
        result_set.end_time = datetime.utcnow()
        
        # Log summary
        logger.info(
            f"Execution complete: {result_set.successful_models}/{result_set.total_models} "
            f"successful, {result_set.total_predictions} predictions, "
            f"{result_set.duration_seconds:.2f}s"
        )
        
        return result_set
    
    def _execute_single_model(
        self,
        model_config: ModelConfig,
        df_features,
        feature_columns: List[str]
    ) -> ModelResult:
        """
        Execute a single model.
        
        Args:
            model_config: Model configuration
            df_features: DataFrame with features
            feature_columns: Available feature columns
            
        Returns:
            ModelResult with predictions or error
        """
        start_time = time.time()
        
        try:
            # 1. Load predictor class
            predictor = self._get_predictor(model_config)
            
            if predictor is None:
                return ModelResult(
                    model_name=model_config.name,
                    magic=model_config.magic,
                    status=RunStatus.FAILED,
                    duration_seconds=time.time() - start_time,
                    error_message="Failed to load predictor"
                )
            
            # 2. Validate features
            required_features = predictor.get_required_features()
            missing = set(required_features) - set(feature_columns)
            
            if missing:
                logger.warning(
                    f"Model '{model_config.name}' missing features: {missing}"
                )
                return ModelResult(
                    model_name=model_config.name,
                    magic=model_config.magic,
                    status=RunStatus.SKIPPED,
                    duration_seconds=time.time() - start_time,
                    error_message=f"Missing features: {list(missing)[:5]}..."
                )
            
            # 3. Run prediction
            predictions = predictor.predict(df_features, model_config)
            
            duration = time.time() - start_time
            
            # 4. Determine status
            if predictions is None or len(predictions) == 0:
                status = RunStatus.EMPTY
            else:
                status = RunStatus.SUCCESS
            
            # 5. Record health
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
            duration = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            logger.error(f"Model '{model_config.name}' failed: {error_msg}")
            logger.debug(traceback.format_exc())
            
            # Record failure
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
        """
        Load or retrieve cached predictor instance.
        
        Args:
            model_config: Model configuration
            
        Returns:
            Predictor instance or None on error
        """
        cache_key = model_config.name
        
        # Check cache
        if cache_key in self._predictor_cache:
            return self._predictor_cache[cache_key]
        
        try:
            # Parse class path
            # e.g., "predictors.stella_alpha_long.StellaAlphaLongPredictor"
            module_path, class_name = model_config.class_path.rsplit('.', 1)
            
            # Import module
            module = importlib.import_module(module_path)
            
            # Get class
            predictor_class = getattr(module, class_name)
            
            # Instantiate
            predictor = predictor_class(model_config)
            
            # Cache
            self._predictor_cache[cache_key] = predictor
            
            logger.debug(f"Loaded predictor: {model_config.class_path}")
            
            return predictor
            
        except ImportError as e:
            logger.error(f"Cannot import predictor module: {e}")
            return None
        except AttributeError as e:
            logger.error(f"Predictor class not found: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading predictor: {e}")
            return None
    
    def clear_predictor_cache(self):
        """Clear the predictor cache (for hot reload)."""
        self._predictor_cache.clear()
        logger.info("Predictor cache cleared")


# Global instance
execution_engine = ExecutionEngine()
