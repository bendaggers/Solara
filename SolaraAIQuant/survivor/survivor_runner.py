"""
survivor/survivor_runner.py — Survivor Engine Timer Loop
==========================================================
Runs the SurvivorEngine on an independent timer every SURVIVOR_INTERVAL_SECONDS.
Completely independent of the watchdog pipeline — runs even when models are executing.
"""
import time
import threading
import structlog
from survivor.survivor_engine import SurvivorEngine
import config

log = structlog.get_logger(__name__)


class SurvivorRunner:
    """Starts and manages the Survivor Engine background loop."""

    def __init__(self, mt5_manager, registry) -> None:
        self._mt5 = mt5_manager
        self._registry = registry
        self._engine = SurvivorEngine(mt5_manager=mt5_manager)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the survivor loop in a daemon background thread."""
        self._thread = threading.Thread(
            target=self._loop,
            name="SAQ_Survivor",
            daemon=True,
        )
        self._thread.start()
        log.info("survivor_runner_started", interval=config.SURVIVOR_INTERVAL_SECONDS)

    def stop(self) -> None:
        """Signal the survivor loop to stop after its current iteration."""
        self._stop_event.set()

    def _loop(self) -> None:
        """Main survivor loop — runs every SURVIVOR_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            try:
                self._run_cycle()
            except Exception as e:
                log.error("survivor_cycle_error", error=str(e), exc_info=True)
            self._stop_event.wait(timeout=config.SURVIVOR_INTERVAL_SECONDS)

    def _run_cycle(self) -> None:
        """One survivor cycle — check and update all open positions."""
        positions = self._mt5.get_all_positions()
        if not positions:
            return

        # TODO: Load position states from SQLite, pass to engine, save updates
        for position in positions:
            # Stub state — will be replaced by SQLite lookup in Phase 2
            state = {
                "current_stage": "STAGE_0",
                "current_sl": position.sl,
                "current_tp": position.tp if position.tp != 0 else None,
                "initial_tp": position.tp if position.tp != 0 else None,
                "highest_price": position.price_current,
                "lowest_price": position.price_current,
            }
            self._engine.process_position(position=position, state=state)

        log.debug("survivor_cycle_complete", positions_checked=len(positions))
