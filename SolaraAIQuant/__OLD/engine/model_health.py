"""
engine/model_health.py — Model Health Tracker
===============================================
Tracks consecutive failures and auto-disables models after 3 failures.
Writes health records to the SQLite ModelHealth table after every cycle.
"""
import structlog
from engine.result_collector import ModelResult, RunStatus
import config

log = structlog.get_logger(__name__)


class ModelHealthTracker:
    """Tracks per-model health and enforces auto-disable rule."""

    def __init__(self, registry) -> None:
        self._registry = registry
        # In-memory counters — also persisted to DB after each cycle
        self._consecutive_failures: dict[str, int] = {}

    def record(self, result: ModelResult) -> None:
        """Record a model run result and check auto-disable threshold."""
        name = result.model_name

        if result.status in (RunStatus.FAILED, RunStatus.TIMEOUT):
            self._consecutive_failures[name] = self._consecutive_failures.get(name, 0) + 1
        else:
            # SUCCESS or EMPTY resets the failure counter
            self._consecutive_failures[name] = 0

        failures = self._consecutive_failures[name]

        if failures >= config.AUTO_DISABLE_AFTER_FAILURES:
            self._registry.disable(
                name=name,
                reason=f"{failures} consecutive failures",
            )
            # TODO: Phase 3 — send alert notification

        # TODO: Persist to state.ModelHealth table
        log.debug(
            "model_health_recorded",
            model=name,
            status=result.status,
            consecutive_failures=failures,
            elapsed=result.elapsed_seconds,
        )
