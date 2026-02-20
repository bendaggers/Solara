"""
signals/conflict_checker.py — Conflict Suppressor
===================================================
Detects and suppresses conflicting signals from the same model
on the same symbol within the same cycle. See FS Section 7.3.
"""
import structlog
from signals.signal_models import RawSignal

log = structlog.get_logger(__name__)


class ConflictChecker:
    """Filters out conflicting signals per FS Section 7.3 rules."""

    def filter(self, signals: list[RawSignal]) -> list[RawSignal]:
        """
        Apply all conflict suppression rules.

        Returns:
            Filtered list of signals safe to forward to risk manager.
        """
        # Group by (model_name, symbol)
        groups: dict[tuple, list[RawSignal]] = {}
        for sig in signals:
            key = (sig.model_name, sig.symbol)
            groups.setdefault(key, []).append(sig)

        result = []
        for (model, symbol), group in groups.items():
            directions = {s.direction for s in group}

            # RULE: Same model, same symbol, LONG + SHORT → suppress both
            if "LONG" in directions and "SHORT" in directions:
                log.warning(
                    "conflicting_signals_suppressed",
                    model=model,
                    symbol=symbol,
                    count=len(group),
                )
                continue

            # RULE: Duplicate direction — keep highest confidence only
            if len(group) > 1:
                group = [max(group, key=lambda s: s.confidence)]
                log.debug("duplicate_signal_deduplicated", model=model, symbol=symbol)

            result.extend(group)

        return result
