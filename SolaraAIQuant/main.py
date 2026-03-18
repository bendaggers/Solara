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
    
    # Clear existing handlers
    root_logger.handlers = []
    
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
            logger.info(f"  Project root: {PROJ_ROOT}")
            logger.info(f"  Models dir: {MODELS_DIR}")
            
            # 2. Initialize database
            logger.info("Initializing database...")
            from state.database import db_manager
            self.db_manager = db_manager
            logger.info("  Database ready")
            
            # 3. Load model registry
            logger.info("Loading model registry...")
            from engine.registry import model_registry
            self.model_registry = model_registry
            enabled_count = len([m for m in model_registry.get_all_models() if m.enabled])
            logger.info(f"  {enabled_count} models enabled")
            
            # 4. Initialize MT5 connection (production only)
            if self.production:
                logger.info("Connecting to MT5...")
                from mt5.mt5_manager import mt5_manager
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
            from engine.execution_engine import ExecutionEngine
            self.execution_engine = ExecutionEngine(
                registry=self.model_registry
            )
            logger.info("  Execution engine ready")
            
            # 6. Initialize signal aggregator
            logger.info("Initializing signal aggregator...")
            from signals.aggregator import SignalAggregator
            self.signal_aggregator = SignalAggregator()
            logger.info("  Signal aggregator ready")
            
            # 7. Initialize pipeline runner
            logger.info("Initializing pipeline runner...")
            from file_watcher.pipeline_runner import PipelineRunner
            self.pipeline_runner = PipelineRunner()
            logger.info("  Pipeline runner ready")
            
            # 8. Initialize file observer
            logger.info("Initializing file observer...")
            from file_watcher.file_observer import FileObserver
            self.file_observer = FileObserver(
                watch_directory=str(MQL5_FILES_DIR),
                on_file_changed=self._on_file_changed
            )
            logger.info(f"  Watching: {MQL5_FILES_DIR}")
            
            # 9. Initialize Survivor Engine (production only)
            if self.production:
                logger.info("Initializing Survivor Engine...")
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
                    check_interval_seconds=60
                )
                logger.info("  Survivor Engine ready (22-stage trailing stop)")
            else:
                logger.info("Skipping Survivor Engine (not production)")
                self.survivor_engine = None
                self.survivor_runner = None
            
            self._is_initialized = True
            
            logger.info("=" * 60)
            logger.info("  INITIALIZATION COMPLETE")
            logger.info("=" * 60)
            logger.info(f"  Mode: {'PRODUCTION' if self.production else 'DEVELOPMENT'}")
            logger.info(f"  Dry run: {self.dry_run}")
            logger.info(f"  Models: {enabled_count} enabled")
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start(self) -> bool:
        """
        Start all services.
        
        Returns:
            True if started successfully
        """
        if not self._is_initialized:
            logger.error("Cannot start - not initialized")
            return False
        
        logger.info("=" * 60)
        logger.info("  STARTING SERVICES")
        logger.info("=" * 60)
        
        self.started_at = datetime.now()
        
        # Start file observer
        logger.info("Starting file observer...")
        self.file_observer.start()
        
        # Start survivor runner (production only)
        if self.survivor_runner:
            logger.info("Starting Survivor Engine runner...")
            self.survivor_runner.start()
        
        logger.info("=" * 60)
        logger.info("  SOLARA AI QUANT IS RUNNING")
        logger.info("=" * 60)
        logger.info("Press Ctrl+C to stop")
        
        return True
    
    def stop(self):
        """Stop all services gracefully."""
        logger.info("=" * 60)
        logger.info("  SHUTTING DOWN")
        logger.info("=" * 60)
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Stop survivor runner
        if self.survivor_runner:
            logger.info("Stopping Survivor Engine...")
            self.survivor_runner.stop()
        
        # Stop file observer
        if self.file_observer:
            logger.info("Stopping file observer...")
            self.file_observer.stop()
        
        # Disconnect MT5
        if self.mt5_manager:
            logger.info("Disconnecting from MT5...")
            self.mt5_manager.disconnect()
        
        # Print summary
        if self.started_at:
            runtime = datetime.now() - self.started_at
            logger.info("-" * 60)
            logger.info("  SESSION SUMMARY")
            logger.info("-" * 60)
            logger.info(f"  Runtime: {runtime}")
            logger.info(f"  Cycles completed: {self.cycles_completed}")
            logger.info(f"  Signals generated: {self.signals_generated}")
            logger.info(f"  Trades executed: {self.trades_executed}")
            logger.info(f"  Errors: {self.errors_count}")
        
        logger.info("=" * 60)
        logger.info("  SHUTDOWN COMPLETE")
        logger.info("=" * 60)
    
    def run_forever(self):
        """Block until shutdown signal received."""
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("\nKeyboard interrupt received")
    
    def _on_file_changed(self, file_path, timeframe=None):
        """
        Callback when CSV file changes.
        
        This triggers the 8-stage pipeline:
        1. Load CSV data
        2. Validate data
        3. Engineer features
        4. Run models
        5. Aggregate signals
        6. Check conflicts
        7. Risk management
        8. Execute trades
        """
        logger.info(f"File changed: {Path(file_path).name}")
        
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
    print("=" * 60)
    print("  SOLARA AI QUANT - STATUS")
    print("=" * 60)
    
    try:
        from config import (
            PROJECT_ROOT, MODELS_DIR, STATE_DIR, MQL5_FILES_DIR,
            mt5_config, risk_config
        )
        
        print(f"\nPaths:")
        print(f"  Project: {PROJECT_ROOT}")
        print(f"  Models:  {MODELS_DIR}")
        print(f"  State:   {STATE_DIR}")
        print(f"  Watch:   {MQL5_FILES_DIR}")
        
        print(f"\nMT5 Configuration:")
        print(f"  Server:  {mt5_config.get('server', 'Not set')}")
        print(f"  Login:   {mt5_config.get('login', 'Not set')}")
        
        print(f"\nRisk Configuration:")
        print(f"  Max positions: {risk_config.get('max_positions', 'Not set')}")
        print(f"  Max risk/trade: {risk_config.get('max_risk_per_trade', 'Not set')}%")
        
        # Check models
        print(f"\nModels:")
        from engine.registry import model_registry
        for model in model_registry.get_all_models():
            status = "✓ enabled" if model.enabled else "✗ disabled"
            print(f"  {model.name}: {status}")
        
        # Check database
        print(f"\nDatabase:")
        from state.database import db_manager
        pos_count = len(db_manager.get_all_position_states())
        print(f"  Active positions: {pos_count}")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\nError loading status: {e}")
        import traceback
        traceback.print_exc()


def run_tests():
    """Run test suite."""
    import subprocess
    
    print("Running tests...")
    print("=" * 60)
    
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
    
    parser.add_argument(
        '--production', '-p',
        action='store_true',
        help='Production mode - connect to real MT5'
    )
    
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Dry run - no real trades'
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Run test suite'
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='Show system status'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='store_true',
        help='Show version'
    )
    
    args = parser.parse_args()
    
    # Handle simple commands
    if args.version:
        print("Solara AI Quant v1.0.0")
        return
    
    if args.test:
        run_tests()
        return
    
    if args.status:
        show_status()
        return
    
    # Setup logging
    log_file = str(PROJECT_ROOT / "logs" / "saq.log")
    setup_logging(args.log_level, log_file)
    
    # Create and run application
    app = SolaraAIQuant(
        production=args.production,
        dry_run=args.dry_run
    )
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        app.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize
    if not app.initialize():
        logger.error("Failed to initialize - exiting")
        sys.exit(1)
    
    # Start
    if not app.start():
        logger.error("Failed to start - exiting")
        sys.exit(1)
    
    # Run until shutdown
    app.run_forever()
    
    # Cleanup
    app.stop()


if __name__ == "__main__":
    main()