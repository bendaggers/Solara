"""
survivor/survivor_engine.py — 22-Stage Survivor Engine
=======================================================
Core logic for progressive position protection.
Migrated from legacy Solara — logic preserved, state moved to SQLite.
"""
import yaml
import structlog
from dataclasses import dataclass
from pathlib import Path
import config

log = structlog.get_logger(__name__)


@dataclass
class StageDefinition:
    name: str
    threshold_pips: int
    protection_pct: float
    tp_active: bool
    description: str


class SurvivorEngine:
    """
    Evaluates and advances positions through the 22 protection stages.
    Does not directly close positions — only modifies SL/TP.
    """

    def __init__(self, mt5_manager) -> None:
        self._mt5 = mt5_manager
        self._stages: dict[str, StageDefinition] = {}
        self._stage_order: list[str] = []
        self._load_stages()

    def _load_stages(self) -> None:
        path: Path = config.STAGE_DEFINITIONS_PATH
        with open(path) as f:
            data = yaml.safe_load(f)

        for name, values in data["stages"].items():
            self._stages[name] = StageDefinition(
                name=name,
                threshold_pips=values["threshold_pips"],
                protection_pct=values["protection_pct"],
                tp_active=values["tp_active"],
                description=values["description"],
            )
        # Order by threshold ascending
        self._stage_order = sorted(
            self._stages.keys(),
            key=lambda s: self._stages[s].threshold_pips,
        )
        log.info("survivor_stages_loaded", count=len(self._stages))

    def determine_stage(self, pips_in_profit: float) -> str:
        """Return the highest stage the position has earned based on pips in profit."""
        current_stage = "STAGE_0"
        for stage_name in self._stage_order:
            if pips_in_profit >= self._stages[stage_name].threshold_pips:
                current_stage = stage_name
            else:
                break
        return current_stage

    def calculate_new_sl(
        self,
        direction: str,
        entry_price: float,
        max_price: float,     # highest price reached (LONG) / lowest (SHORT)
        stage: StageDefinition,
        pip_size: float,
    ) -> float:
        """
        Calculate the new stop loss price for the given stage.

        For LONG:  new_sl = entry + (max_profit_pips * protection_pct * pip_size)
        For SHORT: new_sl = entry - (max_profit_pips * protection_pct * pip_size)
        """
        if direction == "LONG":
            max_profit_pips = (max_price - entry_price) / pip_size
            protected_pips = max_profit_pips * stage.protection_pct
            return entry_price + (protected_pips * pip_size)
        else:
            max_profit_pips = (entry_price - max_price) / pip_size
            protected_pips = max_profit_pips * stage.protection_pct
            return entry_price - (protected_pips * pip_size)

    def process_position(self, position, state: dict) -> dict | None:
        """
        Evaluate a single MT5 position and apply stage advancement if warranted.

        Args:
            position: MT5 position object.
            state:    Current state dict from SQLite PositionState row.

        Returns:
            Updated state dict if modification was applied, else None.
        """
        from mt5.symbol_helper import get_pip_size
        symbol_info = self._mt5.get_symbol_info(position.symbol)
        pip_size = get_pip_size(position.symbol, symbol_info.point)

        if pip_size == 0:
            log.warning("pip_size_zero", symbol=position.symbol)
            return None

        direction = "LONG" if position.type == 0 else "SHORT"

        # Current pips in profit
        if direction == "LONG":
            pips_in_profit = (position.price_current - position.price_open) / pip_size
            max_price = max(state.get("highest_price", position.price_open), position.price_current)
        else:
            pips_in_profit = (position.price_open - position.price_current) / pip_size
            max_price = min(state.get("lowest_price", position.price_open), position.price_current)

        new_stage_name = self.determine_stage(pips_in_profit)
        current_stage_name = state.get("current_stage", "STAGE_0")

        # Stages only advance forward
        current_idx = self._stage_order.index(current_stage_name)
        new_idx = self._stage_order.index(new_stage_name)

        if new_idx <= current_idx:
            return None  # No advancement

        new_stage = self._stages[new_stage_name]
        new_sl = self.calculate_new_sl(
            direction=direction,
            entry_price=position.price_open,
            max_price=max_price,
            stage=new_stage,
            pip_size=pip_size,
        )

        # SL must be strictly better than current
        current_sl = state.get("current_sl", position.sl)
        if direction == "LONG" and new_sl <= current_sl:
            return None
        if direction == "SHORT" and new_sl >= current_sl:
            return None

        # Determine TP
        new_tp = None if not new_stage.tp_active else state.get("initial_tp")

        # Apply modification via MT5
        success = self._mt5.modify_position_sl_tp(
            ticket=position.ticket,
            new_sl=round(new_sl, symbol_info.digits),
            new_tp=new_tp,
        )

        if success:
            log.info(
                "stage_advanced",
                ticket=position.ticket,
                symbol=position.symbol,
                from_stage=current_stage_name,
                to_stage=new_stage_name,
                old_sl=current_sl,
                new_sl=round(new_sl, symbol_info.digits),
                pips_in_profit=round(pips_in_profit, 1),
                protection_pct=new_stage.protection_pct,
            )
            return {
                **state,
                "current_stage": new_stage_name,
                "current_sl": round(new_sl, symbol_info.digits),
                "current_tp": new_tp,
                "highest_price": max_price if direction == "LONG" else state.get("highest_price"),
                "lowest_price": max_price if direction == "SHORT" else state.get("lowest_price"),
            }

        return None
