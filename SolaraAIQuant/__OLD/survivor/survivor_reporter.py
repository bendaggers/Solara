"""
survivor/survivor_reporter.py — Survivor Audit Reporter
=========================================================
Logs stage transitions as immutable audit events.
Will write to SQLite StageTransitionLog table in Phase 2.
"""
import structlog

log = structlog.get_logger(__name__)


class SurvivorReporter:
    """Records position stage transitions for audit and analysis."""

    def report_transition(
        self,
        ticket: int,
        symbol: str,
        magic: int,
        from_stage: str,
        to_stage: str,
        pips_in_profit: float,
        protection_pct: float,
        old_sl: float,
        new_sl: float,
        old_tp: float | None,
        new_tp: float | None,
        mt5_confirmed: bool,
    ) -> None:
        """Log a stage transition event."""
        log.info(
            "stage_transition",
            ticket=ticket,
            symbol=symbol,
            magic=magic,
            from_stage=from_stage,
            to_stage=to_stage,
            pips_in_profit=round(pips_in_profit, 1),
            protection_pct=protection_pct,
            old_sl=old_sl,
            new_sl=new_sl,
            old_tp=old_tp,
            new_tp=new_tp,
            mt5_confirmed=mt5_confirmed,
        )
        # TODO: Phase 2 — write to SQLite StageTransitionLog table
