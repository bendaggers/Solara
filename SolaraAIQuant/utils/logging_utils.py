"""
Solara AI Quant - Logging System

Structured logging with file rotation and colored console output.
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import logging_config, IS_WINDOWS

# Initialize colorama for Windows
if IS_WINDOWS:
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter with colored level names.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[97m',       # White
        'WARNING': '\033[93m',    # Yellow
        'ERROR': '\033[91m',      # Red
        'CRITICAL': '\033[95m',   # Magenta
        'RESET': '\033[0m'
    }
    
    def __init__(self, fmt: str, datefmt: str, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        # Store original level name
        original_levelname = record.levelname
        
        # Add color if enabled
        if self.use_colors:
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"
        
        # Format the message
        result = super().format(record)
        
        # Restore original level name
        record.levelname = original_levelname
        
        return result


def setup_logging(
    name: str = 'saq',
    console_level: str = None,
    file_level: str = None,
    log_file: Path = None
) -> logging.Logger:
    """
    Set up logging with console and file handlers.
    
    Args:
        name: Logger name
        console_level: Console log level (default from config)
        file_level: File log level (default from config)
        log_file: Log file path (default from config)
        
    Returns:
        Configured logger
    """
    console_level = console_level or logging_config.console_level
    file_level = file_level or logging_config.file_level
    log_file = log_file or logging_config.log_file
    
    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all, filter at handlers
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_formatter = ColoredFormatter(
        fmt=logging_config.format,
        datefmt=logging_config.date_format,
        use_colors=True
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=logging_config.max_bytes,
        backupCount=logging_config.backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, file_level.upper()))
    file_formatter = logging.Formatter(
        fmt=logging_config.format,
        datefmt=logging_config.date_format
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger with the given name.
    
    Args:
        name: Logger name (will be prefixed with 'saq.')
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f'saq.{name}')


# Initialize root SAQ logger
root_logger = setup_logging()


class LogMixin:
    """
    Mixin class to add logging to any class.
    
    Usage:
        class MyClass(LogMixin):
            def __init__(self):
                super().__init__()
                self.log.info("MyClass initialized")
    """
    
    @property
    def log(self) -> logging.Logger:
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


def log_section(title: str, logger: Optional[logging.Logger] = None):
    """
    Log a section header for visual separation.
    
    Args:
        title: Section title
        logger: Logger to use (default: root)
    """
    logger = logger or root_logger
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  {title}")
    logger.info("=" * 60)


def log_subsection(title: str, logger: Optional[logging.Logger] = None):
    """
    Log a subsection header.
    
    Args:
        title: Subsection title
        logger: Logger to use (default: root)
    """
    logger = logger or root_logger
    logger.info("")
    logger.info(f"  {title}")
    logger.info("  " + "-" * 40)
