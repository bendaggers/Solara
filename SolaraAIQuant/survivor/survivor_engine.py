"""
Solara AI Quant - Survivor Engine

The Survivor Engine implements a 22-stage progressive trailing stop system.
It monitors open positions and moves stop-loss levels as profit increases,
locking in progressively larger percentages of profit at each stage.

Key Features:
- 22 predefined stages with increasing protection percentages
- Stages only move forward (never backward)
- Independent of model execution (runs on 60-second loop)
- Tracks high-water mark (highest/lowest price reached)
- Persists state to database for crash recovery
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


@dataclass
class StageDefinition:
    """Definition of a single trailing stop stage."""
    stage: int
    trigger_pips: float
    protection_pct: float
    description: str = ""
    
    def calculate_sl_offset(self, profit_pips: float) -> float:
        """
        Calculate SL offset from entry price.
        
        Returns:
            Offset in pips (positive = above entry for LONG)
        """
        return profit_pips * self.protection_pct


@dataclass
class SurvivorSettings:
    """Global settings for Survivor Engine."""
    min_profit_to_start: float = 10.0
    check_interval_seconds: int = 60
    use_server_time: bool = True
    pip_buffer: float = 2.0
    remove_tp_at_stage: int = 3  # Stage at which MT5 TP is removed permanently (0 = disabled)


@dataclass
class PositionUpdate:
    """Result of processing a position."""
    ticket: int
    symbol: str
    direction: str
    current_stage: int
    new_stage: int
    old_sl: Optional[float]
    new_sl: Optional[float]
    profit_pips: float
    max_profit_pips: float
    stage_changed: bool
    sl_modified: bool
    tp_removed: bool = False        # True when TP should be removed this cycle
    new_tp: Optional[float] = None  # 0.0 = remove TP in MT5; None = leave unchanged
    error_message: Optional[str] = None


class SurvivorEngine:
    """
    Implements the 22-stage progressive trailing stop system.
    
    Architecture:
    - Loads stage definitions from YAML
    - Evaluates each open position against current stage
    - Calculates new SL levels based on profit and protection percentage
    - Requests SL modifications via MT5 manager
    - Persists state changes to database
    """
    
    def __init__(
        self,
        stage_definitions_path: Optional[Path] = None,
        mt5_manager = None,
        db_manager = None
    ):
        """
        Initialize Survivor Engine.
        
        Args:
            stage_definitions_path: Path to stage_definitions.yaml
            mt5_manager: MT5 connection manager
            db_manager: Database manager for state persistence
        """
        self.mt5_manager = mt5_manager
        self.db_manager = db_manager
        
        # Load stage definitions
        self.settings = SurvivorSettings()
        self.stages: List[StageDefinition] = []
        
        if stage_definitions_path:
            self._load_definitions(stage_definitions_path)
        else:
            self._load_default_stages()
        
        # Sort stages by trigger_pips (ascending)
        self.stages.sort(key=lambda s: s.trigger_pips)
        
        logger.info(f"SurvivorEngine initialized with {len(self.stages)} stages")
    
    def _load_definitions(self, path: Path):
        """Load stage definitions from YAML file."""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Load settings
            settings = data.get('settings', {})
            self.settings = SurvivorSettings(
                min_profit_to_start=settings.get('min_profit_to_start', 10),
                check_interval_seconds=settings.get('check_interval_seconds', 60),
                use_server_time=settings.get('use_server_time', True),
                pip_buffer=settings.get('pip_buffer', 2),
                remove_tp_at_stage=settings.get('remove_tp_at_stage', 3),
            )
            
            # Load stages
            for stage_data in data.get('stages', []):
                self.stages.append(StageDefinition(
                    stage=stage_data['stage'],
                    trigger_pips=stage_data['trigger_pips'],
                    protection_pct=stage_data['protection_pct'],
                    description=stage_data.get('description', '')
                ))
            
            logger.info(f"Loaded {len(self.stages)} stages from {path}")
            
        except Exception as e:
            logger.error(f"Failed to load stage definitions: {e}")
            self._load_default_stages()
    
    def _load_default_stages(self):
        """Load default 22-stage configuration."""
        default_stages = [
            (0, 0, 0.0),
            (1, 10, 0.20), (2, 15, 0.25), (3, 20, 0.30), (4, 25, 0.35), (5, 30, 0.40),
            (6, 35, 0.45), (7, 40, 0.50), (8, 45, 0.52), (9, 50, 0.55), (10, 55, 0.58),
            (11, 60, 0.60), (12, 65, 0.62), (13, 70, 0.65), (14, 75, 0.68), (15, 80, 0.70),
            (16, 90, 0.72), (17, 100, 0.75), (18, 120, 0.78), (19, 140, 0.80),
            (20, 160, 0.82), (21, 180, 0.85), (22, 200, 0.88)
        ]
        
        for stage, trigger, protection in default_stages:
            self.stages.append(StageDefinition(
                stage=stage,
                trigger_pips=trigger,
                protection_pct=protection,
                description=f"Stage {stage}"
            ))
        
        logger.info("Loaded default stage definitions")
    
    def get_stage_for_profit(self, profit_pips: float, current_stage: int = 0) -> StageDefinition:
        """
        Determine appropriate stage for given profit level.
        
        IMPORTANT: Stages only move forward, never backward.
        
        Args:
            profit_pips: Current profit in pips
            current_stage: Current stage number
            
        Returns:
            StageDefinition for the appropriate stage
        """
        # Find highest qualifying stage
        qualifying_stage = self.stages[0]  # Default to stage 0
        
        for stage in self.stages:
            # Stage must be at or above current (no backward movement)
            if stage.stage < current_stage:
                continue
            
            # Check if profit qualifies for this stage
            if profit_pips >= stage.trigger_pips:
                qualifying_stage = stage
            else:
                # Stages are sorted, so we can stop here
                break
        
        return qualifying_stage
    
    def calculate_new_sl(
        self,
        entry_price: float,
        direction: str,
        profit_pips: float,
        stage: StageDefinition,
        pip_value: float = 0.0001
    ) -> float:
        """
        Calculate new stop-loss price for a position.
        
        Args:
            entry_price: Position entry price
            direction: 'LONG' or 'SHORT'
            profit_pips: Current profit in pips
            stage: Current stage definition
            pip_value: Value of one pip (default 0.0001 for forex)
            
        Returns:
            New stop-loss price
        """
        if stage.protection_pct == 0:
            # Stage 0: No trailing
            return None
        
        # Calculate SL offset in pips
        sl_offset_pips = stage.calculate_sl_offset(profit_pips)
        
        # Apply buffer
        sl_offset_pips -= self.settings.pip_buffer
        
        # Ensure positive protection
        sl_offset_pips = max(0, sl_offset_pips)
        
        # Convert to price
        sl_offset = sl_offset_pips * pip_value
        
        if direction == 'LONG':
            # For LONG: SL is below current price, above entry
            new_sl = entry_price + sl_offset
        else:
            # For SHORT: SL is above current price, below entry
            new_sl = entry_price - sl_offset
        
        return round(new_sl, 5)
    
    def process_position(
        self,
        ticket: int,
        symbol: str,
        direction: str,
        entry_price: float,
        current_price: float,
        current_sl: Optional[float],
        current_stage: int,
        max_profit_pips: float,
        current_tp: float = 0.0,
        pip_value: float = 0.0001
    ) -> PositionUpdate:
        """
        Process a single position and determine if SL/TP should be updated.

        Args:
            ticket: Position ticket number
            symbol: Trading symbol
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price
            current_price: Current market price
            current_sl: Current stop-loss price
            current_stage: Current Survivor stage
            max_profit_pips: Historical maximum profit reached
            current_tp: Current take-profit price (0.0 = already removed / not set)
            pip_value: Pip value for the symbol

        Returns:
            PositionUpdate with results
        """
        # Calculate current profit in pips
        if direction == 'LONG':
            profit_pips = (current_price - entry_price) / pip_value
        else:
            profit_pips = (entry_price - current_price) / pip_value
        
        # Update max profit (high-water mark)
        new_max_profit = max(max_profit_pips, profit_pips)
        
        # Check minimum profit threshold
        if new_max_profit < self.settings.min_profit_to_start:
            return PositionUpdate(
                ticket=ticket,
                symbol=symbol,
                direction=direction,
                current_stage=current_stage,
                new_stage=current_stage,
                old_sl=current_sl,
                new_sl=current_sl,
                profit_pips=profit_pips,
                max_profit_pips=new_max_profit,
                stage_changed=False,
                sl_modified=False
            )
        
        # Determine appropriate stage based on MAX profit (not current)
        # This prevents stage regression during pullbacks
        new_stage_def = self.get_stage_for_profit(new_max_profit, current_stage)
        new_stage = new_stage_def.stage
        
        # Calculate new SL based on max profit reached
        new_sl = self.calculate_new_sl(
            entry_price=entry_price,
            direction=direction,
            profit_pips=new_max_profit,  # Use max profit for SL calculation
            stage=new_stage_def,
            pip_value=pip_value
        )
        
        # Check if SL should be modified
        sl_modified = False
        if new_sl is not None:
            if current_sl is None:
                sl_modified = True
            elif direction == 'LONG' and new_sl > current_sl:
                # For LONG, only move SL up
                sl_modified = True
            elif direction == 'SHORT' and new_sl < current_sl:
                # For SHORT, only move SL down
                sl_modified = True
            else:
                # Don't move SL backward
                new_sl = current_sl
                sl_modified = False
        else:
            new_sl = current_sl
        
        stage_changed = new_stage > current_stage

        # ── TP removal (one-time action) ──────────────────────────────────────
        # Once the trailing SL is meaningful (stage >= remove_tp_at_stage),
        # remove the MT5 TP so the trade can ride the full trend wave.
        # current_tp > 0 means TP is still active in MT5 and hasn't been removed yet.
        tp_removed = False
        new_tp     = None
        remove_at  = self.settings.remove_tp_at_stage

        if (
            remove_at > 0           # feature is enabled (0 = disabled)
            and new_stage >= remove_at
            and current_tp > 0.0    # TP is still set in MT5
        ):
            tp_removed = True
            new_tp     = 0.0
            logger.info(
                f"[Survivor] {symbol} #{ticket}: TP removed at Stage {new_stage} "
                f"(profit={profit_pips:.1f}p, max={new_max_profit:.1f}p, "
                f"threshold=Stage {remove_at}) — trailing SL now sole exit"
            )

        return PositionUpdate(
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            current_stage=current_stage,
            new_stage=new_stage,
            old_sl=current_sl,
            new_sl=new_sl,
            profit_pips=profit_pips,
            max_profit_pips=new_max_profit,
            stage_changed=stage_changed,
            sl_modified=sl_modified,
            tp_removed=tp_removed,
            new_tp=new_tp,
        )
    
    def process_all_positions(self, positions: List[Dict]) -> List[PositionUpdate]:
        """
        Process all open positions.
        
        Args:
            positions: List of position dictionaries from MT5
            
        Returns:
            List of PositionUpdate results
        """
        results = []
        
        for pos in positions:
            try:
                # Get position state from database
                state = self._get_position_state(pos['ticket'])
                
                if state is None:
                    # New position - initialize state
                    state = {
                        'current_stage': 0,
                        'max_profit_pips': 0
                    }
                
                # Get pip value for symbol
                pip_value = self._get_pip_value(pos['symbol'])
                
                # Process position
                update = self.process_position(
                    ticket=pos['ticket'],
                    symbol=pos['symbol'],
                    direction=pos['direction'],
                    entry_price=pos['entry_price'],
                    current_price=pos['current_price'],
                    current_sl=pos.get('sl'),
                    current_stage=state['current_stage'],
                    max_profit_pips=state['max_profit_pips'],
                    current_tp=pos.get('tp', 0.0),
                    pip_value=pip_value,
                )
                
                results.append(update)
                
            except Exception as e:
                logger.error(f"Error processing position {pos.get('ticket')}: {e}")
                results.append(PositionUpdate(
                    ticket=pos.get('ticket', 0),
                    symbol=pos.get('symbol', 'UNKNOWN'),
                    direction=pos.get('direction', 'UNKNOWN'),
                    current_stage=0,
                    new_stage=0,
                    old_sl=None,
                    new_sl=None,
                    profit_pips=0,
                    max_profit_pips=0,
                    stage_changed=False,
                    sl_modified=False,
                    error_message=str(e)
                ))
        
        return results
    
    def apply_updates(self, updates: List[PositionUpdate]) -> Dict[str, int]:
        """
        Apply position updates (modify SL via MT5 and update database).
        
        Args:
            updates: List of PositionUpdate to apply
            
        Returns:
            Statistics dictionary
        """
        stats = {
            'processed': 0,
            'stage_changes': 0,
            'sl_modifications': 0,
            'sl_modification_failures': 0,
            'tp_removals': 0,
            'tp_removal_failures': 0,
            'errors': 0,
        }
        
        for update in updates:
            stats['processed'] += 1
            
            if update.error_message:
                stats['errors'] += 1
                continue
            
            try:
                # ── SL modification ───────────────────────────────────────────
                if update.sl_modified and self.mt5_manager:
                    success = self.mt5_manager.modify_position(
                        ticket=update.ticket,
                        sl=update.new_sl,
                        tp=update.new_tp if update.tp_removed else None,
                    )

                    if success:
                        stats['sl_modifications'] += 1
                        logger.info(
                            f"Position {update.ticket}: SL modified "
                            f"{update.old_sl:.5f} → {update.new_sl:.5f}"
                        )
                        if update.tp_removed:
                            stats['tp_removals'] += 1
                            logger.info(
                                f"Position {update.ticket} ({update.symbol}): "
                                f"TP removed — trailing SL now sole exit"
                            )
                    else:
                        stats['sl_modification_failures'] += 1
                        logger.warning(
                            f"Position {update.ticket}: SL modification failed"
                        )
                        continue

                # ── TP-only removal (SL didn't change this cycle but TP needs removing) ──
                elif update.tp_removed and self.mt5_manager:
                    success = self.mt5_manager.modify_position(
                        ticket=update.ticket,
                        sl=None,        # keep current SL
                        tp=0.0,         # remove TP
                    )
                    if success:
                        stats['tp_removals'] += 1
                        logger.info(
                            f"Position {update.ticket} ({update.symbol}): "
                            f"TP removed (SL unchanged) — trailing SL now sole exit"
                        )
                    else:
                        stats['tp_removal_failures'] += 1
                        logger.warning(
                            f"Position {update.ticket}: TP removal failed"
                        )
                        continue

                # ── Persist state changes ─────────────────────────────────────
                if update.stage_changed or update.sl_modified or update.tp_removed:
                    self._update_position_state(update)

                    if update.stage_changed:
                        stats['stage_changes'] += 1
                        logger.info(
                            f"Position {update.ticket}: Stage "
                            f"{update.current_stage} → {update.new_stage} "
                            f"(profit: {update.max_profit_pips:.1f} pips)"
                        )
                
            except Exception as e:
                logger.error(f"Error applying update for {update.ticket}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def _get_position_state(self, ticket: int) -> Optional[Dict]:
        """Get position state from database."""
        if self.db_manager is None:
            return None
        
        state = self.db_manager.get_position_state(ticket)
        
        if state is None:
            return None
        
        return {
            'current_stage': state.current_stage,
            'max_profit_pips': state.max_profit_pips or 0,
            'highest_price': state.highest_price,
            'lowest_price': state.lowest_price
        }
    
    def _update_position_state(self, update: PositionUpdate):
        """Update position state in database."""
        if self.db_manager is None:
            return

        if update.stage_changed or update.tp_removed:
            self.db_manager.update_position_stage(
                ticket=update.ticket,
                new_stage=update.new_stage,
                new_sl=update.new_sl,
                new_tp=update.new_tp,   # 0.0 when TP removed, None when unchanged
                trigger_pips=update.max_profit_pips,
                protection_pct=self.stages[update.new_stage].protection_pct
                    if update.new_stage < len(self.stages) else 0,
            )
    
    def _get_pip_value(self, symbol: str) -> float:
        """Get pip value for a symbol."""
        # Standard forex pairs
        if 'JPY' in symbol:
            return 0.01
        return 0.0001
    
    def get_stage_info(self, stage_number: int) -> Optional[StageDefinition]:
        """Get stage definition by number."""
        for stage in self.stages:
            if stage.stage == stage_number:
                return stage
        return None
    
    def get_all_stages(self) -> List[StageDefinition]:
        """Get all stage definitions."""
        return self.stages.copy()
    
    def print_stage_summary(self):
        """Print stage definitions summary."""
        print("\n" + "=" * 60)
        print("  SURVIVOR ENGINE - STAGE DEFINITIONS")
        print("=" * 60)
        print(f"\n  Min profit to start: {self.settings.min_profit_to_start} pips")
        print(f"  Check interval: {self.settings.check_interval_seconds} seconds")
        print(f"  Pip buffer: {self.settings.pip_buffer} pips\n")
        
        print(f"  {'Stage':<8} {'Trigger':<12} {'Protection':<12} {'Description'}")
        print("  " + "-" * 56)
        
        for stage in self.stages:
            print(
                f"  {stage.stage:<8} {stage.trigger_pips:<12.0f} "
                f"{stage.protection_pct*100:<12.0f}% {stage.description}"
            )
        
        print("=" * 60 + "\n")


# Global instance
survivor_engine: Optional[SurvivorEngine] = None


def get_survivor_engine() -> SurvivorEngine:
    """Get or create global Survivor Engine instance."""
    global survivor_engine
    if survivor_engine is None:
        from config import PROJECT_ROOT
        stage_path = PROJECT_ROOT / 'survivor' / 'stage_definitions.yaml'
        if not stage_path.exists():
            stage_path = None
        survivor_engine = SurvivorEngine(stage_definitions_path=stage_path)
    return survivor_engine
