"""
watchdog/pipeline_runner.py — Pipeline Orchestrator
=====================================================
Executes the full cycle for one timeframe event:
  1. Ingest  → load + validate CSV
  2. Feature → compute all features (once, shared)
  3. Engine  → run models via worker pool
  4. Signals → aggregate + conflict check
  5. Risk    → pre-trade checks
  6. Execute → place orders via MT5
"""
import time
import structlog
from ingestion.data_loader import DataLoader
from ingestion.data_validator import DataValidationError
from features.feature_engineer import FeatureEngineer
from features.feature_validator import FeatureValidator
from engine.execution_engine import ExecutionEngine
from signals.signal_aggregator import SignalAggregator
from execution.risk_manager import RiskManager
from execution.trade_executor import TradeExecutor

log = structlog.get_logger(__name__)


class PipelineRunner:
    """Runs the complete SAQ pipeline for a single timeframe event."""

    def __init__(self, mt5_manager, registry) -> None:
        self._mt5 = mt5_manager
        self._registry = registry
        self._loader = DataLoader()
        self._features = FeatureEngineer()
        self._feat_validator = FeatureValidator()
        self._engine = ExecutionEngine(registry=registry, feat_validator=self._feat_validator)
        self._aggregator = SignalAggregator()
        self._risk = RiskManager(mt5_manager=mt5_manager)
        self._executor = TradeExecutor(mt5_manager=mt5_manager)

    def run(self, timeframe: str) -> None:
        """Execute full pipeline for the given timeframe."""
        started_at = time.monotonic()
        log.info("cycle_started", timeframe=timeframe)

        try:
            # Step 1 — Ingest
            df_clean = self._loader.load(timeframe)

            # Step 2 — Feature engineering (once, shared to all models)
            featured_df = self._features.compute(df_clean, timeframe)
            if featured_df.empty:
                log.warning("cycle_aborted_empty_features", timeframe=timeframe)
                return

            # Step 3 — Model execution
            result_set = self._engine.run(
                timeframe=timeframe,
                featured_df=featured_df,
            )

            # Step 4 — Signal aggregation
            signals = self._aggregator.aggregate(result_set)

            # Step 5 + 6 — Risk check then execute
            for signal in signals:
                approved = self._risk.check(signal)
                if approved:
                    self._executor.execute(signal)

        except DataValidationError as e:
            log.error("cycle_aborted_validation", timeframe=timeframe, error=str(e))
        except Exception as e:
            log.error("cycle_error", timeframe=timeframe, error=str(e), exc_info=True)
            raise  # re-raise so event_handler logs CRITICAL
        finally:
            elapsed = time.monotonic() - started_at
            log.info("cycle_complete", timeframe=timeframe, elapsed_seconds=round(elapsed, 3))
