"""
signals/signal_aggregator.py — Signal Aggregator
==================================================
Routes ModelResultSet through the conflict checker.
Default strategy: INDEPENDENT_PASSTHROUGH — each model's signal
stands alone, no cross-model voting required.
"""
import structlog
from engine.result_collector import ModelResultSet
from signals.signal_models import RawSignal, AggregatedSignal
from signals.conflict_checker import ConflictChecker

log = structlog.get_logger(__name__)


class SignalAggregator:
    """Aggregates raw model signals into a clean list for risk checking."""

    def __init__(self) -> None:
        self._conflict_checker = ConflictChecker()

    def aggregate(self, result_set: ModelResultSet) -> list[AggregatedSignal]:
        """
        Aggregate all raw signals from a ModelResultSet.

        Returns:
            List of AggregatedSignal objects ready for risk checking.
        """
        raw_signals: list[RawSignal] = result_set.all_signals()

        if not raw_signals:
            log.info("no_signals_to_aggregate", timeframe=result_set.timeframe)
            return []

        # Apply conflict suppression
        filtered = self._conflict_checker.filter(raw_signals)

        # Convert to AggregatedSignal
        aggregated = [
            AggregatedSignal(
                symbol=s.symbol,
                direction=s.direction,
                confidence=s.confidence,
                model_name=s.model_name,
                magic=s.magic,
                weight=s.weight,
                price=s.price,
                comment=s.comment,
                timeframe=s.timeframe,
                timestamp=s.timestamp,
            )
            for s in filtered
        ]

        log.info(
            "signals_aggregated",
            timeframe=result_set.timeframe,
            raw=len(raw_signals),
            after_filter=len(aggregated),
        )
        return aggregated
