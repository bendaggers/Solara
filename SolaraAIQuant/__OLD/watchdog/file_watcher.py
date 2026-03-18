"""
watchdog/file_watcher.py — File Watchdog Observer
===================================================
Monitors all four MT5 CSV files for modification events.
Uses OS-native filesystem events (inotify on Linux, ReadDirectoryChangesW on Windows).
"""
import time
import structlog
from watchdog.observers import Observer
from watchdog.cycle_lock import CycleLockManager
from watchdog.event_handler import SAQEventHandler
from watchdog.pipeline_runner import PipelineRunner
import config

log = structlog.get_logger(__name__)


class FileWatcher:
    """Starts and manages the filesystem observer for all watched CSV files."""

    def __init__(self, mt5_manager, registry) -> None:
        self._mt5 = mt5_manager
        self._registry = registry
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching all CSV files. Blocks until shutdown signal."""
        locks = CycleLockManager(timeframes=config.SUPPORTED_TIMEFRAMES)
        runner = PipelineRunner(mt5_manager=self._mt5, registry=self._registry)
        handler = SAQEventHandler(cycle_locks=locks, pipeline_runner=runner)

        self._observer = Observer()

        # Watch all unique parent directories
        watched_dirs = set(str(p.parent) for p in config.WATCHED_FILES.values())
        for directory in watched_dirs:
            self._observer.schedule(handler, path=directory, recursive=False)
            log.info("watching_directory", path=directory)

        self._observer.start()
        log.info("file_watchdog_started")

        try:
            while self._observer.is_alive():
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            log.info("file_watchdog_stopping")
            self._observer.stop()

        self._observer.join()
        log.info("file_watchdog_stopped")
