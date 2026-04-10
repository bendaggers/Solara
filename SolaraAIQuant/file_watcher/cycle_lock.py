"""
Solara AI Quant - Cycle Lock

Prevents overlapping execution cycles for the same timeframe.
Uses threading.Event for each timeframe to track active cycles.
"""

import threading
from typing import Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Timeframe(Enum):
    """Trading timeframes."""
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


class CycleLock:
    """
    Thread-safe cycle lock for preventing overlapping timeframe processing.
    
    Each timeframe has its own lock. When a cycle starts for a timeframe,
    the lock is acquired. Any new file events for that timeframe are 
    skipped until the cycle completes.
    
    Usage:
        lock = CycleLock()
        
        if lock.acquire(Timeframe.H4):
            try:
                # Process H4 data...
            finally:
                lock.release(Timeframe.H4)
        else:
            logger.warning("H4 cycle already running, skipping")
    """
    
    def __init__(self):
        self._locks: Dict[Timeframe, threading.Event] = {}
        self._master_lock = threading.Lock()
        
        # Initialize locks for all timeframes
        for tf in Timeframe:
            self._locks[tf] = threading.Event()
            self._locks[tf].set()  # Initially unlocked (set = available)
    
    def acquire(self, timeframe: Timeframe) -> bool:
        """
        Try to acquire lock for a timeframe.
        
        Args:
            timeframe: The timeframe to lock
            
        Returns:
            True if lock acquired, False if already locked
        """
        with self._master_lock:
            if not self._locks[timeframe].is_set():
                # Already locked
                logger.debug(f"Cycle lock for {timeframe.value} already held")
                return False
            
            # Acquire the lock
            self._locks[timeframe].clear()
            logger.debug(f"Acquired cycle lock for {timeframe.value}")
            return True
    
    def release(self, timeframe: Timeframe):
        """
        Release lock for a timeframe.
        
        Args:
            timeframe: The timeframe to unlock
        """
        with self._master_lock:
            self._locks[timeframe].set()
            logger.debug(f"Released cycle lock for {timeframe.value}")
    
    def is_locked(self, timeframe: Timeframe) -> bool:
        """
        Check if a timeframe is currently locked.
        
        Args:
            timeframe: The timeframe to check
            
        Returns:
            True if locked, False if available
        """
        return not self._locks[timeframe].is_set()
    
    def get_status(self) -> Dict[str, bool]:
        """
        Get lock status for all timeframes.
        
        Returns:
            Dict mapping timeframe name to locked status
        """
        return {
            tf.value: self.is_locked(tf)
            for tf in Timeframe
        }
    
    def wait_for_release(self, timeframe: Timeframe, timeout: float = None) -> bool:
        """
        Wait for a timeframe lock to be released.
        
        Args:
            timeframe: The timeframe to wait for
            timeout: Maximum time to wait (seconds), None = wait forever
            
        Returns:
            True if lock was released, False if timeout
        """
        return self._locks[timeframe].wait(timeout)


class CycleLockContext:
    """
    Context manager for cycle locks.
    
    Usage:
        with CycleLockContext(cycle_lock, Timeframe.H4) as acquired:
            if acquired:
                # Process H4 data...
            else:
                # Cycle already running
    """
    
    def __init__(self, lock: CycleLock, timeframe: Timeframe):
        self.lock = lock
        self.timeframe = timeframe
        self.acquired = False
    
    def __enter__(self) -> bool:
        self.acquired = self.lock.acquire(self.timeframe)
        return self.acquired
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            self.lock.release(self.timeframe)
        return False  # Don't suppress exceptions


# Global instance
cycle_lock = CycleLock()
