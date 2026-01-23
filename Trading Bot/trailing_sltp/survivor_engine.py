#!/usr/bin/env python3
# survivor_engine.py - Survivor's Edition v3.0 Engine - REVISED VERSION

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SurvivorEngineV3:
    """Survivor's Edition v3.0 Engine with Regression Defense - REVISED"""
    
# survivor_engine.py - Survivor's Edition v3.0 Engine - CORRECTED VERSION

    # ================== ORIGINAL WORKING STAGE DEFINITIONS ==================
    STAGE_DEFINITIONS = {
        'DEFENSE_0': {'threshold': 0.00, 'protection': 0.70, 'tp': False, 'priority': -1},
        'STAGE_0':  {'threshold': 0.00, 'protection': 0.00,  'tp': True,  'priority': 0},  # 0-14%
        'STAGE_1':  {'threshold': 0.15, 'protection': 0.25, 'tp': True,  'priority': 1},  # 15-29%
        'STAGE_1A': {'threshold': 0.30, 'protection': 0.40, 'tp': True,  'priority': 2},  # 30-44%
        'STAGE_2A': {'threshold': 0.45, 'protection': 0.50, 'tp': True,  'priority': 3},  # 45-59%
        'STAGE_2B': {'threshold': 0.60, 'protection': 0.60, 'tp': True,  'priority': 4},  # 60-79%
        'STAGE_2C': {'threshold': 0.70, 'protection': 0.70, 'tp': False, 'priority': 5},  # 70-89%
        'STAGE_3A': {'threshold': 0.80, 'protection': 0.75, 'tp': False, 'priority': 6},  # 80-99%
        'STAGE_3B': {'threshold': 1.00, 'protection': 0.80, 'tp': False, 'priority': 7},  # 100-119%
        'STAGE_4':  {'threshold': 1.20, 'protection': 0.85, 'tp': False, 'priority': 8},  # 120-179%
        'STAGE_5':  {'threshold': 1.80, 'protection': 0.90, 'tp': False, 'priority': 9}   # 180%+
    }

    # Stage thresholds for progression - MUST MATCH THE ABOVE!
    STAGE_THRESHOLDS = [
        ('STAGE_0', 0.00),
        ('STAGE_1', 0.15),   # Correct: 15% threshold
        ('STAGE_1A', 0.30),  # Correct: 30% threshold  
        ('STAGE_2A', 0.45),  # Correct: 45% threshold
        ('STAGE_2B', 0.60),  # Correct: 60% threshold
        ('STAGE_2C', 0.70),  # Correct: 70% threshold (not 0.80)
        ('STAGE_3A', 0.80),  # Correct: 80% threshold
        ('STAGE_3B', 1.00),  # Correct: 100% threshold (not 0.90 or 1.20)
        ('STAGE_4', 1.20),   # Correct: 120% threshold
        ('STAGE_5', 1.80)    # Correct: 180% threshold
    ]

    # Stage order for comparison
    STAGE_ORDER = ['STAGE_0', 'STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 
                'STAGE_2C', 'STAGE_3A', 'STAGE_3B', 'STAGE_4', 'STAGE_5']

    # Stages that cannot be moved back from (trailing stages)
    TRAILING_STAGES = ['STAGE_2C', 'STAGE_3A', 'STAGE_3B', 'STAGE_4', 'STAGE_5']
    
    def __init__(self, market_data_file: str, hysteresis_config: Dict, 
                 safe_distance_config: Dict, regression_config: Dict):
        self.market_data_file = market_data_file
        self.market_data = {}
        self.hysteresis = hysteresis_config
        self.safe_distance = safe_distance_config
        self.regression_config = regression_config
        
        # Position history tracking
        self.position_history = self._load_position_history()
        self.cycle_timestamp = datetime.now()
    
    # ================== POSITION HISTORY MANAGEMENT ==================
    # (This section remains the same)
    def _load_position_history(self) -> Dict:
        """Load position history from file"""
        try:
            history_file = "state/position_history.json"
            if os.path.exists(history_file):
                print(f"Loading position history from {history_file}")
                with open(history_file, 'r') as f:
                    data = json.load(f)
                
                # Convert string dates to datetime
                for pos_id, history in data.items():
                    for date_field in ['peak_profit_time', 'defense_since', 'last_update']:
                        if history.get(date_field):
                            try:
                                history[date_field] = datetime.fromisoformat(history[date_field])
                            except:
                                history[date_field] = datetime.now()
                
                print(f"Loaded position history for {len(data)} positions")
                return data
        except Exception as e:
            print(f"Could not load position history: {e}")
            print("Creating fresh position history")
        return {}
    
    def save_position_history(self):
        """Save position history to file"""
        try:
            os.makedirs("state", exist_ok=True)
            
            # Convert datetime to string
            serializable = {}
            for pos_id, history in self.position_history.items():
                serializable[pos_id] = history.copy()
                for date_field in ['peak_profit_time', 'defense_since', 'last_update']:
                    if date_field in serializable[pos_id] and serializable[pos_id][date_field]:
                        serializable[pos_id][date_field] = serializable[pos_id][date_field].isoformat()
            
            with open("state/position_history.json", 'w') as f:
                json.dump(serializable, f, indent=2)
            
            print(f"Saved position history for {len(self.position_history)} positions")
            
            # Backward compatibility
            with open("state/confirmed_stages.json", 'w') as f:
                simplified = {pid: h.get('current_stage', 'STAGE_0') 
                            for pid, h in self.position_history.items()}
                json.dump(simplified, f, indent=2)
                
        except Exception as e:
            print(f"Failed to save position history: {e}")
    
    def clean_position_history_file(self):
        """Clean corrupted position history file"""
        try:
            history_file = "state/position_history.json"
            if os.path.exists(history_file):
                # Create backup
                import shutil
                backup_file = f"{history_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(history_file, backup_file)
                print(f"Created backup: {backup_file}")
                
                # Reset history
                self.position_history = {}
                self.save_position_history()
                print("Position history cleaned and reset")
        except Exception as e:
            print(f"Error cleaning position history: {e}")
    
    def _cleanup_old_positions(self):
        """Remove positions older than 24 hours"""
        to_remove = []
        for pos_id, history in self.position_history.items():
            last_update = history.get('last_update')
            if last_update and (datetime.now() - last_update) > timedelta(hours=24):
                to_remove.append(pos_id)
        
        for pos_id in to_remove:
            del self.position_history[pos_id]
        
        if to_remove:
            print(f"Cleaned up {len(to_remove)} old positions")
    
    # ================== MARKET DATA LOADING ==================
    # (This section remains the same)
    def load_market_data(self) -> bool:
        """Load market data from JSON file"""
        try:
            if not os.path.exists(self.market_data_file):
                print(f"Market data file not found: {self.market_data_file}")
                print(f"Current directory: {os.getcwd()}")
                print(f"File path: {os.path.abspath(self.market_data_file)}")
                return False
            
            with open(self.market_data_file, 'r') as f:
                data = json.load(f)
            
            self.market_data = {}
            
            # Check if data is in 'data' key or is the main list
            if 'data' in data:
                items = data['data']
            else:
                items = data
            
            for item in items:
                symbol = item.get('pair', '')
                if not symbol:
                    continue
                
                # Extract Bollinger Bands
                lower_band = item.get('lower_band', 0)
                upper_band = item.get('upper_band', 0)
                
                # If not found, try alternative names
                if lower_band == 0:
                    lower_band = item.get('lowerBand', 0)
                if upper_band == 0:
                    upper_band = item.get('upperBand', 0)
                
                self.market_data[symbol] = {
                    'lower_band': round(lower_band, 7),
                    'upper_band': round(upper_band, 7),
                    'bb_width': round(upper_band - lower_band, 7)
                }
            
            print(f"Loaded market data for {len(self.market_data)} symbols")
            return True
            
        except Exception as e:
            print(f"Error loading market data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ================== CORE ENGINE METHODS ==================
    
    def get_pip_size(self, symbol: str) -> float:
        """Get pip size for symbol"""
        symbol_upper = symbol.upper()
        
        if "JPY" in symbol_upper and not any(x in symbol_upper for x in ['XAUJPY', 'XAGJPY']):
            return 0.01
        elif any(x in symbol_upper for x in ['XAU', 'GOLD', 'XAG', 'SILVER', 'OIL']):
            return 0.01
        elif any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'ADA', 'US30', 'NAS', 'SPX', 'DAX', 'FTSE']):
            return 1.0
        else:
            return 0.0001
    
    def calculate_profit_ratio(self, position: Dict, symbol_data: Dict) -> float:
        """Calculate profit ratio: profit_pips / bb_width"""
        try:
            symbol = position['symbol']
            pip_size = self.get_pip_size(symbol)
            
            entry = position['entry_price']
            current = position['current_price']
            
            # Calculate profit in pips (always positive for ratio)
            profit_pips = abs(current - entry) / pip_size
            
            bb_width = symbol_data['bb_width']
            bb_width_pips = bb_width / pip_size
            
            if bb_width_pips <= 0:
                return 0.0
            
            return profit_pips / bb_width_pips
            
        except Exception as e:
            print(f"Error calculating profit ratio for {position['symbol']}: {e}")
            return 0.0


    def determine_normal_stage(self, profit_ratio: float, previous_stage: str) -> str:
        """Determine normal stage with hysteresis - ORIGINAL WORKING VERSION"""
        # Find target stage based on profit ratio using thresholds
        target_stage = 'STAGE_0'
        
        # Find the highest stage that profit_ratio meets or exceeds
        for stage, threshold in reversed(self.STAGE_THRESHOLDS):
            if profit_ratio >= threshold:
                target_stage = stage
                break
        
        # Apply hysteresis ONLY if we're moving to a different stage
        if target_stage != previous_stage:
            try:
                target_idx = self.STAGE_ORDER.index(target_stage)
                prev_idx = self.STAGE_ORDER.index(previous_stage)
                
                if target_idx > prev_idx:  # Moving up
                    # Need to exceed threshold minus up_buffer
                    stage_threshold = next((t for s, t in self.STAGE_THRESHOLDS if s == target_stage), 0)
                    if profit_ratio >= stage_threshold - self.hysteresis.get('up_buffer', 0.02):
                        new_stage = target_stage
                    else:
                        new_stage = previous_stage
                else:  # Moving down
                    # Need to fall below CURRENT stage's threshold minus down_buffer
                    stage_threshold = next((t for s, t in self.STAGE_THRESHOLDS if s == previous_stage), 0)
                    if profit_ratio < stage_threshold - self.hysteresis.get('down_buffer', 0.05):
                        new_stage = target_stage
                    else:
                        new_stage = previous_stage
            except ValueError:
                new_stage = previous_stage
        else:
            new_stage = previous_stage
        
        # One-way transition - can't go back from trailing stages
        if previous_stage in self.TRAILING_STAGES:
            try:
                prev_idx = self.STAGE_ORDER.index(previous_stage)
                new_idx = self.STAGE_ORDER.index(new_stage)
                if new_idx < prev_idx:
                    print(f"One-way transition: Cannot go back from {previous_stage} to {new_stage}")
                    new_stage = previous_stage
            except ValueError:
                pass
        
        return new_stage


    # ================== REGRESSION DEFENSE SYSTEM ==================
    # (This section remains the same)
    def detect_regression(self, position_id: str, current_profit: float, 
                         current_stage: str, profit_ratio: float) -> Tuple[bool, Optional[str]]:
        """Detect regression and return defense stage if needed"""
        if position_id not in self.position_history:
            return False, None
        
        history = self.position_history[position_id]
        
        # Check if defense expired
        if history.get('defense_active', False):
            if history.get('defense_cycles', 0) >= self.regression_config.get('max_defense_cycles', 8):
                print(f"Defense expired for {position_id}")
                return False, None
        
        previous_stage = history.get('previous_stage', 'STAGE_0')
        peak_profit = history.get('peak_profit', 0.0)
        stage_history = history.get('stage_history', [])
        
        # Criterion 1: Stage backward movement
        if (previous_stage != current_stage and 
            self._is_higher_stage(previous_stage, current_stage)):
            
            min_stage = self.regression_config.get('min_stage_for_detection', 'STAGE_1')
            if self._is_higher_or_equal_stage(previous_stage, min_stage):
                stage_diff = self._stage_difference(previous_stage, current_stage)
                stage_diff_abs = abs(stage_diff)
                if stage_diff_abs >= 1:
                    print(f"REGRESSION: Stage moved back from {previous_stage} to {current_stage} (diff: {stage_diff_abs})")
                    if stage_diff_abs == 1:
                        return True, self.regression_config.get('defense_level_1', 'STAGE_2C')
                    elif stage_diff_abs == 2:
                        return True, self.regression_config.get('defense_level_2', 'STAGE_3A')
                    else:
                        return True, self.regression_config.get('defense_level_3', 'STAGE_3B')
        
        # Criterion 2: Profit give-back
        if peak_profit > 0 and current_profit > 0:
            giveback_ratio = 1.0 - (current_profit / peak_profit)
            giveback_threshold = self.regression_config.get('giveback_threshold', 0.30)
            
            if giveback_ratio >= giveback_threshold:
                # Check if position was in profit for at least 2 cycles
                if len(stage_history) >= 2:
                    print(f"REGRESSION: {giveback_ratio*100:.1f}% profit give-back")
                    if giveback_ratio <= 0.40:
                        return True, self.regression_config.get('defense_level_1', 'STAGE_2C')
                    elif giveback_ratio <= 0.50:
                        return True, self.regression_config.get('defense_level_2', 'STAGE_3A')
                    else:
                        return True, self.regression_config.get('defense_level_3', 'STAGE_3B')
        
        # Criterion 3: Momentum stagnation
        stagnation_cycles = self.regression_config.get('stagnation_cycles', 4)
        if len(stage_history) >= stagnation_cycles:
            recent_stages = stage_history[-stagnation_cycles:]
            if len(set(recent_stages)) == 1:  # All same stage
                # Check profit ratio fluctuation
                if 'profit_history' in history and len(history['profit_history']) >= stagnation_cycles:
                    recent_profits = history['profit_history'][-stagnation_cycles:]
                    max_profit = max(recent_profits)
                    min_profit = min(recent_profits)
                    
                    if max_profit > 0 and (max_profit - min_profit) / max_profit < 0.05:
                        print(f"REGRESSION: Stagnation for {stagnation_cycles} cycles")
                        return True, self.regression_config.get('defense_level_1', 'STAGE_2C')
        
        return False, None
    
    def _is_higher_stage(self, stage1: str, stage2: str) -> bool:
        """Check if stage1 is higher than stage2"""
        try:
            idx1 = self.STAGE_ORDER.index(stage1)
            idx2 = self.STAGE_ORDER.index(stage2)
            return idx1 > idx2
        except ValueError:
            return False
    
    def _is_higher_or_equal_stage(self, stage1: str, stage2: str) -> bool:
        """Check if stage1 is higher or equal to stage2"""
        try:
            idx1 = self.STAGE_ORDER.index(stage1)
            idx2 = self.STAGE_ORDER.index(stage2)
            return idx1 >= idx2
        except ValueError:
            return False
    
    def _stage_difference(self, stage1: str, stage2: str) -> int:
        """Calculate difference in stages"""
        try:
            idx1 = self.STAGE_ORDER.index(stage1)
            idx2 = self.STAGE_ORDER.index(stage2)
            return idx1 - idx2  # Positive if stage1 > stage2
        except ValueError:
            return 0
    
    def determine_final_stage(self, normal_stage: str, defense_stage: Optional[str], 
                            position_id: str) -> Tuple[str, bool]:
        """Choose final stage: MAX(normal, defense)"""
        if defense_stage is None:
            return normal_stage, False
        
        # Check if normal caught up
        if self._is_higher_or_equal_stage(normal_stage, defense_stage):
            if position_id in self.position_history:
                history = self.position_history[position_id]
                if history.get('defense_active', False):
                    print(f"Defense completed for {position_id}")
            return normal_stage, False
        
        # Activate defense
        print(f"DEFENSE ACTIVATED: {defense_stage} (was {normal_stage})")
        return defense_stage, True
    
    def update_position_history(self, position_id: str, position: Dict, 
                               profit_ratio: float, current_stage: str,
                               defense_active: bool = False):
        """Update position history"""
        if position_id not in self.position_history:
            self.position_history[position_id] = {
                'symbol': position['symbol'],
                'type': 'BUY' if position['type'] == 0 else 'SELL',
                'stage_history': [],
                'profit_history': [],
                'peak_profit': 0.0,
                'peak_profit_time': None,
                'previous_stage': 'STAGE_0',
                'current_stage': 'STAGE_0',
                'defense_active': False,
                'defense_since': None,
                'defense_cycles': 0,
                'regression_count': 0,
                'last_update': self.cycle_timestamp
            }
        
        history = self.position_history[position_id]
        
        # Calculate current profit
        symbol = position['symbol']
        pip_size = self.get_pip_size(symbol)
        current_profit = abs(position['current_price'] - position['entry_price']) / pip_size
        
        # Update profit history
        history['profit_history'].append(current_profit)
        if len(history['profit_history']) > 20:
            history['profit_history'] = history['profit_history'][-20:]
        
        # Update peak profit
        if current_profit > history['peak_profit']:
            history['peak_profit'] = current_profit
            history['peak_profit_time'] = self.cycle_timestamp
        
        # Update stage history
        if not history['stage_history'] or history['stage_history'][-1] != current_stage:
            history['stage_history'].append(current_stage)
            if len(history['stage_history']) > 10:
                history['stage_history'] = history['stage_history'][-10:]
        
        # Update defense status
        if defense_active:
            if not history['defense_active']:
                history['defense_active'] = True
                history['defense_since'] = self.cycle_timestamp
                history['defense_cycles'] = 1
                history['regression_count'] = history.get('regression_count', 0) + 1
                print(f"Defense count: {history['regression_count']}")
            else:
                history['defense_cycles'] += 1
        else:
            if history['defense_active']:
                history['defense_active'] = False
                history['defense_since'] = None
                defense_duration = history['defense_cycles']
                print(f"Defense ended after {defense_duration} cycles")
        
        # Update current info
        history['current_stage'] = current_stage
        history['previous_stage'] = current_stage
        history['last_update'] = self.cycle_timestamp
    
    # ================== SL/TP CALCULATION - REVISED ==================
    
    def calculate_sl(self, position: Dict, stage: str, symbol_data: Dict) -> Optional[float]:
        """Calculate Stop Loss based on stage - REVISED"""
        try:
            symbol = position['symbol']
            entry = position['entry_price']
            current = position['current_price']
            is_buy = (position['type'] == 0)
            pip_size = self.get_pip_size(symbol)
            
            # Calculate profit in pips
            profit_pips = abs(current - entry) / pip_size
            protection = self.STAGE_DEFINITIONS[stage]['protection']
            
            # DEFENSE_0: Emergency defense
            if stage == 'DEFENSE_0':
                if is_buy:
                    sl = current - (0.30 * profit_pips * pip_size)
                else:
                    sl = current + (0.30 * profit_pips * pip_size)
                print(f"   DEFENSE_0: Emergency protection activated")
            
            # STAGE_0: ALWAYS 30 pip fixed stop (no breakeven logic)
            elif stage == 'STAGE_0':
                if is_buy:
                    sl = entry - (30 * pip_size)
                else:
                    sl = entry + (30 * pip_size)
                print(f"   STAGE_0: Fixed 30-pip stop ({'BUY' if is_buy else 'SELL'})")
            
            # Profit-locking stages (STAGE_1 and above)
            elif stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A']:
                if is_buy:
                    sl = entry + (protection * profit_pips * pip_size)
                else:
                    sl = entry - (protection * profit_pips * pip_size)
                print(f"   {stage}: Locking {int(protection*100)}% of {profit_pips:.1f}p profit")
            
            # STAGE_3B: Hybrid protection
            elif stage == 'STAGE_3B':
                bb_width = symbol_data['bb_width']
                if is_buy:
                    profit_lock = entry + (0.80 * profit_pips * pip_size)
                    trailing = current - (0.20 * bb_width)
                    sl = max(profit_lock, trailing)
                else:
                    profit_lock = entry - (0.80 * profit_pips * pip_size)
                    trailing = current + (0.20 * bb_width)
                    sl = min(profit_lock, trailing)
                print(f"   STAGE_3B: Hybrid protection ({profit_pips:.1f}p profit)")
            
            # Trailing stages
            elif stage in ['STAGE_4', 'STAGE_5']:
                if is_buy:
                    sl = current - ((1 - protection) * profit_pips * pip_size)
                else:
                    sl = current + ((1 - protection) * profit_pips * pip_size)
                print(f"   {stage}: Trailing protection ({int(protection*100)}%)")
            
            else:
                # Fallback to 30-pip stop
                if is_buy:
                    sl = entry - (30 * pip_size)
                else:
                    sl = entry + (30 * pip_size)
                print(f"   Fallback: 30-pip stop")
            
            # Apply safe distance
            sl = self._apply_safe_distance(sl, current, is_buy, pip_size)
            
            return round(sl, 5)
            
        except Exception as e:
            print(f"Error calculating SL for {position['symbol']}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def calculate_tp(self, position: Dict, stage: str, symbol_data: Dict) -> Optional[float]:
        """Calculate Take Profit based on stage"""
        try:
            stage_info = self.STAGE_DEFINITIONS[stage]
            
            # No TP for defense stages
            if not stage_info['tp']:
                return None
            
            # Use Bollinger Bands
            is_buy = (position['type'] == 0)
            if is_buy:
                tp = symbol_data['upper_band']
            else:
                tp = symbol_data['lower_band']
            
            return round(tp, 5)
            
        except Exception as e:
            print(f"Error calculating TP: {e}")
            return None
    
    def _apply_safe_distance(self, sl: float, current_price: float, 
                           is_buy: bool, pip_size: float) -> float:
        """Ensure SL is at safe distance from current price"""
        min_pips = self.safe_distance.get('min_pips', 10)
        min_distance = min_pips * pip_size
        
        if is_buy:
            if current_price - sl < min_distance:
                sl = current_price - min_distance
                print(f"   Adjusted SL for safe distance (+{min_pips} pips)")
        else:
            if sl - current_price < min_distance:
                sl = current_price + min_distance
                print(f"   Adjusted SL for safe distance (+{min_pips} pips)")
        
        return sl
    
    def is_better_sl(self, new_sl: float, current_sl: float, is_buy: bool) -> bool:
        """Check if new SL provides better protection"""
        if abs(current_sl) < 0.00001:  # No current SL
            # Safety first: Always set SL if none exists
            print(f"   No current SL - setting SL for safety")
            return True
        
        if is_buy:
            return new_sl > current_sl  # Higher is better for BUY
        else:
            return new_sl < current_sl  # Lower is better for SELL
    
    # ================== MAIN PROCESSING ==================
    
    def process_all_positions(self, positions: List[Dict]) -> List[Dict]:
        """Process all positions with regression defense"""
        updates = []
        
        if not self.market_data:
            print("No market data loaded")
            return updates
        
        self.cycle_timestamp = datetime.now()
        
        for position in positions:
            symbol = position['symbol']
            
            if symbol not in self.market_data:
                print(f"No market data for {symbol}")
                continue
            
            symbol_data = self.market_data[symbol]
            
            # Calculate profit ratio
            profit_ratio = self.calculate_profit_ratio(position, symbol_data)
            
            # Generate position ID
            position_id = f"{position['ticket']}_{symbol}"
            
            # Get previous stage
            previous_stage = self.position_history.get(position_id, {}).get('current_stage', 'STAGE_0')
            
            # 1. Normal Protection Track
            normal_stage = self.determine_normal_stage(profit_ratio, previous_stage)
            
            # 2. Regression Defense Track
            pip_size = self.get_pip_size(symbol)
            current_profit = abs(position['current_price'] - position['entry_price']) / pip_size
            
            regression_detected, defense_stage = self.detect_regression(
                position_id, current_profit, normal_stage, profit_ratio
            )
            
            # 3. Final Stage Determination
            final_stage, defense_active = self.determine_final_stage(
                normal_stage, defense_stage, position_id
            )
            
            # Update position history
            self.update_position_history(
                position_id, position, profit_ratio, final_stage, defense_active
            )
            
            # Calculate new SL/TP
            new_sl = self.calculate_sl(position, final_stage, symbol_data)
            new_tp = self.calculate_tp(position, final_stage, symbol_data)
            
            # Check if updates needed
            current_sl = position.get('sl', 0.0)
            current_tp = position.get('tp', 0.0)
            
            should_update_sl = False
            if new_sl is not None and self.is_better_sl(new_sl, current_sl, position['type'] == 0):
                should_update_sl = True
            else:
                new_sl = None
            
            should_update_tp = (new_tp is not None and 
                               abs(new_tp - current_tp) > 0.00001)
            
            needs_update = should_update_sl or should_update_tp
            
            # Debug output
            print(f"   {symbol} #{position['ticket']}: Stage={final_stage}, Profit={current_profit:.1f}p, Ratio={profit_ratio:.3f}")
            if should_update_sl:
                print(f"     SL: {current_sl:.5f} → {new_sl:.5f}")
            if should_update_tp:
                print(f"     TP: {current_tp:.5f} → {new_tp:.5f}")
            
            # Create update info
            update_info = {
                'ticket': position['ticket'],
                'symbol': symbol,
                'stage': final_stage,
                'current_sl': current_sl,
                'current_tp': current_tp,
                'new_sl': new_sl,
                'new_tp': new_tp,
                'needs_update': needs_update,
                'protection_percent': int(self.STAGE_DEFINITIONS[final_stage]['protection'] * 100),
                'profit_ratio': round(profit_ratio, 3),
                'defense_active': defense_active,
                'regression_detected': regression_detected,
                'normal_stage': normal_stage
            }
            
            if regression_detected:
                update_info['defense_activated'] = True
                update_info['defense_stage'] = defense_stage
            
            updates.append(update_info)
        
        # Save history and cleanup
        self.save_position_history()
        self._cleanup_old_positions()
        
        return updates
    
    def get_protection_percent(self, stage: str) -> float:
        """Get protection percentage for a stage"""
        if stage in self.STAGE_DEFINITIONS:
            return self.STAGE_DEFINITIONS[stage]['protection']
        return 0.0