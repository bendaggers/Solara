"""
main.py — Solara AI Quant Entry Point
======================================
Boots all domains in the correct order, validates configuration,
connects to MT5, and starts the File Watchdog + Survivor runner.

Usage:
    python main.py

Environment:
    Set SAQ_ENV=production for live trading.
    All credentials must be in environment variables or .env file.
"""

import sys
import signal
import logging
import structlog

import config
from config import validate, ensure_dirs


log = structlog.get_logger(__name__)


def setup_logging() -> None:
    """Configure structlog for JSON-structured output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, config.LOG_LEVEL, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def handle_shutdown(signum, frame) -> None:
    """Graceful shutdown on SIGTERM / SIGINT."""
    log.info("shutdown_signal_received", signal=signum)
    # Watchdog and runner threads are daemons — they exit with main process.
    # TODO: Phase 3 — signal watchdog to drain active cycles before exit.
    sys.exit(0)


def main() -> None:
    setup_logging()
    ensure_dirs()

    log.info(
        "saq_starting",
        env=config.SAQ_ENV,
        version="1.0.0",
        max_concurrent_models=config.MAX_CONCURRENT_MODELS,
        timeframes=config.SUPPORTED_TIMEFRAMES,
    )

    # ── Step 1: Validate configuration ───────────────────────────────────────
    errors = validate()
    if errors:
        for err in errors:
            log.error("config_validation_failed", error=err)
        log.critical("startup_aborted", reason="configuration errors must be resolved")
        sys.exit(1)

    log.info("config_validated")

    # ── Step 2: Connect to MT5 ────────────────────────────────────────────────
    from mt5.mt5_manager import MT5Manager
    mt5 = MT5Manager()
    if not mt5.connect():
        log.critical("mt5_connection_failed", "Cannot connect to MT5 — aborting startup")
        sys.exit(1)

    log.info("mt5_connected", server=config.MT5_SERVER, login=config.MT5_LOGIN)

    # ── Step 3: Initialize database ───────────────────────────────────────────
    from state.database import init_db
    init_db()
    log.info("database_initialized", path=str(config.DATABASE_PATH))

    # ── Step 4: Load and validate model registry ──────────────────────────────
    from engine.model_registry import ModelRegistry
    registry = ModelRegistry()
    registry.load()
    log.info(
        "registry_loaded",
        total_models=registry.count(),
        enabled_models=registry.count_enabled(),
        timeframes=registry.timeframes_active(),
    )

    # ── Step 5: Start Survivor Engine runner (independent timer loop) ─────────
    from survivor.survivor_runner import SurvivorRunner
    survivor = SurvivorRunner(mt5_manager=mt5, registry=registry)
    survivor.start()
    log.info(
        "survivor_started",
        interval_seconds=config.SURVIVOR_INTERVAL_SECONDS,
    )

    # ── Step 6: Register shutdown handlers ───────────────────────────────────
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # ── Step 7: Start File Watchdog (blocks until shutdown) ───────────────────
    from watchdog.file_watcher import FileWatcher
    watcher = FileWatcher(mt5_manager=mt5, registry=registry)

    log.info("watchdog_starting", watched_files={
        tf: str(path) for tf, path in config.WATCHED_FILES.items()
    })

    watcher.start()  # blocks — runs until SIGTERM/SIGINT


if __name__ == "__main__":
    main()
