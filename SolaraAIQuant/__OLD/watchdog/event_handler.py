"""
watchdog/event_handler.py — Filesystem Event Handler
======================================================
Receives FILE_MODIFIED events from the watchdog observer.
Checks cycle lock, then fires the pipeline in a background thread.
"""
import threading
import structlog
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.cycle_lock import CycleLockManager
import config

log = structlog.get_logger(__name__)


class SAQEventHandler(FileSystemEventHandler):
    """Handles filesystem events for MT5 CSV files."""

    def __init__(
        self,
        cycle_locks: CycleLockManager,
        pipeline_runner,          # PipelineRunner — avoid circular import
    ) -> None:
        super().__init__()
        self._locks = cycle_locks
        self._runner = pipeline_runner
        # Reverse map: file path string → timeframe
        self._path_to_tf: dict[str, str] = {
            str(path): tf for tf, path in config.WATCHED_FILES.items()
        }

    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return

        tf = self._path_to_tf.get(str(event.src_path))
        if tf is None:
            return  # not a watched file

        if self._locks.is_locked(tf):
            log.warning(
                "cycle_overlap_skipped",
                timeframe=tf,
                message="Previous cycle still running — event skipped",
            )
            return

        # Fire pipeline in its own thread (non-blocking)
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(tf,),
            name=f"SAQ_{tf}_pipeline",
            daemon=True,
        )
        thread.start()

    def _run_pipeline(self, timeframe: str) -> None:
        self._locks.acquire(timeframe)
        try:
            self._runner.run(timeframe)
        except Exception as e:
            log.critical(
                "pipeline_crashed",
                timeframe=timeframe,
                error=str(e),
                exc_info=True,
            )
        finally:
            self._locks.release(timeframe)
