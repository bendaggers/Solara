"""
engine/worker_pool.py — ThreadPoolExecutor Wrapper
====================================================
Wraps Python's ThreadPoolExecutor with SAQ-specific naming and lifecycle.
One instance per timeframe pipeline per cycle.
"""
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from typing import Callable, Any
import structlog

log = structlog.get_logger(__name__)


class WorkerPool:
    """Manages a bounded pool of worker threads for model execution."""

    def __init__(self, max_workers: int, timeframe: str) -> None:
        self._max_workers = max_workers
        self._timeframe = timeframe
        self._executor: ThreadPoolExecutor | None = None

    def __enter__(self) -> "WorkerPool":
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix=f"SAQ_{self._timeframe}_worker",
        )
        return self

    def __exit__(self, *args) -> None:
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        if self._executor is None:
            raise RuntimeError("WorkerPool used outside of context manager")
        return self._executor.submit(fn, *args, **kwargs)
