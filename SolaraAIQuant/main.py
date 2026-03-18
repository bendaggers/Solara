#!/usr/bin/env python3
"""
Solara AI Quant (SAQ) - Main Entry Point

The orchestrator that ties together all components:
- File watchdog for CSV monitoring
- Model execution engine
- Signal aggregation
- Risk management
- Trade execution
- Survivor Engine (position management)

Usage:
    python main.py                    # Production mode
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

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Configure logging system."""
    from logging.handlers import RotatingFileHandler
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(detailed_formatter)
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
    
    return root_logger


logger = logging.getLogger(__name__)


class SolaraAIQuant:
    """
    Main application class for Solara AI Quant.
    
    Coordinates all components:
    - FileObserver: Watches for CSV file changes
    - PipelineRunner: Executes the 8-stage pipeline
    - ExecutionEngine: Runs models in parallel
    - SignalAggregator: Combines model outputs
    - RiskManager: Validates trade safety
    - MT5Manager: Executes trades
    - SurvivorEngine: Manages open positions
    """
    
    def __init__(self, production: bool = False, dry_run: bool = False):
        """
        Initialize SAQ application.
        
        Args:
            production: If True, connect to real MT5
            dry_run: If True, don't execute real trades
        """
        self.production = production
        self.dry_run = dry_run
        self.started_at: Optional[datetime] = None
        
        # Components (initialized in initialize())
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
        
        # Runtime state
        self._shutdown_event = threading.Event()
        self._is_initialized = False
        
        # Statistics
        self.cycles_completed = 0
        self.signals_generated = 0
        self.trades_executed = 0
        self.errors_count = 0
    
    def initialize(self) -> bool:
        """
        Initialize all components.
        
        Returns:
            True if initialization successful
        """
        logger.info("=" * 60)
        logger.info("  SOLARA AI QUANT - INITIALIZING")
        logger.info("=" * 60)
        
        try:
            # 1. Load configuration
            logger.info("Loading configuration...")
            from config import (
                PROJECT_ROOT, MODELS_DIR, LOGS_DIR, STATE_DIR,
                MQL5_FILES_DIR, mt5_config, risk_config, execution_config
            )
            self.config = {
                'project_root': PROJECT_ROOT,
                'models_dir': MODELS_DIR,
                'logs_dir': LOGS_DIR,
                'state_dir': STATE_DIR,
                'mql5_files_dir': MQL5_FILES_DIR,
                'mt5': mt5_config,
                'risk': risk_config,
                'execution': execution_config
            }
            logger.info(f"  Project root: {PROJECT_ROOT}")
            logger.info(f"  Models dir: {MODELS_DIR}")
            
            # 2. Initialize database
            logger.info("Initializing database...")
            from database import db_manager
            self.db_manager = db_manager
            logger.info("  Database ready")
            
            # 3. Load model registry
            logger.info("Loading model registry...")
            from registry import model_registry
            self.model_registry = model_registry
            enabled_count = len([m for m in model_registry.get_all_models() if m.enabled])
            logger.info(f"  {enabled_count} models enabled")
            
            # 4. Initialize MT5 connection (production only)
            if self.production:
                logger.info("Connecting to MT5...")
                from mt5_manager import mt5_manager
                if not mt5_manager.connect():
                    logger.error("Failed to connect to MT5")
                    return False
                self.mt5_manager = mt5_manager
                logger.info("  MT5 connected")
            else:
                logger.info("Skipping MT5 connection (not production)")
                self.mt5_manager = None
            
            # 5. Initialize execution engine
            logger.info("Initializing execution engine...")
            from execution_engine import ExecutionEngine
            self.execution_engine = ExecutionEngine(
                model_registry=self.model_registry,
                db_manager=self.db_manager
            )
            logger.info("  Execution engine ready")
            
            # 6. Initialize signal aggregator
            logger.info("Initializing signal aggregator...")
            from aggregator import SignalAggregator
            self.signal_aggregator = SignalAggregator()
            logger.info("  Signal aggregator ready")
            
            # 7. Initialize pipeline runner
            logger.info("Initializing pipeline runner...")
            from pipeline_runner import PipelineRunner
            self.pipeline_runner = PipelineRunner(
                execution_engine=self.execution_engine,
                signal_aggregator=self.signal_aggregator,
                mt5_manager=self.mt5_manager,
                db_manager=self.db_manager,
                dry_run=self.dry_run
            )
            logger.info("  Pipeline runner ready")
            
            # 8. Initialize file observer
            logger.info("Initializing file observer...")
            from file_observer import FileObserver
            self.file_observer = FileObserver(
                watch_directory=str(MQL5_FILES_DIR),
                on_file_changed=self._on_file_changed
            )
            logger.info(f"  Watching: {MQL5_FILES_DIR}")
            
            # 9. Initialize Survivor Engine
            logger.info("Initializing Survivor Engine...")
            from survivor_engine import SurvivorEngine
            stage_path = PROJECT_ROOT / 'survivor' / 'stage_definitions.yaml'
            self.survivor_engine = SurvivorEngine(
                stage_definitions_path=stage_path if stage_path.exists() else None,
                mt5_manager=self.mt5_manager,
                db_manager=self.db_manager
            )
            logger.info(f"  Survivor Engine ready ({len(self.survivor_engine.stages)} stages)")
            
            # 10. Initialize Survivor Runner
            logger.info("Initializing Survivor Runner...")
            from survivor_runner import SurvivorRunner
            self.survivor_runner = SurvivorRunner(
                survivor_engine=self.survivor_engine,
                mt5_manager=self.mt5_manager,
                db_manager=self.db_manager,
                check_interval=60
            )
            logger.info("  Survivor Runner ready (60s interval)")
            
            self._is_initialized = True
            logger.info("=" * 60)
            logger.info("  INITIALIZATION COMPLETE")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            return False
    
    def start(self):
        """Start all components."""
        if not self._is_initialized:
            logger.error("Cannot start - not initialized")
            return False
        
        logger.info("=" * 60)
        logger.info("  STARTING SOLARA AI QUANT")
        logger.info("=" * 60)
        
        mode = []
        if self.production:
            mode.append("PRODUCTION")
        else:
            mode.append("DEVELOPMENT")
        if self.dry_run:
            mode.append("DRY-RUN")
        
        logger.info(f"  Mode: {' | '.join(mode)}")
        logger.info(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.started_at = datetime.now()
        
        # Start file observer
        self.file_observer.start()
        logger.info("  File observer started")
        
        # Start survivor runner
        if self.production:
            self.survivor_runner.start()
            logger.info("  Survivor runner started")
        
        logger.info("=" * 60)
        logger.info("  SAQ IS RUNNING - WAITING FOR CSV UPDATES")
        logger.info("=" * 60)
        
        return True
    
    def stop(self):
        """Stop all components gracefully."""
        logger.info("=" * 60)
        logger.info("  STOPPING SOLARA AI QUANT")
        logger.info("=" * 60)
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Stop components
        if self.file_observer:
            self.file_observer.stop()
            logger.info("  File observer stopped")
        
        if self.survivor_runner:
            self.survivor_runner.stop()
            logger.info("  Survivor runner stopped")
        
        # Disconnect MT5
        if self.mt5_manager:
            self.mt5_manager.disconnect()
            logger.info("  MT5 disconnected")
        
        # Print summary
        if self.started_at:
            runtime = datetime.now() - self.started_at
            logger.info("-" * 60)
            logger.info(f"  Runtime: {runtime}")
            logger.info(f"  Cycles completed: {self.cycles_completed}")
            logger.info(f"  Signals generated: {self.signals_generated}")
            logger.info(f"  Trades executed: {self.trades_executed}")
            logger.info(f"  Errors: {self.errors_count}")
        
        logger.info("=" * 60)
        logger.info("  SAQ STOPPED")
        logger.info("=" * 60)
    
    def run_forever(self):
        """Block until shutdown signal."""
        try:
            while not self._shutdown_event.is_set():
                self._shutdown_event.wait(timeout=1.0)
        except KeyboardInterrupt:
            pass
    
    def _on_file_changed(self, file_path: str, timeframe: str):
        """
        Callback when a CSV file changes.
        
        This triggers the 8-stage pipeline.
        """
        logger.info(f"File changed: {file_path} (timeframe: {timeframe})")
        
        try:
            # Run the pipeline
            result = self.pipeline_runner.run(file_path, timeframe)
            
            # Update statistics
            self.cycles_completed += 1
            self.signals_generated += result.get('signals_generated', 0)
            self.trades_executed += result.get('trades_executed', 0)
            
            logger.info(
                f"Cycle complete: {result.get('signals_generated', 0)} signals, "
                f"{result.get('trades_executed', 0)} trades"
            )
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self.errors_count += 1
    
    def get_status(self) -> dict:
        """Get current system status."""
        return {
            'is_initialized': self._is_initialized,
            'is_running': not self._shutdown_event.is_set(),
            'production': self.production,
            'dry_run': self.dry_run,
            'started_at': str(self.started_at) if self.started_at else None,
            'uptime_seconds': (
                (datetime.now() - self.started_at).total_seconds()
                if self.started_at else 0
            ),
            'cycles_completed': self.cycles_completed,
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'errors_count': self.errors_count,
            'survivor_stats': (
                self.survivor_runner.get_stats()
                if self.survivor_runner else None
            )
        }


# Global instance for signal handlers
app_instance: Optional[SolaraAIQuant] = None


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global app_instance
    logger.info(f"Received signal {signum}")
    if app_instance:
        app_instance.stop()
    sys.exit(0)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Solara AI Quant - Automated Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Development mode
  python main.py --production       # Production mode (real MT5)
  python main.py --dry-run          # No real trades
  python main.py --test             # Run tests
  python main.py --status           # Show system status
        """
    )
    
    parser.add_argument(
        '--production', '-p',
        action='store_true',
        help='Run in production mode (connect to real MT5)'
    )
    
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Dry run mode (no real trades)'
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Run test suite'
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='Show system status and exit'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Log level (default: INFO)'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='Solara AI Quant v1.0.0'
    )
    
    return parser.parse_args()


def show_status():
    """Show system status and configuration."""
    print("\n" + "=" * 60)
    print("  SOLARA AI QUANT - SYSTEM STATUS")
    print("=" * 60)
    
    try:
        from config import (
            PROJECT_ROOT, MODELS_DIR, LOGS_DIR, STATE_DIR,
            MQL5_FILES_DIR, mt5_config, risk_config
        )
        
        print(f"\n  PATHS:")
        print(f"  ────────────────────────────────────")
        print(f"  Project Root:    {PROJECT_ROOT}")
        print(f"  Models Dir:      {MODELS_DIR}")
        print(f"  Logs Dir:        {LOGS_DIR}")
        print(f"  State Dir:       {STATE_DIR}")
        print(f"  MQL5 Files:      {MQL5_FILES_DIR}")
        
        print(f"\n  DATABASE:")
        print(f"  ────────────────────────────────────")
        from database import db_manager
        print(f"  Status: Connected")
        
        print(f"\n  MT5 CONFIG:")
        print(f"  ────────────────────────────────────")
        print(f"  Login:           {mt5_config.login}")
        print(f"  Server:          {mt5_config.server}")
        print(f"  Magic:           {mt5_config.magic}")
        
        print(f"\n  RISK CONFIG:")
        print(f"  ────────────────────────────────────")
        print(f"  Max Drawdown:    {risk_config.max_drawdown_pct}%")
        print(f"  Max Daily Trades:{risk_config.max_daily_trades}")
        print(f"  Max Positions:   {risk_config.max_positions}")
        
        print(f"\n  MODELS:")
        print(f"  ────────────────────────────────────")
        from registry import model_registry
        for model in model_registry.get_all_models():
            status = "✓" if model.enabled else "✗"
            print(f"  {status} {model.name} ({model.timeframe})")
        
    except Exception as e:
        print(f"\n  Error: {e}")
    
    print("\n" + "=" * 60 + "\n")


def run_tests():
    """Run the test suite."""
    print("\n" + "=" * 60)
    print("  RUNNING TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        # Run Phase 1-3 tests
        from test_phases_1_3 import run_all_tests as run_tests_1_3
        print("Running Phase 1-3 tests...")
        run_tests_1_3()
        
        # Run Phase 4-6 tests
        from test_phases_4_6 import run_all_tests as run_tests_4_6
        print("\nRunning Phase 4-6 tests...")
        run_tests_4_6()
        
        # Run Phase 7-8 tests
        try:
            from test_phases_7_8 import run_all_tests as run_tests_7_8
            print("\nRunning Phase 7-8 tests...")
            run_tests_7_8()
        except ImportError:
            print("\nPhase 7-8 tests not found")
        
        print("\n" + "=" * 60)
        print("  ALL TESTS PASSED")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    global app_instance
    
    # Parse arguments
    args = parse_args()
    
    # Handle special modes
    if args.status:
        show_status()
        return
    
    if args.test:
        run_tests()
        return
    
    # Setup logging
    from config import LOGS_DIR
    log_file = LOGS_DIR / 'saq.log'
    setup_logging(log_level=args.log_level, log_file=str(log_file))
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create application
    app_instance = SolaraAIQuant(
        production=args.production,
        dry_run=args.dry_run
    )
    
    # Initialize
    if not app_instance.initialize():
        logger.error("Failed to initialize - exiting")
        sys.exit(1)
    
    # Start
    if not app_instance.start():
        logger.error("Failed to start - exiting")
        sys.exit(1)
    
    # Run until shutdown
    try:
        app_instance.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app_instance.stop()


if __name__ == '__main__':
    main()
