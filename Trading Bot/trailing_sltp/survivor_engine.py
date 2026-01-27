"""
Survivor's Edition v5.0 Engine - Clean Version
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class SurvivorEngineV5:
    """
    Survivor's Edition v5.0 - Clean Version
    """
    
    # ================== STAGE DEFINITIONS ==================
    STAGE_DEFINITIONS = {
        'STAGE_0':  {'threshold_pips': 0,   'protection': 0.00,  'tp': True,  'name': 'Entry'},
        'STAGE_1':  {'threshold_pips': 8,   'protection': 0.10,  'tp': True,  'name': 'Initial Lock'},
        'STAGE_2':  {'threshold_pips': 10,  'protection': 0.15,  'tp': True,  'name': 'Building'},
        'STAGE_3':  {'threshold_pips': 15,  'protection': 0.20,  'tp': True,  'name': 'Developing'},
        'STAGE_4':  {'threshold_pips': 20,  'protection': 0.25,  'tp': True,  'name': 'Base Secure'},
        'STAGE_5':  {'threshold_pips': 25,  'protection': 0.30,  'tp': True,  'name': 'Quarter Lock'},
        'STAGE_6':  {'threshold_pips': 30,  'protection': 0.35,  'tp': True,  'name': 'Growing'},
        'STAGE_7':  {'threshold_pips': 35,  'protection': 0.40,  'tp': True,  'name': 'Approaching Half'},
        'STAGE_8':  {'threshold_pips': 40,  'protection': 0.45,  'tp': True,  'name': 'Near Half'},
        'STAGE_9':  {'threshold_pips': 45,  'protection': 0.50,  'tp': True,  'name': 'Half Lock'},
        'STAGE_10': {'threshold_pips': 50,  'protection': 0.55,  'tp': True,  'name': 'Majority'},
        'STAGE_11': {'threshold_pips': 55,  'protection': 0.60,  'tp': True,  'name': 'Solid'},
        'STAGE_12': {'threshold_pips': 60,  'protection': 0.65,  'tp': True,  'name': 'Strong'},
        'STAGE_13': {'threshold_pips': 65,  'protection': 0.70,  'tp': True,  'name': 'Dominant'},
        'STAGE_14': {'threshold_pips': 70,  'protection': 0.72,  'tp': False, 'name': 'Trail Start'},
        'STAGE_15': {'threshold_pips': 80,  'protection': 0.75,  'tp': False, 'name': 'Trail Active'},
        'STAGE_16': {'threshold_pips': 90,  'protection': 0.78,  'tp': False, 'name': 'Trail Strong'},
        'STAGE_17': {'threshold_pips': 100, 'protection': 0.80,  'tp': False, 'name': 'Full Lock'},
        'STAGE_18': {'threshold_pips': 120, 'protection': 0.82,  'tp': False, 'name': 'Secure'},
        'STAGE_19': {'threshold_pips': 130, 'protection': 0.84,  'tp': False, 'name': 'Very Secure'},
        'STAGE_20': {'threshold_pips': 150, 'protection': 0.86,  'tp': False, 'name': 'Excellent'},
        'STAGE_21': {'threshold_pips': 180, 'protection': 0.88,  'tp': False, 'name': 'Superior'},
        'STAGE_22': {'threshold_pips': 200, 'protection': 0.90,  'tp': False, 'name': 'Maximum'}
    }
    
    # Ordered stages
    STAGE_ORDER = [f'STAGE_{i}' for i in range(23)]
    
    def __init__(self, initial_sl_pips: int = 30):
        """
        Initialize engine
        
        Args:
            initial_sl_pips: Initial stop loss distance in pips
        """
        self.initial_sl_pips = initial_sl_pips
        self.position_states = self._load_position_states()
        self.cycle_timestamp = datetime.now()
        
        # Fixed TP distance (pips from entry)
        self.tp_distance_pips = 100
        
        # Market data for BB calculations
        self.market_data = self._load_market_data()
        
        # Initialize SL update statistics
        self.sl_update_stats = {'tightened': 0, 'no_change': 0, 'loosened': 0}
    
    # ================== MARKET DATA LOADING ==================

    def _load_market_data(self) -> Dict:
        """Load Bollinger Band data from file"""
        try:
            # Fixed path to market data
            market_data_path = r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files\marketdata_PERIOD_H4.json"
            
            if not os.path.exists(market_data_path):
                return {}
            
            with open(market_data_path, 'r') as f:
                data = json.load(f)
            
            market_data = {}
            
            # Extract the data array
            if isinstance(data, dict) and 'data' in data:
                items = data['data']
            else:
                items = data
            
            for item in items:
                symbol = item.get('pair', '')
                lower_band = item.get('lower_band')
                upper_band = item.get('upper_band')
                
                if symbol and lower_band is not None and upper_band is not None:
                    try:
                        # Calculate BB width
                        bb_width_price = float(upper_band) - float(lower_band)
                        pip_size = self.get_pip_size(symbol)
                        
                        if pip_size > 0:
                            bb_width_pips = bb_width_price / pip_size
                            market_data[symbol] = {
                                'lower_band': float(lower_band),
                                'upper_band': float(upper_band),
                                'bb_width_price': bb_width_price,
                                'bb_width_pips': bb_width_pips
                            }
                            
                    except Exception:
                        continue
            
            return market_data
            
        except Exception:
            return {}

    # ================== UTILITY FUNCTIONS ==================
    
    def get_pip_size(self, symbol: str) -> float:
        """Get pip size for a symbol"""
        symbol_upper = symbol.upper()
        
        # JPY pairs
        if symbol_upper.endswith('JPY'):
            return 0.01
        # Gold/XAU
        if any(x in symbol_upper for x in ['XAU', 'GOLD']):
            return 0.01
        # Silver/XAG
        if any(x in symbol_upper for x in ['XAG', 'SILVER']):
            return 0.001
        # Crypto
        if any(x in symbol_upper for x in ['BTC', 'ETH']):
            return 1.0
        # Indices
        if any(x in symbol_upper for x in ['US30', 'NAS', 'SPX', 'DAX']):
            return 1.0
        # Default for major forex pairs
        return 0.0001
    
    def get_position_id(self, position: Dict) -> str:
        """Generate unique position ID"""
        return str(position.get('ticket', 0))
    
    def calculate_profit_pips(self, position: Dict) -> float:
        """Calculate current profit in pips"""
        try:
            symbol = position['symbol']
            pip_size = self.get_pip_size(symbol)
            
            if pip_size == 0:
                return 0.0
            
            entry = position['entry_price']
            current = position['current_price']
            profit = abs(current - entry) / pip_size
            
            return round(profit, 2)
            
        except Exception:
            return 0.0
    
    def calculate_profit_ratio(self, position: Dict) -> float:
        """Calculate profit ratio: profit_pips / bb_width_pips"""
        symbol = position['symbol']
        
        if symbol not in self.market_data:
            return 0.0
        
        bb_data = self.market_data[symbol]
        profit_pips = self.calculate_profit_pips(position)
        bb_width_pips = bb_data['bb_width_pips']
        
        if bb_width_pips <= 0:
            return 0.0
        
        ratio = profit_pips / bb_width_pips
        return round(ratio, 3)
    
    def get_bb_width_pips(self, symbol: str) -> float:
        """Get BB width in pips for a symbol"""
        if symbol in self.market_data:
            width = self.market_data[symbol].get('bb_width_pips', 0.0)
            return round(width, 2)
        return 0.0
    
    def get_bb_width_price(self, symbol: str) -> float:
        """Get BB width in price for a symbol"""
        if symbol in self.market_data:
            return self.market_data[symbol].get('bb_width_price', 0.0)
        return 0.0
    
    def determine_stage(self, profit_pips: float) -> str:
        """Determine protection stage based on profit in pips"""
        for stage_name in reversed(self.STAGE_ORDER):
            if stage_name in self.STAGE_DEFINITIONS:
                threshold = self.STAGE_DEFINITIONS[stage_name]['threshold_pips']
                if profit_pips >= threshold:
                    return stage_name
        return 'STAGE_0'
    
    # ================== SL/TP CALCULATION ==================
    
    def calculate_sl(self, position: Dict, stage: str, profit_pips: float) -> float:
        """Calculate Stop Loss price"""
        symbol = position['symbol']
        entry = position['entry_price']
        is_buy = (position['type'] == 0)
        pip_size = self.get_pip_size(symbol)
        
        stage_info = self.STAGE_DEFINITIONS[stage]
        protection = stage_info['protection']
        
        if stage == 'STAGE_0':
            # Initial SL
            if is_buy:
                sl = entry - (self.initial_sl_pips * pip_size)
            else:
                sl = entry + (self.initial_sl_pips * pip_size)
        else:
            # Profit protection
            protected_pips = profit_pips * protection
            if is_buy:
                sl = entry + (protected_pips * pip_size)
            else:
                sl = entry - (protected_pips * pip_size)
        
        return round(sl, 5)
    
    def calculate_tp(self, position: Dict) -> Optional[float]:
        """Calculate Take Profit price"""
        symbol = position['symbol']
        entry = position['entry_price']
        is_buy = (position['type'] == 0)
        pip_size = self.get_pip_size(symbol)
        
        # Simple TP at fixed distance
        if is_buy:
            tp = entry + (self.tp_distance_pips * pip_size)
        else:
            tp = entry - (self.tp_distance_pips * pip_size)
        
        return round(tp, 5)
    
    # ================== SL UPDATE LOGIC ==================
    
    def should_update_sl(self, new_sl: float, current_sl: float, is_buy: bool) -> Tuple[bool, str]:
        """Check if we should update SL"""
        # No current SL
        if current_sl == 0.0 or current_sl is None:
            self.sl_update_stats['tightened'] += 1
            return True, "No existing SL"
        
        # No new SL calculated
        if new_sl is None:
            self.sl_update_stats['no_change'] += 1
            return False, "No new SL calculated"
        
        # Essentially the same price
        pip_size = 0.0001
        if abs(new_sl - current_sl) < (0.1 * pip_size):
            self.sl_update_stats['no_change'] += 1
            return False, "SL unchanged"
        
        # For BUY positions
        if is_buy:
            if new_sl > current_sl:
                self.sl_update_stats['tightened'] += 1
                return True, f"SL tightened"
            else:
                self.sl_update_stats['loosened'] += 1
                return False, f"SL would loosen"
        
        # For SELL positions  
        else:
            if new_sl < current_sl:
                self.sl_update_stats['tightened'] += 1
                return True, f"SL tightened"
            else:
                self.sl_update_stats['loosened'] += 1
                return False, f"SL would loosen"
    
    def print_sl_update_stats(self):
        """Print statistics about SL updates"""
        total = sum(self.sl_update_stats.values())
        if total > 0:
            print(f"\nSL Updates: Tightened={self.sl_update_stats['tightened']}, "
                  f"No Change={self.sl_update_stats['no_change']}, "
                  f"Would Loosen={self.sl_update_stats['loosened']}")
    
    # ================== POSITION STATE MANAGEMENT ==================
    
    def _load_position_states(self) -> Dict:
        """Load position states from file"""
        try:
            state_file = "state/position_states_v5.json"
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def save_position_states(self):
        """Save position states to file"""
        try:
            os.makedirs("state", exist_ok=True)
            with open("state/position_states_v5.json", 'w') as f:
                json.dump(self.position_states, f, indent=2)
        except Exception:
            pass
    
    def update_position_state(self, position_id: str, position: Dict, 
                             stage: str, profit_pips: float):
        """Update position state with simplified stage history"""
        if position_id not in self.position_states:
            self.position_states[position_id] = {
                'symbol': position['symbol'],
                'type': 'BUY' if position['type'] == 0 else 'SELL',
                'entry_price': position['entry_price'],
                'stage_history': [],  # SIMPLIFIED: Just stage names
                'profit_history': [],
                'profit_ratio_history': [],
                'bb_width_history': [],
                'bb_width_price_history': [],
                'profit_pips_threshold_history': [],
                'previous_stage': 'STAGE_0',
                'current_stage': 'STAGE_0',
                'peak_profit_pips': 0.0,
                'peak_profit_ratio': 0.0,
                'last_update': self.cycle_timestamp.isoformat()
            }
        
        state = self.position_states[position_id]
        
        # Calculate metrics
        profit_ratio = self.calculate_profit_ratio(position)
        bb_width_pips = self.get_bb_width_pips(position['symbol'])
        bb_width_price = self.get_bb_width_price(position['symbol'])
        
        # Calculate distance to next stage threshold
        next_stage_threshold = self._get_next_stage_threshold(stage)
        threshold_distance = next_stage_threshold - profit_pips if next_stage_threshold > 0 else 0
        
        # Update stage history if changed - SIMPLIFIED VERSION
        if stage != state['current_stage']:
            # Just store the stage name (no extra data)
            state['stage_history'].append(stage)
            state['previous_stage'] = state['current_stage']
            state['current_stage'] = stage
        
        # Update history arrays
        state['profit_history'].append(round(profit_pips, 2))
        state['profit_ratio_history'].append(round(profit_ratio, 3))
        state['bb_width_history'].append(round(bb_width_pips, 2))
        state['bb_width_price_history'].append(round(bb_width_price, 5))
        state['profit_pips_threshold_history'].append(round(threshold_distance, 2))
        
        # Update peak values
        if profit_pips > state.get('peak_profit_pips', 0):
            state['peak_profit_pips'] = round(profit_pips, 2)
        
        if profit_ratio > state.get('peak_profit_ratio', 0):
            state['peak_profit_ratio'] = round(profit_ratio, 3)
        
        # Keep history sizes manageable
        max_history = 50
        for key in ['profit_history', 'profit_ratio_history', 'bb_width_history', 
                   'bb_width_price_history', 'profit_pips_threshold_history']:
            if key in state and len(state[key]) > max_history:
                state[key] = state[key][-max_history:]
        
        # Keep stage history reasonable size
        if len(state['stage_history']) > 20:
            state['stage_history'] = state['stage_history'][-20:]
        
        state['last_update'] = self.cycle_timestamp.isoformat()
    
    def _get_next_stage_threshold(self, current_stage: str) -> float:
        """Get the profit threshold for the next stage"""
        try:
            current_index = self.STAGE_ORDER.index(current_stage)
            if current_index < len(self.STAGE_ORDER) - 1:
                next_stage = self.STAGE_ORDER[current_index + 1]
                return self.STAGE_DEFINITIONS[next_stage]['threshold_pips']
        except (ValueError, IndexError):
            pass
        return -1
    
    def cleanup_old_positions(self, max_age_hours: int = 72):
        """Remove old positions"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []
        
        for pos_id, state in self.position_states.items():
            last_update_str = state.get('last_update')
            if last_update_str:
                try:
                    last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
                    if last_update < cutoff_time:
                        to_remove.append(pos_id)
                except:
                    pass
        
        for pos_id in to_remove:
            del self.position_states[pos_id]
    
    # ================== MAIN PROCESSING ==================
    
    def process_all_positions(self, positions: List[Dict]) -> List[Dict]:
        """Process all positions with proper SL logic"""
        updates = []
        self.cycle_timestamp = datetime.now()
        
        # Reset stats for this cycle
        self.sl_update_stats = {'tightened': 0, 'no_change': 0, 'loosened': 0}
        
        for position in positions:
            position_id = self.get_position_id(position)
            symbol = position['symbol']
            
            profit_pips = self.calculate_profit_pips(position)
            stage = self.determine_stage(profit_pips)
            
            # Update position state (with simplified stage history)
            self.update_position_state(position_id, position, stage, profit_pips)
            
            # Get current SL/TP
            current_sl = position.get('sl', 0.0)
            current_tp = position.get('tp', 0.0)
            
            # Calculate new SL/TP
            new_sl = self.calculate_sl(position, stage, profit_pips)
            
            # Check if we should set TP
            stage_info = self.STAGE_DEFINITIONS[stage]
            if stage_info['tp']:
                new_tp = self.calculate_tp(position)
            else:
                new_tp = None
            
            # Check if new SL is better than current SL
            should_update_sl, sl_reason = self.should_update_sl(
                new_sl, current_sl, position['type'] == 0
            )
            
            # Check TP update
            should_update_tp = False
            if new_tp is not None and abs(new_tp - current_tp) > 0.00001:
                should_update_tp = True
            
            # Create update record
            update_info = {
                'ticket': position['ticket'],
                'symbol': position['symbol'],
                'stage': stage,
                'stage_name': stage_info['name'],
                'protection_percent': int(stage_info['protection'] * 100),
                'profit_pips': round(profit_pips, 1),
                'profit_ratio': round(self.calculate_profit_ratio(position), 3),
                'bb_width_pips': round(self.get_bb_width_pips(position['symbol']), 1),
                'current_sl': current_sl,
                'current_tp': current_tp,
                'new_sl': new_sl,
                'new_tp': new_tp if new_tp else current_tp,
                'needs_update': should_update_sl or should_update_tp,
                'update_sl': should_update_sl,
                'update_tp': should_update_tp
            }
            
            updates.append(update_info)
        
        # Print statistics
        self.print_sl_update_stats()
        
        # Save states
        self.save_position_states()
        self.cleanup_old_positions()
        
        return updates
    
    def get_protection_percent(self, stage: str) -> int:
        """Get protection percentage for a stage"""
        if stage in self.STAGE_DEFINITIONS:
            return int(self.STAGE_DEFINITIONS[stage]['protection'] * 100)
        return 0