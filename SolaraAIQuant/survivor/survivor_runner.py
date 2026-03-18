"""
Solara AI Quant - Survivor Runner

Independent 60-second loop that monitors all open positions
and applies the Survivor Engine trailing stop logic.

Runs independently of the main model execution pipeline.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SurvivorRunnerStats:
    """Statistics for Survivor Runner."""
    total_cycles: int = 0
    total_positions_processed: int = 0
    total_stage_changes: int = 0
    total_sl_modifications: int = 0
    total_errors: int = 0
    last_cycle_at: Optional[datetime] = None
    last_cycle_duration_ms: int = 0
    started_at: Optional[datetime] = None


class SurvivorRunner:
    """
    Runs Survivor Engine on a 60-second loop.
    
    Features:
    - Independent of model execution pipeline
    - Thread-safe operation
    - Graceful shutdown support
    - Statistics tracking
    - Error recovery
    """
    
    def __init__(
        self,
        survivor_engine,
        mt5_manager,
        db_manager,
        check_interval: int = 60,
        on_stage_change: Optional[Callable] = None,
        on_sl_modified: Optional[Callable] = None
    ):
        """
        Initialize Survivor Runner.
        
        Args:
            survivor_engine: SurvivorEngine instance
            mt5_manager: MT5 connection manager
            db_manager: Database manager
            check_interval: Seconds between checks (default 60)
            on_stage_change: Callback when stage changes
            on_sl_modified: Callback when SL is modified
        """
        self.survivor_engine = survivor_engine
        self.mt5_manager = mt5_manager
        self.db_manager = db_manager
        self.check_interval = check_interval
        
        # Callbacks
        self.on_stage_change = on_stage_change
        self.on_sl_modified = on_sl_modified
        
        # Thread control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False
        self._lock = threading.Lock()
        
        # Statistics
        self.stats = SurvivorRunnerStats()
        
        logger.info(f"SurvivorRunner initialized (interval: {check_interval}s)")
    
    def start(self):
        """Start the survivor runner loop."""
        with self._lock:
            if self._is_running:
                logger.warning("SurvivorRunner already running")
                return
            
            self._stop_event.clear()
            self._is_running = True
            self.stats.started_at = datetime.utcnow()
            
            self._thread = threading.Thread(
                target=self._run_loop,
                name="SurvivorRunner",
                daemon=True
            )
            self._thread.start()
            
            logger.info("SurvivorRunner started")
    
    def stop(self, timeout: float = 10.0):
        """
        Stop the survivor runner loop.
        
        Args:
            timeout: Maximum seconds to wait for thread to stop
        """
        with self._lock:
            if not self._is_running:
                return
            
            logger.info("Stopping SurvivorRunner...")
            self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            
            if self._thread.is_alive():
                logger.warning("SurvivorRunner thread did not stop gracefully")
        
        with self._lock:
            self._is_running = False
            self._thread = None
        
        logger.info("SurvivorRunner stopped")
    
    def _run_loop(self):
        """Main runner loop."""
        logger.info("SurvivorRunner loop starting...")
        
        while not self._stop_event.is_set():
            try:
                cycle_start = time.time()
                
                # Run one cycle
                self._run_cycle()
                
                # Update stats
                self.stats.last_cycle_at = datetime.utcnow()
                self.stats.last_cycle_duration_ms = int(
                    (time.time() - cycle_start) * 1000
                )
                self.stats.total_cycles += 1
                
            except Exception as e:
                logger.error(f"SurvivorRunner cycle error: {e}", exc_info=True)
                self.stats.total_errors += 1
            
            # Wait for next cycle (or stop signal)
            self._stop_event.wait(timeout=self.check_interval)
        
        logger.info("SurvivorRunner loop exiting...")
    
    def _run_cycle(self):
        """Run a single survivor cycle."""
        # 1. Get open positions from MT5
        positions = self._get_open_positions()
        
        if not positions:
            logger.debug("No open positions to process")
            return
        
        logger.debug(f"Processing {len(positions)} positions")
        
        # 2. Process all positions through Survivor Engine
        updates = self.survivor_engine.process_all_positions(positions)
        
        # 3. Apply updates (modify SL, update database)
        cycle_stats = self.survivor_engine.apply_updates(updates)
        
        # 4. Update statistics
        self.stats.total_positions_processed += cycle_stats['processed']
        self.stats.total_stage_changes += cycle_stats['stage_changes']
        self.stats.total_sl_modifications += cycle_stats['sl_modifications']
        self.stats.total_errors += cycle_stats['errors']
        
        # 5. Trigger callbacks
        for update in updates:
            if update.stage_changed and self.on_stage_change:
                try:
                    self.on_stage_change(update)
                except Exception as e:
                    logger.error(f"Stage change callback error: {e}")
            
            if update.sl_modified and self.on_sl_modified:
                try:
                    self.on_sl_modified(update)
                except Exception as e:
                    logger.error(f"SL modified callback error: {e}")
        
        # 6. Log summary if changes occurred
        if cycle_stats['stage_changes'] > 0 or cycle_stats['sl_modifications'] > 0:
            logger.info(
                f"Survivor cycle: {cycle_stats['processed']} positions, "
                f"{cycle_stats['stage_changes']} stage changes, "
                f"{cycle_stats['sl_modifications']} SL modifications"
            )
    
    def _get_open_positions(self) -> List[Dict]:
        """Get open positions from MT5."""
        if self.mt5_manager is None:
            return []
        
        try:
            mt5_positions = self.mt5_manager.get_positions()
            
            if mt5_positions is None:
                return []
            
            # Convert to list of dicts
            positions = []
            for pos in mt5_positions:
                # Get current price
                tick = self.mt5_manager.get_symbol_tick(pos.symbol)
                if tick is None:
                    continue
                
                # Determine current price based on direction
                if pos.type == 0:  # BUY
                    current_price = tick.bid  # Close at bid
                    direction = 'LONG'
                else:  # SELL
                    current_price = tick.ask  # Close at ask
                    direction = 'SHORT'
                
                positions.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'direction': direction,
                    'entry_price': pos.price_open,
                    'current_price': current_price,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'volume': pos.volume,
                    'magic': pos.magic,
                    'profit': pos.profit
                })
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def run_once(self):
        """Run a single cycle manually (for testing)."""
        self._run_cycle()
    
    def is_running(self) -> bool:
        """Check if runner is active."""
        with self._lock:
            return self._is_running
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        return {
            'is_running': self.is_running(),
            'total_cycles': self.stats.total_cycles,
            'total_positions_processed': self.stats.total_positions_processed,
            'total_stage_changes': self.stats.total_stage_changes,
            'total_sl_modifications': self.stats.total_sl_modifications,
            'total_errors': self.stats.total_errors,
            'last_cycle_at': str(self.stats.last_cycle_at) if self.stats.last_cycle_at else None,
            'last_cycle_duration_ms': self.stats.last_cycle_duration_ms,
            'started_at': str(self.stats.started_at) if self.stats.started_at else None,
            'uptime_seconds': (
                (datetime.utcnow() - self.stats.started_at).total_seconds()
                if self.stats.started_at else 0
            )
        }
    
    def print_stats(self):
        """Print current statistics."""
        stats = self.get_stats()
        
        print("\n" + "=" * 50)
        print("  SURVIVOR RUNNER STATISTICS")
        print("=" * 50)
        print(f"  Status: {'RUNNING' if stats['is_running'] else 'STOPPED'}")
        print(f"  Started: {stats['started_at']}")
        print(f"  Uptime: {stats['uptime_seconds']:.0f} seconds")
        print("-" * 50)
        print(f"  Total Cycles: {stats['total_cycles']}")
        print(f"  Positions Processed: {stats['total_positions_processed']}")
        print(f"  Stage Changes: {stats['total_stage_changes']}")
        print(f"  SL Modifications: {stats['total_sl_modifications']}")
        print(f"  Errors: {stats['total_errors']}")
        print("-" * 50)
        print(f"  Last Cycle: {stats['last_cycle_at']}")
        print(f"  Last Cycle Duration: {stats['last_cycle_duration_ms']}ms")
        print("=" * 50 + "\n")


# Global instance
survivor_runner: Optional[SurvivorRunner] = None


def get_survivor_runner() -> Optional[SurvivorRunner]:
    """Get global Survivor Runner instance."""
    global survivor_runner
    return survivor_runner


def create_survivor_runner(
    survivor_engine,
    mt5_manager,
    db_manager,
    check_interval: int = 60
) -> SurvivorRunner:
    """Create and set global Survivor Runner instance."""
    global survivor_runner
    survivor_runner = SurvivorRunner(
        survivor_engine=survivor_engine,
        mt5_manager=mt5_manager,
        db_manager=db_manager,
        check_interval=check_interval
    )
    return survivor_runner
