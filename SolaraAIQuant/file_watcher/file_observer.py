"""
Solara AI Quant - File Observer

Monitors CSV files exported by MT5 EA for changes.
Triggers pipeline execution when files are modified.

Uses the watchdog library for OS-native file monitoring:
- Windows: ReadDirectoryChangesW
- Linux: inotify
- macOS: FSEvents

Timing behaviour:
    On file change detection, the handler waits PROCESSING_DELAY_SECONDS
    before reading the file. This gives the EA time to finish writing all
    28 symbols before SAQ reads the CSV.

    Set via .env:  WATCHDOG_PROCESSING_DELAY_SECONDS=10  (default: 10)

    The delay replaces the old empty-file retry — instead of reacting
    immediately and checking for empty files, we simply wait long enough
    for the EA to always finish, then read.
"""

import time
from pathlib import Path
from typing import Dict, Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import logging
import threading

from config import watchdog_config, TIMEFRAMES, MQL5_FILES_DIR
from .cycle_lock import cycle_lock, Timeframe, CycleLockContext

logger = logging.getLogger(__name__)


class CSVFileHandler(FileSystemEventHandler):
    """
    Handles file modification events for CSV files.

    On each file change:
      1. Check it's a watched CSV file
      2. Debounce — ignore if fired too recently
      3. Wait PROCESSING_DELAY_SECONDS for EA to finish writing
      4. Verify file is not empty
      5. Trigger pipeline callback
    """

    def __init__(
        self,
        watched_files: Dict[str, Timeframe],
        on_file_changed: Callable[[Path, Timeframe], None],
        debounce_seconds: float = 2.0,
        processing_delay_seconds: float = 10.0,
    ):
        super().__init__()
        self.watched_files             = watched_files
        self.on_file_changed           = on_file_changed
        self.debounce_seconds          = debounce_seconds
        self.processing_delay_seconds  = processing_delay_seconds

        self._last_modified: Dict[str, float] = {}
        self._lock = threading.Lock()

    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return
        if not isinstance(event, FileModifiedEvent):
            return

        file_path = Path(event.src_path)
        filename  = file_path.name.lower()

        # Check if this is a watched file
        timeframe = None
        for watched_name, tf in self.watched_files.items():
            if filename == watched_name.lower():
                timeframe = tf
                break

        if timeframe is None:
            return

        # Debounce — ignore if we just processed this file
        with self._lock:
            now  = time.time()
            last = self._last_modified.get(filename, 0)

            if now - last < self.debounce_seconds:
                logger.debug(
                    f"Debouncing {filename} (last: {now - last:.2f}s ago)"
                )
                return

            self._last_modified[filename] = now

        # Wait for EA to finish writing all symbols
        if self.processing_delay_seconds > 0:
            logger.debug(
                f"File change detected: {filename} — "
                f"waiting {self.processing_delay_seconds:.0f}s for EA to finish writing"
            )
            time.sleep(self.processing_delay_seconds)

        # Verify file is not empty after the wait
        try:
            if file_path.stat().st_size == 0:
                logger.warning(
                    f"Still empty after {self.processing_delay_seconds:.0f}s wait: "
                    f"{filename} — skipping cycle"
                )
                return
        except OSError:
            logger.warning(f"Cannot stat file: {filename}")
            return

        logger.info(f"File modified: {filename} -> {timeframe.value}")
        self.on_file_changed(file_path, timeframe)


class FileObserver:
    """
    Watches for CSV file changes in the MT5 MQL5/Files directory.
    """

    def __init__(
        self,
        watch_directory: Optional[Path] = None,
        on_file_changed: Optional[Callable[[Path, Timeframe], None]] = None,
    ):
        self.watch_directory = watch_directory or MQL5_FILES_DIR
        self.on_file_changed = on_file_changed or self._default_handler

        # Build mapping of filenames to timeframes
        self.watched_files: Dict[str, Timeframe] = {}
        for tf_name, tf_config in TIMEFRAMES.items():
            try:
                timeframe = Timeframe[tf_name]
                self.watched_files[tf_config.csv_filename] = timeframe
            except KeyError:
                logger.warning(f"Unknown timeframe: {tf_name}")

        self._observer: Optional[Observer] = None
        self._running = False

    def _default_handler(self, file_path: Path, timeframe: Timeframe):
        logger.info(f"Default handler: {file_path.name} ({timeframe.value})")

    def start(self):
        """Start watching for file changes."""
        if self._running:
            logger.warning("FileObserver already running")
            return

        if not Path(self.watch_directory).exists():
            logger.warning(
                f"Watch directory does not exist: {self.watch_directory}"
            )
            logger.warning(
                "MT5 may not be running or path is incorrect — continuing anyway"
            )

        handler = CSVFileHandler(
            watched_files=self.watched_files,
            on_file_changed=self._handle_file_change,
            debounce_seconds=watchdog_config.debounce_seconds,
            processing_delay_seconds=watchdog_config.processing_delay_seconds,
        )

        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(Path(self.watch_directory)),
            recursive=False,
        )

        self._observer.start()
        self._running = True

        logger.info(
            f"FileObserver started — watching: {self.watch_directory}  "
            f"delay: {watchdog_config.processing_delay_seconds:.0f}s"
        )
        logger.info(f"Watched files: {list(self.watched_files.keys())}")

    def stop(self):
        """Stop watching for file changes."""
        if not self._running:
            return

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        self._running = False
        logger.info("FileObserver stopped")

    def _handle_file_change(self, file_path: Path, timeframe: Timeframe):
        """Handle file change with cycle lock protection."""
        with CycleLockContext(cycle_lock, timeframe) as acquired:
            if not acquired:
                logger.warning(
                    f"Cycle overlap: {timeframe.value} already running, skipping"
                )
                return
            try:
                self.on_file_changed(file_path, timeframe)
            except Exception as e:
                logger.exception(f"Error in file change handler: {e}")

    def is_running(self) -> bool:
        return self._running

    def get_watched_files(self) -> Dict[str, str]:
        return {
            filename: tf.value
            for filename, tf in self.watched_files.items()
        }

    def run_forever(self):
        """Start observer and block until interrupted."""
        self.start()
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
        finally:
            self.stop()


# Global instance
file_observer: Optional[FileObserver] = None


def get_file_observer() -> FileObserver:
    """Get or create the global file observer."""
    global file_observer
    if file_observer is None:
        file_observer = FileObserver()
    return file_observer
