#!/usr/bin/env python3
"""
Solara AI Quant (SAQ) - Main Entry Point

Usage:
    python main.py                    # Development mode
    python main.py --production       # Production mode (real MT5)
    python main.py --dry-run          # Dry run (no real trades)
    python main.py --test             # Run tests
    python main.py --status           # Show system status
"""

import os
import sys
import signal
import logging
import argparse
import threading
from datetime import datetime
from typing import Optional
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Configure logging — file handler only, terminal handled by saq_log."""
    from logger import configure_stdlib_logging
    configure_stdlib_logging(log_file=log_file, level=log_level)


logger = logging.getLogger(__name__)


class SolaraAIQuant:
    """Main application class for Solara AI Quant."""

    def __init__(self, production: bool = False, dry_run: bool = False):
        self.production = production
        self.dry_run = dry_run
        self.started_at: Optional[datetime] = None

        self.config = None
        self.db_manager = None
        self.model_registry = None
        self.mt5_manager = None
        self.file_observer = None
        self.pipeline_runner = None
        self.execution_engine = None
        self.signal_aggregator = None
        self.survivor_engine = None
        self.survivor_runner = None

        self._shutdown_event = threading.Event()
        self._is_initialized = False

        self.cycles_completed = 0
        self.signals_generated = 0
        self.trades_executed = 0
        self.errors_count = 0

    def initialize(self) -> bool:
        """Initialize all components. Returns True if successful."""
        from logger import saq_log

        saq_log.startup_banner()

        try:
            # 1. Load configuration
            from config import (
                PROJECT_ROOT as PROJ_ROOT, MODELS_DIR, LOGS_DIR, STATE_DIR,
                MQL5_FILES_DIR, mt5_config, risk_config, execution_config
            )
            self.config = {
                'project_root': PROJ_ROOT,
                'models_dir': MODELS_DIR,
                'logs_dir': LOGS_DIR,
                'state_dir': STATE_DIR,
                'mql5_files_dir': MQL5_FILES_DIR,
                'mt5': mt5_config,
                'risk': risk_config,
                'execution': execution_config
            }
            logger.info(f"Config loaded — root: {PROJ_ROOT}")

            # 2. Initialize database
            from state.database import db_manager
            self.db_manager = db_manager
            saq_log.startup_item(
                "Database ready", ok=True,
                detail=str(STATE_DIR / "solara_aq.db")
            )
            logger.info("Database initialized")

            # 3. Load model registry
            from engine.registry import model_registry
            self.model_registry = model_registry
            enabled_count = len([m for m in model_registry.get_all_models() if m.enabled])
            saq_log.startup_item(
                "Registry loaded", ok=True,
                detail=f"{enabled_count} model{'s' if enabled_count != 1 else ''} enabled"
            )
            logger.info(f"Registry loaded — {enabled_count} models enabled")

            # 4. MT5 connection (production only)
            if self.production:
                from mt5.mt5_manager import mt5_manager
                if not mt5_manager.connect():
                    saq_log.startup_failed("Failed to connect to MT5")
                    return False
                self.mt5_manager = mt5_manager
                saq_log.startup_item("MT5 connected", ok=True,
                    detail=str(mt5_config.server))
                logger.info("MT5 connected")
            else:
                self.mt5_manager = None
                saq_log.startup_item("MT5", ok=False,
                    detail="skipped (not production)")
                logger.info("MT5 skipped — not production")

            # 5. Execution engine
            from engine.execution_engine import ExecutionEngine
            self.execution_engine = ExecutionEngine(registry=self.model_registry)
            saq_log.startup_item(
                "Execution engine", ok=True,
                detail=f"{execution_config.max_concurrent_models} workers"
            )
            logger.info("Execution engine ready")

            # 6. Signal aggregator
            from signals.aggregator import SignalAggregator
            self.signal_aggregator = SignalAggregator()
            saq_log.startup_item("Signal aggregator")
            logger.info("Signal aggregator ready")

            # 7. Pipeline runner
            from file_watcher.pipeline_runner import PipelineRunner
            self.pipeline_runner = PipelineRunner()
            saq_log.startup_item("Pipeline runner")
            logger.info("Pipeline runner ready")

            # 8. File observer
            from file_watcher.file_observer import FileObserver
            self.file_observer = FileObserver(
                watch_directory=str(MQL5_FILES_DIR),
                on_file_changed=self._on_file_changed
            )
            saq_log.startup_watched_files(
                list(self.file_observer.get_watched_files().keys())
            )
            logger.info(f"File observer ready — watching {MQL5_FILES_DIR}")

            # 9. Survivor Engine (production only)
            if self.production:
                from survivor.survivor_engine import SurvivorEngine
                from survivor.survivor_runner import SurvivorRunner

                stage_defs_path = PROJECT_ROOT / "survivor" / "stage_definitions.yaml"
                self.survivor_engine = SurvivorEngine(
                    mt5_manager=self.mt5_manager,
                    db_manager=self.db_manager,
                    stage_definitions_path=str(stage_defs_path)
                )
                self.survivor_runner = SurvivorRunner(
                    survivor_engine=self.survivor_engine,
                    mt5_manager=self.mt5_manager,
                    db_manager=self.db_manager,
                    check_interval=60
                )
                saq_log.startup_item("Survivor engine", ok=True,
                    detail="22-stage trailing stop")
                logger.info("Survivor engine ready")
            else:
                self.survivor_engine = None
                self.survivor_runner = None
                saq_log.startup_item("Survivor engine", ok=False,
                    detail="skipped (not production)")

            self._is_initialized = True
            saq_log.startup_mode(
                'PRODUCTION' if self.production else 'DEVELOPMENT',
                self.dry_run
            )
            logger.info(
                f"Init complete — "
                f"mode={'PRODUCTION' if self.production else 'DEVELOPMENT'} "
                f"dry_run={self.dry_run} models={enabled_count}"
            )
            return True

        except Exception as e:
            saq_log.startup_failed(str(e))
            logger.exception(f"Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start(self) -> bool:
        """Start all services. Returns True if started successfully."""
        from logger import saq_log

        if not self._is_initialized:
            saq_log.error("Cannot start — not initialized")
            return False

        self.started_at = datetime.now()

        self.file_observer.start()

        if self.survivor_runner:
            self.survivor_runner.start()

        saq_log.startup_ready()
        logger.info("SAQ started — watching for CSV updates")
        return True

    def stop(self):
        """Stop all services gracefully."""
        from logger import saq_log

        self._shutdown_event.set()

        if self.survivor_runner:
            self.survivor_runner.stop()

        if self.file_observer:
            self.file_observer.stop()

        if self.mt5_manager:
            self.mt5_manager.disconnect()

        if self.started_at:
            runtime = datetime.now() - self.started_at
            print()
            saq_log.info("Session summary",
                f"runtime {str(runtime).split('.')[0]} · "
                f"cycles {self.cycles_completed} · "
                f"signals {self.signals_generated} · "
                f"trades {self.trades_executed} · "
                f"errors {self.errors_count}"
            )

        logger.info("SAQ stopped")

    def run_forever(self):
        """Block until shutdown signal received."""
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            pass

    def _on_file_changed(self, file_path, timeframe=None):
        """Callback when a watched CSV file changes."""
        try:
            result = self.pipeline_runner.run(file_path, timeframe)
            self.cycles_completed += 1
            if result:
                self.signals_generated += result.signals_generated
                self.trades_executed += result.trades_executed
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.errors_count += 1


def show_status():
    """Show system status and configuration."""
    from logger import saq_log
    print()
    saq_log.info("SOLARA AI QUANT — STATUS")
    print()

    try:
        from config import (
            PROJECT_ROOT, MODELS_DIR, STATE_DIR, MQL5_FILES_DIR,
            mt5_config, risk_config
        )

        saq_log.ok("Project", str(PROJECT_ROOT))
        saq_log.ok("Models",  str(MODELS_DIR))
        saq_log.ok("State",   str(STATE_DIR))
        saq_log.ok("Watch",   str(MQL5_FILES_DIR))

        print()
        saq_log.ok("MT5 server", str(mt5_config.get('server', 'Not set')))
        saq_log.ok("MT5 login",  str(mt5_config.get('login',  'Not set')))

        print()
        from engine.registry import model_registry
        for model in model_registry.get_all_models():
            saq_log.startup_item(
                model.name, ok=model.enabled,
                detail="enabled" if model.enabled else "disabled"
            )

        print()
        from state.database import db_manager
        pos_count = len(db_manager.get_all_position_states())
        saq_log.ok("Active positions", str(pos_count))

    except Exception as e:
        saq_log.error("Error loading status", str(e))
        import traceback
        traceback.print_exc()


def run_tests():
    """Run test suite."""
    import subprocess
    print("Running tests...")

    test_files = [
        "tests/test_phases_1_3.py",
        "tests/test_phases_4_6.py",
        "tests/test_phases_7_8.py",
    ]

    for test_file in test_files:
        test_path = PROJECT_ROOT / test_file
        if test_path.exists():
            print(f"\n--- {test_file} ---")
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_path), "-v"],
                cwd=str(PROJECT_ROOT)
            )
            if result.returncode != 0:
                print(f"FAILED: {test_file}")
        else:
            print(f"Skipping {test_file} (not found)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Solara AI Quant - Automated Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    Development mode
  python main.py --production       Production mode (real MT5)
  python main.py -p --dry-run       Production with no real trades
  python main.py --test             Run test suite
  python main.py --status           Show configuration
        """
    )

    parser.add_argument('--production', '-p', action='store_true',
        help='Production mode - connect to real MT5')
    parser.add_argument('--dry-run', '-d', action='store_true',
        help='Dry run - no real trades')
    parser.add_argument('--test', '-t', action='store_true',
        help='Run test suite')
    parser.add_argument('--status', '-s', action='store_true',
        help='Show system status')
    parser.add_argument('--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO', help='Logging level')
    parser.add_argument('--version', '-v', action='store_true',
        help='Show version')

    args = parser.parse_args()

    if args.version:
        print("Solara AI Quant v1.0.0")
        return

    if args.test:
        run_tests()
        return

    if args.status:
        show_status()
        return

    log_file = str(PROJECT_ROOT / "logs" / "saq.log")
    setup_logging(args.log_level, log_file)

    app = SolaraAIQuant(
        production=args.production,
        dry_run=args.dry_run
    )

    def signal_handler(signum, frame):
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not app.initialize():
        sys.exit(1)

    if not app.start():
        sys.exit(1)

    app.run_forever()
    app.stop()


if __name__ == "__main__":
    main()
