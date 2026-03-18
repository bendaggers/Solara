"""
Solara AI Quant - File Observer

Monitors CSV files exported by MT5 EA for changes.
Triggers pipeline execution when files are modified.

Uses the watchdog library for OS-native file monitoring:
- Windows: ReadDirectoryChangesW
- Linux: inotify
- macOS: FSEvents
"""

import os
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
    
    Only processes FILE_MODIFIED events for watched CSV files.
    CREATE, DELETE, MOVED events are ignored.
    """
    
    def __init__(
        self,
        watched_files: Dict[str, Timeframe],
        on_file_changed: Callable[[Path, Timeframe], None],
        debounce_seconds: float = 1.0
    ):
        """
        Args:
            watched_files: Dict mapping filename to Timeframe
            on_file_changed: Callback when a watched file changes
            debounce_seconds: Minimum time between processing same file
        """
        super().__init__()
        self.watched_files = watched_files
        self.on_file_changed = on_file_changed
        self.debounce_seconds = debounce_seconds
        
        # Track last modification time per file for debouncing
        self._last_modified: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def on_modified(self, event):
        """Handle file modification event."""
        # Only process file events (not directory)
        if event.is_directory:
            return
        
        # Only process FileModifiedEvent
        if not isinstance(event, FileModifiedEvent):
            return
        
        file_path = Path(event.src_path)
        filename = file_path.name.lower()
        
        # Check if this is a watched file
        timeframe = None
        for watched_name, tf in self.watched_files.items():
            if filename == watched_name.lower():
                timeframe = tf
                break
        
        if timeframe is None:
            # Not a watched file
            return
        
        # Debounce: ignore if we just processed this file
        with self._lock:
            now = time.time()
            last = self._last_modified.get(filename, 0)
            
            if now - last < self.debounce_seconds:
                logger.debug(f"Debouncing {filename} (last: {now - last:.2f}s ago)")
                return
            
            self._last_modified[filename] = now
        
        # Check file is not empty
        try:
            if file_path.stat().st_size == 0:
                logger.warning(f"Ignoring empty file: {filename}")
                return
        except OSError:
            logger.warning(f"Cannot stat file: {filename}")
            return
        
        logger.info(f"File modified: {filename} -> {timeframe.value}")
        
        # Trigger callback
        self.on_file_changed(file_path, timeframe)


class FileObserver:
    """
    Watches for CSV file changes in the MT5 MQL5/Files directory.
    
    Architecture:
    - Uses watchdog library for efficient OS-native monitoring
    - Maintains one Observer for the directory
    - Uses CSVFileHandler to filter and debounce events
    - Triggers pipeline_runner when files change
    """
    
    def __init__(
        self,
        watch_directory: Optional[Path] = None,
        on_file_changed: Optional[Callable[[Path, Timeframe], None]] = None
    ):
        """
        Args:
            watch_directory: Directory to watch (default: MQL5_FILES_DIR)
            on_file_changed: Callback when file changes
        """
        self.watch_directory = watch_directory or MQL5_FILES_DIR
        self.on_file_changed = on_file_changed or self._default_handler
        
        # Build mapping of filenames to timeframes
        self.watched_files: Dict[str, Timeframe] = {}
        for tf_name, tf_config in TIMEFRAMES.items():
            try:
                timeframe = Timeframe[tf_name]
                self.watched_files[tf_config['csv_file']] = timeframe
            except KeyError:
                logger.warning(f"Unknown timeframe: {tf_name}")
        
        self._observer: Optional[Observer] = None
        self._running = False
    
    def _default_handler(self, file_path: Path, timeframe: Timeframe):
        """Default handler just logs the event."""
        logger.info(f"Default handler: {file_path.name} ({timeframe.value})")
    
    def start(self):
        """Start watching for file changes."""
        if self._running:
            logger.warning("FileObserver already running")
            return
        
        # Validate directory exists
        if not self.watch_directory.exists():
            logger.error(f"Watch directory does not exist: {self.watch_directory}")
            logger.info("Creating directory...")
            self.watch_directory.mkdir(parents=True, exist_ok=True)
        
        # Create handler
        handler = CSVFileHandler(
            watched_files=self.watched_files,
            on_file_changed=self._handle_file_change,
            debounce_seconds=watchdog_config.debounce_seconds
        )
        
        # Create and start observer
        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(self.watch_directory),
            recursive=False
        )
        
        self._observer.start()
        self._running = True
        
        logger.info(f"FileObserver started watching: {self.watch_directory}")
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
        """
        Handle a file change event with cycle lock protection.
        
        If the timeframe cycle is already running, skip this event.
        """
        # Try to acquire cycle lock
        with CycleLockContext(cycle_lock, timeframe) as acquired:
            if not acquired:
                logger.warning(
                    f"Cycle overlap: {timeframe.value} cycle already running, skipping"
                )
                return
            
            # Call the actual handler
            try:
                self.on_file_changed(file_path, timeframe)
            except Exception as e:
                logger.exception(f"Error in file change handler: {e}")
    
    def is_running(self) -> bool:
        """Check if observer is running."""
        return self._running
    
    def get_watched_files(self) -> Dict[str, str]:
        """Get mapping of watched files to timeframes."""
        return {
            filename: tf.value
            for filename, tf in self.watched_files.items()
        }
    
    def run_forever(self):
        """
        Start observer and block until interrupted.
        
        This is the main entry point for the watchdog process.
        Blocks until SIGTERM or SIGINT is received.
        """
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
