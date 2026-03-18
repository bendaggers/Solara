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
    """Model health status."""
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


class RunStatus(Enum):
    """Result of a model run."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    EMPTY = "EMPTY"  # No predictions (not a failure)
    SKIPPED = "SKIPPED"  # Skipped due to missing features


@dataclass
class HealthReport:
    """Health report for a model."""
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
    - 3 consecutive failures -> model disabled
    - EMPTY results do NOT count as failures
    - Manual re-enable requires editing model_registry.yaml
    
    Health persisted in SQLite for recovery after restart.
    """
    
    FAILURE_THRESHOLD = 3  # Consecutive failures before auto-disable
    
    def __init__(self):
        # In-memory cache of disabled models (for fast checks)
        self._disabled_models: Dict[str, bool] = {}
    
    def record_run(
        self,
        model_name: str,
        magic: int,
        status: RunStatus,
        duration_seconds: float = 0,
        error_message: Optional[str] = None
    ):
        """
        Record a model run result.
        
        Args:
            model_name: Name of the model
            magic: Model's magic number
            status: Result status
            duration_seconds: How long the run took
            error_message: Error details if failed
        """
        is_failure = status in (RunStatus.FAILED, RunStatus.TIMEOUT)
        
        with db_manager.session_scope() as session:
            # Get or create health record
            health = session.query(ModelHealth).filter_by(model_name=model_name).first()
            
            if health is None:
                health = ModelHealth(
                    model_name=model_name,
                    magic=magic,
                    total_runs=0,
                    total_failures=0,
                    consecutive_failures=0,
                    is_auto_disabled=False
                )
                session.add(health)
            
            # Update stats
            health.total_runs += 1
            health.last_run_at = datetime.utcnow()
            health.last_run_status = status.value
            health.last_run_duration = duration_seconds
            
            if is_failure:
                health.total_failures += 1
                health.consecutive_failures += 1
                health.last_error = error_message
                
                # Check for auto-disable
                if health.consecutive_failures >= self.FAILURE_THRESHOLD:
                    if not health.is_auto_disabled:
                        health.is_auto_disabled = True
                        health.disabled_at = datetime.utcnow()
                        health.disabled_reason = f"{self.FAILURE_THRESHOLD} consecutive failures"
                        
                        logger.warning(
                            f"AUTO-DISABLED model '{model_name}' after "
                            f"{health.consecutive_failures} consecutive failures"
                        )
                        
                        # Update cache
                        self._disabled_models[model_name] = True
            else:
                # Reset consecutive failures on success
                health.consecutive_failures = 0
            
            session.commit()
            
            logger.debug(
                f"Model '{model_name}' run: {status.value}, "
                f"consecutive_failures={health.consecutive_failures}"
            )
    
    def is_model_healthy(self, model_name: str) -> bool:
        """
        Check if a model is healthy (not auto-disabled).
        
        Args:
            model_name: Name of the model
            
        Returns:
            True if model can run, False if auto-disabled
        """
        # Check cache first
        if model_name in self._disabled_models:
            return not self._disabled_models[model_name]
        
        # Check database
        with db_manager.session_scope() as session:
            health = session.query(ModelHealth).filter_by(model_name=model_name).first()
            
            if health is None:
                return True  # No record = healthy
            
            # Update cache
            self._disabled_models[model_name] = health.is_auto_disabled
            
            return not health.is_auto_disabled
    
    def get_health_report(self, model_name: str) -> HealthReport:
        """Get detailed health report for a model."""
        with db_manager.session_scope() as session:
            health = session.query(ModelHealth).filter_by(model_name=model_name).first()
            
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
                    failure_rate=0.0
                )
            
            # Determine status
            if health.is_auto_disabled:
                status = HealthStatus.DISABLED
            elif health.consecutive_failures > 0:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY
            
            failure_rate = (
                health.total_failures / health.total_runs
                if health.total_runs > 0 else 0.0
            )
            
            return HealthReport(
                model_name=model_name,
                status=status,
                consecutive_failures=health.consecutive_failures,
                total_runs=health.total_runs,
                total_failures=health.total_failures,
                last_run_at=health.last_run_at,
                last_run_status=health.last_run_status,
                is_enabled=not health.is_auto_disabled,
                failure_rate=failure_rate
            )
    
    def get_all_health_reports(self) -> Dict[str, HealthReport]:
        """Get health reports for all known models."""
        reports = {}
        
        with db_manager.session_scope() as session:
            all_health = session.query(ModelHealth).all()
            
            for health in all_health:
                reports[health.model_name] = self.get_health_report(health.model_name)
        
        return reports
    
    def reset_model_health(self, model_name: str):
        """
        Reset health for a model (manual recovery).
        
        Use this after fixing a model to clear failure count.
        """
        with db_manager.session_scope() as session:
            health = session.query(ModelHealth).filter_by(model_name=model_name).first()
            
            if health:
                health.consecutive_failures = 0
                health.is_auto_disabled = False
                health.disabled_at = None
                health.disabled_reason = None
                session.commit()
                
                # Update cache
                self._disabled_models[model_name] = False
                
                logger.info(f"Reset health for model '{model_name}'")
    
    def load_disabled_cache(self):
        """Load disabled models into cache from database."""
        with db_manager.session_scope() as session:
            disabled = session.query(ModelHealth).filter_by(is_auto_disabled=True).all()
            
            self._disabled_models = {
                h.model_name: True for h in disabled
            }
            
            if self._disabled_models:
                logger.warning(
                    f"Loaded {len(self._disabled_models)} auto-disabled models: "
                    f"{list(self._disabled_models.keys())}"
                )
    
    def print_health_summary(self):
        """Print health summary for all models."""
        reports = self.get_all_health_reports()
        
        if not reports:
            print("  No model health data recorded yet.")
            return
        
        print("\n" + "=" * 70)
        print("  MODEL HEALTH SUMMARY")
        print("=" * 70)
        
        print(f"\n  {'Model':<25} {'Status':<12} {'Runs':<8} {'Fails':<8} {'Consec':<8}")
        print("  " + "-" * 65)
        
        for name, report in sorted(reports.items()):
            status_icon = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.WARNING: "⚠",
                HealthStatus.DISABLED: "✗",
                HealthStatus.UNKNOWN: "?"
            }.get(report.status, "?")
            
            print(
                f"  {name:<25} {status_icon} {report.status.value:<10} "
                f"{report.total_runs:<8} {report.total_failures:<8} "
                f"{report.consecutive_failures:<8}"
            )
        
        # Count by status
        healthy = sum(1 for r in reports.values() if r.status == HealthStatus.HEALTHY)
        warning = sum(1 for r in reports.values() if r.status == HealthStatus.WARNING)
        disabled = sum(1 for r in reports.values() if r.status == HealthStatus.DISABLED)
        
        print(f"\n  Summary: {healthy} healthy, {warning} warning, {disabled} disabled")
        print("=" * 70 + "\n")


# Global instance
model_health_tracker = ModelHealthTracker()
