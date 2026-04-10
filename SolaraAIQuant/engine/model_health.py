"""
Solara AI Quant - Model Health Tracker

Tracks model execution health and implements auto-disable
after consecutive failures.

Health states:
- HEALTHY: Running normally
- WARNING: 1-2 consecutive failures
- DISABLED: 3+ consecutive failures (auto-disabled)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict
from enum import Enum
import logging

from state.database import db_manager
from state.models import ModelHealth

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


class RunStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    EMPTY = "EMPTY"
    SKIPPED = "SKIPPED"


@dataclass
class HealthReport:
    model_name: str
    status: HealthStatus
    consecutive_failures: int
    total_runs: int
    total_failures: int
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    is_enabled: bool
    failure_rate: float


class ModelHealthTracker:
    """
    Tracks model health and manages auto-disable.

    Auto-disable rules:
    - 3 consecutive failures → model disabled
    - EMPTY results do NOT count as failures
    - Manual re-enable requires editing model_registry.yaml

    Column mapping to state/models.py ModelHealth table:
        is_auto_disabled  → auto_disabled
        disabled_reason   → auto_disabled_reason
        last_run_duration → (not stored — not in schema)
        last_error        → (not stored — not in schema)
        magic             → (not stored — not in schema)
    """

    FAILURE_THRESHOLD = 3

    def __init__(self):
        self._disabled_models: Dict[str, bool] = {}

    def record_run(
        self,
        model_name: str,
        magic: int,          # kept in signature for caller compatibility
        status: RunStatus,
        duration_seconds: float = 0,
        error_message: Optional[str] = None
    ):
        """Record a model run result and update health state."""
        is_failure = status in (RunStatus.FAILED, RunStatus.TIMEOUT)

        try:
            with db_manager.session_scope() as session:
                health = (
                    session.query(ModelHealth)
                    .filter_by(model_name=model_name)
                    .first()
                )

                if health is None:
                    health = ModelHealth(
                        model_name=model_name,
                        total_runs=0,
                        failed_runs=0,
                        consecutive_failures=0,
                        auto_disabled=False,
                    )
                    session.add(health)

                # Update counters
                health.total_runs += 1
                health.last_run_at = datetime.utcnow()
                health.last_run_status = status.value

                if health.first_run_at is None:
                    health.first_run_at = datetime.utcnow()

                if status == RunStatus.SUCCESS:
                    health.successful_runs = (health.successful_runs or 0) + 1
                elif status in (RunStatus.FAILED, RunStatus.TIMEOUT):
                    health.failed_runs = (health.failed_runs or 0) + 1
                elif status == RunStatus.EMPTY:
                    health.empty_runs = (health.empty_runs or 0) + 1
                elif status == RunStatus.TIMEOUT:
                    health.timeout_runs = (health.timeout_runs or 0) + 1

                if is_failure:
                    health.consecutive_failures += 1

                    if (
                        health.consecutive_failures >= self.FAILURE_THRESHOLD
                        and not health.auto_disabled
                    ):
                        health.auto_disabled = True
                        health.disabled_at = datetime.utcnow()
                        health.auto_disabled_reason = (
                            f"{self.FAILURE_THRESHOLD} consecutive failures"
                        )
                        self._disabled_models[model_name] = True

                        logger.warning(
                            f"AUTO-DISABLED model '{model_name}' after "
                            f"{health.consecutive_failures} consecutive failures"
                        )
                else:
                    # SUCCESS or EMPTY resets the streak
                    health.consecutive_failures = 0

                session.commit()

                logger.debug(
                    f"Model '{model_name}' run recorded: {status.value}, "
                    f"consecutive_failures={health.consecutive_failures}"
                )

        except Exception as e:
            logger.error(f"Database error recording health for '{model_name}': {e}")

    def is_model_healthy(self, model_name: str) -> bool:
        """Check if a model is healthy (not auto-disabled)."""
        if model_name in self._disabled_models:
            return not self._disabled_models[model_name]

        try:
            with db_manager.session_scope() as session:
                health = (
                    session.query(ModelHealth)
                    .filter_by(model_name=model_name)
                    .first()
                )

                if health is None:
                    return True

                self._disabled_models[model_name] = health.auto_disabled
                return not health.auto_disabled

        except Exception as e:
            logger.error(f"Database error checking health for '{model_name}': {e}")
            return True  # Fail open — don't block execution on DB errors

    def get_health_report(self, model_name: str) -> HealthReport:
        """Get detailed health report for a model."""
        try:
            with db_manager.session_scope() as session:
                health = (
                    session.query(ModelHealth)
                    .filter_by(model_name=model_name)
                    .first()
                )

                if health is None:
                    return HealthReport(
                        model_name=model_name,
                        status=HealthStatus.UNKNOWN,
                        consecutive_failures=0,
                        total_runs=0,
                        total_failures=0,
                        last_run_at=None,
                        last_run_status=None,
                        is_enabled=True,
                        failure_rate=0.0,
                    )

                if health.auto_disabled:
                    status = HealthStatus.DISABLED
                elif health.consecutive_failures > 0:
                    status = HealthStatus.WARNING
                else:
                    status = HealthStatus.HEALTHY

                total_failures = health.failed_runs or 0
                failure_rate = (
                    total_failures / health.total_runs
                    if health.total_runs > 0 else 0.0
                )

                return HealthReport(
                    model_name=model_name,
                    status=status,
                    consecutive_failures=health.consecutive_failures,
                    total_runs=health.total_runs,
                    total_failures=total_failures,
                    last_run_at=health.last_run_at,
                    last_run_status=health.last_run_status,
                    is_enabled=not health.auto_disabled,
                    failure_rate=failure_rate,
                )

        except Exception as e:
            logger.error(f"Database error getting health report for '{model_name}': {e}")
            return HealthReport(
                model_name=model_name,
                status=HealthStatus.UNKNOWN,
                consecutive_failures=0,
                total_runs=0,
                total_failures=0,
                last_run_at=None,
                last_run_status=None,
                is_enabled=True,
                failure_rate=0.0,
            )

    def get_all_health_reports(self) -> Dict[str, HealthReport]:
        """Get health reports for all known models."""
        reports = {}
        try:
            with db_manager.session_scope() as session:
                all_health = session.query(ModelHealth).all()
                for health in all_health:
                    reports[health.model_name] = self.get_health_report(
                        health.model_name
                    )
        except Exception as e:
            logger.error(f"Database error getting all health reports: {e}")
        return reports

    def reset_model_health(self, model_name: str):
        """Reset health for a model (manual recovery after fixing)."""
        try:
            with db_manager.session_scope() as session:
                health = (
                    session.query(ModelHealth)
                    .filter_by(model_name=model_name)
                    .first()
                )

                if health:
                    health.consecutive_failures = 0
                    health.auto_disabled = False
                    health.disabled_at = None
                    health.auto_disabled_reason = None
                    session.commit()

                self._disabled_models[model_name] = False
                logger.info(f"Reset health for model '{model_name}'")

        except Exception as e:
            logger.error(f"Database error resetting health for '{model_name}': {e}")

    def load_disabled_cache(self):
        """Load auto-disabled models into cache from database on startup."""
        try:
            with db_manager.session_scope() as session:
                disabled = (
                    session.query(ModelHealth)
                    .filter_by(auto_disabled=True)
                    .all()
                )
                self._disabled_models = {h.model_name: True for h in disabled}

                if self._disabled_models:
                    logger.warning(
                        f"Loaded {len(self._disabled_models)} auto-disabled models: "
                        f"{list(self._disabled_models.keys())}"
                    )
        except Exception as e:
            logger.error(f"Database error loading disabled cache: {e}")

    def print_health_summary(self):
        """Print health summary for all models."""
        reports = self.get_all_health_reports()

        if not reports:
            print("  No model health data recorded yet.")
            return

        print("\n" + "=" * 70)
        print("  MODEL HEALTH SUMMARY")
        print("=" * 70)
        print(
            f"\n  {'Model':<25} {'Status':<12} "
            f"{'Runs':<8} {'Fails':<8} {'Consec':<8}"
        )
        print("  " + "-" * 65)

        for name, report in sorted(reports.items()):
            icon = {
                HealthStatus.HEALTHY: "OK",
                HealthStatus.WARNING: "WARN",
                HealthStatus.DISABLED: "DISABLED",
                HealthStatus.UNKNOWN: "?",
            }.get(report.status, "?")

            print(
                f"  {name:<25} {icon:<12} "
                f"{report.total_runs:<8} {report.total_failures:<8} "
                f"{report.consecutive_failures:<8}"
            )

        healthy = sum(1 for r in reports.values() if r.status == HealthStatus.HEALTHY)
        warning = sum(1 for r in reports.values() if r.status == HealthStatus.WARNING)
        disabled = sum(1 for r in reports.values() if r.status == HealthStatus.DISABLED)

        print(
            f"\n  Summary: {healthy} healthy, {warning} warning, {disabled} disabled"
        )
        print("=" * 70 + "\n")


# Global instance
model_health_tracker = ModelHealthTracker()
