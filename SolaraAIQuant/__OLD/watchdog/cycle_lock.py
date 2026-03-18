"""
watchdog/cycle_lock.py — Per-Timeframe Cycle Locks
====================================================
One threading.Event per timeframe.
Set   = cycle is running (locked).
Clear = cycle is idle (unlocked).

CRITICAL: Every acquire MUST have a corresponding release in a
try/finally block. A stuck lock permanently blocks that timeframe.
"""
import threading
from typing import Optional


class CycleLockManager:
    """Manages independent cycle locks for each timeframe."""

    def __init__(self, timeframes: list[str]) -> None:
        self._locks: dict[str, threading.Event] = {
            tf: threading.Event() for tf in timeframes
        }

    def is_locked(self, timeframe: str) -> bool:
        return self._locks[timeframe].is_set()

    def acquire(self, timeframe: str) -> None:
        """Lock the given timeframe. Call before pipeline starts."""
        self._locks[timeframe].set()

    def release(self, timeframe: str) -> None:
        """Unlock the given timeframe. Always call in finally block."""
        self._locks[timeframe].clear()

    def status(self) -> dict[str, bool]:
        """Return lock status for all timeframes."""
        return {tf: e.is_set() for tf, e in self._locks.items()}
