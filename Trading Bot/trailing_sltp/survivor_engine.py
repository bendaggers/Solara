"""
Survivor's Edition v5.0 Engine - Modified for Solara Integration
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import csv

# ================== FIX 1: Add BOTH paths before any imports ==================

# Get current directory (where survivor_engine.py is)
current_dir = os.path.dirname(os.path.abspath(__file__))

# FIX: Add current directory to sys.path BEFORE trying to import reporter
# This allows Python to find survivor_reporter.py in the same directory
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Keep existing code for config import
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# ================== Now try imports ==================

try:
    # Import reporter from same directory (should work now)
    from survivor_reporter import SurvivorReporter
    HAS_REPORTER = True
    print("✅ Survivor Reporter import successful")
except ImportError as e:
    print(f"⚠️ Survivor Reporter import failed: {e}")
    print("⚠️ Engine will run without reporting functionality")
    HAS_REPORTER = False
    SurvivorReporter = None

try:
    import config
    print("✅ Config import successful")
except ImportError:
    print("❌ Config import failed in survivor_engine.py")
    # Fallback to default values
    config = None


class SurvivorEngineV5:
    """
    Survivor's Edition v5.0 - Modified for Solara Integration
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
    
    def __init__(self, initial_sl_pips: int = None, tp_distance_pips: int = None):
        """
        Initialize engine with config values
        
        Args:
            initial_sl_pips: Initial stop loss distance in pips (from config if None)
            tp_distance_pips: Take profit distance in pips (from config if None)
        """

        self.reporter = None
        print("✅ Survivor Engine initialized")

        # Use config values if not specified
        if initial_sl_pips is None:
            self.initial_sl_pips = config.STOP_LOSS_PIPS if config else 30
        else:
            self.initial_sl_pips = initial_sl_pips
            
        if tp_distance_pips is None:
            self.tp_distance_pips = config.TAKE_PROFIT_PIPS if config else 100
        else:
            self.tp_distance_pips = tp_distance_pips
        
        self.position_states = self._load_position_states()
        self.cycle_timestamp = datetime.now()
        
        # Market data for BB calculations - use config path
        self.market_data = self._load_market_data()
        
        # Initialize SL update statistics
        self.sl_update_stats = {'tightened': 0, 'no_change': 0, 'loosened': 0}
    
    # ================== MARKET DATA LOADING ==================


    def _load_market_data(self) -> Dict:
        """
        Load market data directly from the CSV defined in config.MARKET_DATA_FILE.
        Only required columns are used:
        pair, lower_band, middle_band, upper_band
        """
        try:
            if not config or not hasattr(config, "DATA_PATH"):
                print("❌ config.DATA_PATH not defined")
                return {}

            market_data_path = config.DATA_PATH

            if not os.path.exists(market_data_path):
                print(f"❌ Market data file not found: {market_data_path}")
                return {}

            market_data = {}
            loaded_symbols = 0

            with open(market_data_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                required_columns = {
                    "pair",
                    "lower_band",
                    "middle_band",
                    "upper_band",
                }

                if not required_columns.issubset(reader.fieldnames):
                    missing = required_columns - set(reader.fieldnames or [])
                    print(f"❌ Missing required columns: {missing}")
                    return {}

                for row in reader:
                    symbol = row.get("pair")

                    try:
                        lower = float(row["lower_band"])
                        upper = float(row["upper_band"])
                        middle = (
                            float(row["middle_band"])
                            if row.get("middle_band") not in (None, "", "nan")
                            else None
                        )
                    except (ValueError, TypeError):
                        continue

                    pip_size = self.get_pip_size(symbol)
                    if pip_size <= 0:
                        continue

                    bb_width_price = upper - lower

                    market_data[symbol] = {
                        "lower_band": lower,
                        "upper_band": upper,
                        "middle_band": middle,
                        "bb_width_price": bb_width_price,
                        "bb_width_pips": bb_width_price / pip_size,
                    }

                    loaded_symbols += 1

            print(f"✅ Loaded market data for {loaded_symbols} symbols")
            return market_data

        except Exception as e:
            print(f"❌ Error loading market data: {e}")
            return {}


    # ================== UTILITY FUNCTIONS ==================
    
    def get_pip_size(self, symbol: str) -> float:
        """Get pip size for a symbol using config PIP_SIZES"""
        try:
            if config and hasattr(config, 'PIP_SIZES'):
                # Use the same logic as SymbolHelper in mt5_manager
                symbol_upper = symbol.upper()
                
                # Check for specific patterns
                if "JPY" in symbol_upper and not any(x in symbol_upper for x in ['XAUJPY', 'XAGJPY']):
                    return config.PIP_SIZES.get("JPY", 0.01)
                elif any(x in symbol_upper for x in ['XAU', 'GOLD']):
                    return config.PIP_SIZES.get("XAU", 0.01)
                elif any(x in symbol_upper for x in ['XAG', 'SILVER']):
                    return config.PIP_SIZES.get("XAG", 0.01)
                elif any(x in symbol_upper for x in ['OIL', 'WTI', 'BRENT', 'USOIL', 'UKOIL']):
                    return config.PIP_SIZES.get("OIL", 0.01)
                elif any(x in symbol_upper for x in ['BTC']):
                    return config.PIP_SIZES.get("BTC", 1.0)
                elif any(x in symbol_upper for x in ['US30', 'NAS', 'SPX', 'DAX']):
                    return 1.0  # Indices
                else:
                    return config.PIP_SIZES.get("default", 0.0001)
        except Exception:
            pass
        
        # Fallback to hardcoded values if config fails
        symbol_upper = symbol.upper()
        
        if symbol_upper.endswith('JPY'):
            return 0.01
        if any(x in symbol_upper for x in ['XAU', 'GOLD']):
            return 0.01
        if any(x in symbol_upper for x in ['XAG', 'SILVER']):
            return 0.001
        if any(x in symbol_upper for x in ['BTC', 'ETH']):
            return 1.0
        if any(x in symbol_upper for x in ['US30', 'NAS', 'SPX', 'DAX']):
            return 1.0
        return 0.0001
    
    def get_position_id(self, position: Dict) -> str:
        """Generate unique position ID"""
        return str(position.get('ticket', 0))
    
    def calculate_profit_pips(self, position: Dict) -> float:
        """Calculate current profit in pips (positive = profit, negative = loss)"""
        try:
            symbol = position['symbol']
            pip_size = self.get_pip_size(symbol)
            
            if pip_size == 0:
                return 0.0
            
            entry = position['entry_price']
            current = position['current_price']
            
            # Calculate signed profit
            if position['type'] == 0:  # BUY
                profit = (current - entry) / pip_size
            else:  # SELL
                profit = (entry - current) / pip_size
            
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
    
    # ================== BB DATA METHODS ==================
    
    def get_bb_data(self, symbol: str) -> Optional[Dict]:
        """Get full BB data for a symbol (upper, middle, lower, width)"""
        if symbol in self.market_data:
            return self.market_data[symbol]
        return None
    
    def get_bb_width_pips(self, symbol: str) -> float:
        """Get BB width in pips for a symbol"""
        bb_data = self.get_bb_data(symbol)
        if bb_data:
            return bb_data.get('bb_width_pips', 0.0)
        return 0.0
    
    def get_bb_width_price(self, symbol: str) -> float:
        """Get BB width in price for a symbol"""
        bb_data = self.get_bb_data(symbol)
        if bb_data:
            return bb_data.get('bb_width_price', 0.0)
        return 0.0
    
    def get_bb_upper_band(self, symbol: str) -> Optional[float]:
        """Get upper Bollinger Band for a symbol"""
        bb_data = self.get_bb_data(symbol)
        if bb_data:
            return bb_data.get('upper_band')
        return None
    
    def get_bb_middle_band(self, symbol: str) -> Optional[float]:
        """Get middle Bollinger Band (SMA) for a symbol"""
        bb_data = self.get_bb_data(symbol)
        if bb_data:
            return bb_data.get('middle_band')
        return None
    
    def get_bb_lower_band(self, symbol: str) -> Optional[float]:
        """Get lower Bollinger Band for a symbol"""
        bb_data = self.get_bb_data(symbol)
        if bb_data:
            return bb_data.get('lower_band')
        return None
    
    def calculate_distance_to_bb(self, position: Dict, which_band: str = 'upper') -> float:
        """
        Calculate distance from current price to specified BB band in pips
        
        Args:
            position: Position dictionary
            which_band: 'upper', 'middle', or 'lower'
        
        Returns:
            Distance in pips (positive if price is above band for BUY, 
            negative if price is below band for SELL)
        """
        try:
            symbol = position['symbol']
            current_price = position['current_price']
            is_buy = position['type'] == 0
            pip_size = self.get_pip_size(symbol)
            
            if pip_size == 0:
                return 0.0
            
            # Get the requested band
            if which_band == 'upper':
                band_price = self.get_bb_upper_band(symbol)
            elif which_band == 'middle':
                band_price = self.get_bb_middle_band(symbol)
            elif which_band == 'lower':
                band_price = self.get_bb_lower_band(symbol)
            else:
                return 0.0
            
            if band_price is None:
                return 0.0
            
            # Calculate distance in pips
            if is_buy:
                distance = (current_price - band_price) / pip_size
            else:  # SELL
                distance = (band_price - current_price) / pip_size
            
            return round(distance, 2)
            
        except Exception:
            return 0.0
    
    def determine_stage(self, profit_pips: float) -> str:
        """Determine protection stage based on profit in pips (only positive profit)"""
        if profit_pips <= 0:
            return 'STAGE_0'
        
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
            # Look for state file in multiple locations
            possible_paths = [
                "state/position_states_v5.json",
                os.path.join(os.path.dirname(__file__), "state/position_states_v5.json"),
                "position_states_v5.json"
            ]
            
            for state_file in possible_paths:
                if os.path.exists(state_file):
                    with open(state_file, 'r') as f:
                        return json.load(f)
        except Exception:
            pass
        return {}
    
    def save_position_states(self):
        """Save position states to file"""
        try:
            state_dir = "state"
            os.makedirs(state_dir, exist_ok=True)
            state_file = os.path.join(state_dir, "position_states_v5.json")
            with open(state_file, 'w') as f:
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
        
        # Track events to log later (when reporter is initialized)
        events_to_log = {
            'new_positions': [],
            'stage_changes': []
        }
        
        # Reset stats for this cycle
        self.sl_update_stats = {'tightened': 0, 'no_change': 0, 'loosened': 0}
        
        for position in positions:
            position_id = self.get_position_id(position)
            symbol = position['symbol']
            
            profit_pips = self.calculate_profit_pips(position)
            stage = self.determine_stage(profit_pips)
            
            # Get old stage for logging
            old_stage = self.position_states.get(position_id, {}).get('current_stage', 'STAGE_0')
            
            # Check if this is a new position (track for later logging)
            is_new_position = position_id not in self.position_states
            if is_new_position:
                events_to_log['new_positions'].append(position)
            
            # Update position state
            self.update_position_state(position_id, position, stage, profit_pips)
            
            # Track stage change for later logging
            if stage != old_stage:
                events_to_log['stage_changes'].append({
                    'position': position,
                    'old_stage': old_stage,
                    'new_stage': stage,
                    'profit_pips': profit_pips,
                    'position_state': self.position_states.get(position_id, {})
                })
            
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
            
            # Calculate BB distances and get BB data
            distance_to_upper = self.calculate_distance_to_bb(position, 'upper')
            distance_to_middle = self.calculate_distance_to_bb(position, 'middle')
            distance_to_lower = self.calculate_distance_to_bb(position, 'lower')
            
            bb_data = self.get_bb_data(symbol)
            bb_upper = bb_data.get('upper_band') if bb_data else None
            bb_middle = bb_data.get('middle_band') if bb_data else None
            bb_lower = bb_data.get('lower_band') if bb_data else None
            
            # Create update record with enhanced info
            update_info = {
                'ticket': position['ticket'],
                'symbol': position['symbol'],
                'stage': stage,
                'stage_name': stage_info['name'],
                'protection_percent': int(stage_info['protection'] * 100),
                'profit_pips': round(profit_pips, 1),
                'profit_ratio': round(self.calculate_profit_ratio(position), 3),
                'bb_width_pips': round(self.get_bb_width_pips(symbol), 1),
                'bb_upper': bb_upper,
                'bb_middle': bb_middle,
                'bb_lower': bb_lower,
                'distance_to_upper': distance_to_upper,
                'distance_to_middle': distance_to_middle,
                'distance_to_lower': distance_to_lower,
                'current_sl': current_sl,
                'current_tp': current_tp,
                'new_sl': new_sl,
                'new_tp': new_tp if new_tp else current_tp,
                'needs_update': should_update_sl or should_update_tp,
                'update_sl': should_update_sl,
                'update_tp': should_update_tp,
                'sl_reason': sl_reason,
                'position_type': 'BUY' if position['type'] == 0 else 'SELL'
            }
            
            updates.append(update_info)
        
        # Print statistics
        self.print_sl_update_stats()
        
        # ================== REPORTER INITIALIZATION ==================
        # Initialize reporter ONLY AFTER all processing is complete
        if len(positions) > 0 and HAS_REPORTER and self.reporter is None:
            try:
                # Create reporter instance
                self.reporter = SurvivorReporter()
                print(f"📁 Reporter initialized for {len(positions)} positions")
                
                # Log engine cycle
                self.reporter.log_engine_cycle({
                    "cycle_timestamp": self.cycle_timestamp.isoformat(),
                    "positions_count": len(positions),
                    "engine_version": "5.0.2"
                })
                
                # Log new positions (tracked during processing)
                for position in events_to_log['new_positions']:
                    try:
                        market_context = {
                            "bb_width_pips": self.get_bb_width_pips(position['symbol']),
                            "bb_upper": self.get_bb_upper_band(position['symbol']),
                            "bb_middle": self.get_bb_middle_band(position['symbol']),
                            "bb_lower": self.get_bb_lower_band(position['symbol']),
                            "profit_ratio": self.calculate_profit_ratio(position)
                        }
                        self.reporter.log_position_opened(position, market_context)
                    except Exception as e:
                        print(f"⚠️ Failed to log new position {position['ticket']}: {e}")
                
                # Log stage changes (tracked during processing)
                for change in events_to_log['stage_changes']:
                    try:
                        position = change['position']
                        bb_data = {
                            "bb_width_pips": self.get_bb_width_pips(position['symbol']),
                            "profit_ratio": self.calculate_profit_ratio(position),
                            "distance_to_upper": self.calculate_distance_to_bb(position, 'upper'),
                            "distance_to_middle": self.calculate_distance_to_bb(position, 'middle'),
                            "distance_to_lower": self.calculate_distance_to_bb(position, 'lower'),
                            "threshold_pips": self.STAGE_DEFINITIONS[change['new_stage']]['threshold_pips'],
                            "peak_profit": change['position_state'].get('peak_profit_pips', change['profit_pips'])
                        }
                        
                        trigger = f"Profit threshold ({self.STAGE_DEFINITIONS[change['new_stage']]['threshold_pips']} pips)"
                        self.reporter.log_stage_change(
                            position, change['old_stage'], change['new_stage'], 
                            change['profit_pips'], trigger, bb_data
                        )
                    except Exception as e:
                        print(f"⚠️ Failed to log stage change for position {position['ticket']}: {e}")
                
                # Save last run report
                self._save_last_run_report(updates, positions)
                
            except Exception as e:
                print(f"⚠️ Failed to initialize reporter: {e}")
                self.reporter = None
        
        # Save states
        self.save_position_states()
        self.cleanup_old_positions()
        
        return updates


    def get_protection_percent(self, stage: str) -> int:
        """Get protection percentage for a stage"""
        if stage in self.STAGE_DEFINITIONS:
            return int(self.STAGE_DEFINITIONS[stage]['protection'] * 100)
        return 0
    
    def print_position_summary(self, position: Dict):
        """Print detailed summary for a single position"""
        profit_pips = self.calculate_profit_pips(position)
        stage = self.determine_stage(profit_pips)
        stage_info = self.STAGE_DEFINITIONS[stage]
        
        print(f"\n📊 Position #{position['ticket']} ({position['symbol']})")
        print(f"   Type: {'BUY' if position['type'] == 0 else 'SELL'}")
        print(f"   Entry: {position['entry_price']}")
        print(f"   Current: {position['current_price']}")
        print(f"   Profit: {profit_pips} pips")
        print(f"   Stage: {stage_info['name']} (Stage {stage.split('_')[1]})")
        print(f"   Protection: {int(stage_info['protection'] * 100)}%")
        print(f"   SL: {position.get('sl', 'Not set')}")
        print(f"   TP: {position.get('tp', 'Not set')}")
        
        # BB info if available
        if position['symbol'] in self.market_data:
            bb_data = self.market_data[position['symbol']]
            print(f"   BB Upper: {bb_data.get('upper_band')}")
            print(f"   BB Middle: {bb_data.get('middle_band')}")
            print(f"   BB Lower: {bb_data.get('lower_band')}")
            print(f"   BB Width: {bb_data.get('bb_width_pips', 0):.1f} pips")
            print(f"   Profit/BB Ratio: {self.calculate_profit_ratio(position):.1%}")

    # ================== REPORTER HELPER METHODS ==================
    def _log_cycle_start(self, positions_count: int):
        """Log engine cycle start if reporter exists"""
        if self.reporter:
            self.reporter.log_engine_cycle({
                "cycle_timestamp": self.cycle_timestamp.isoformat(),
                "positions_count": positions_count,
                "engine_version": "5.0.2"
            })

    def _log_new_position(self, position: Dict):
        """Log new position if reporter exists"""
        if self.reporter:
            try:
                market_context = {
                    "bb_width_pips": self.get_bb_width_pips(position['symbol']),
                    "bb_upper": self.get_bb_upper_band(position['symbol']),
                    "bb_middle": self.get_bb_middle_band(position['symbol']),
                    "bb_lower": self.get_bb_lower_band(position['symbol']),
                    "profit_ratio": self.calculate_profit_ratio(position)
                }
                self.reporter.log_position_opened(position, market_context)
            except Exception as e:
                print(f"⚠️ Failed to log new position: {e}")

    def _log_stage_change(self, position: Dict, old_stage: str, new_stage: str, 
                        profit_pips: float, position_state: Dict = None):
        """Log stage change if reporter exists"""
        if self.reporter:
            bb_data = {
                "bb_width_pips": self.get_bb_width_pips(position['symbol']),
                "profit_ratio": self.calculate_profit_ratio(position),
                "distance_to_upper": self.calculate_distance_to_bb(position, 'upper'),
                "distance_to_middle": self.calculate_distance_to_bb(position, 'middle'),
                "distance_to_lower": self.calculate_distance_to_bb(position, 'lower'),
                "threshold_pips": self.STAGE_DEFINITIONS[new_stage]['threshold_pips'],
                "peak_profit": position_state.get('peak_profit_pips', profit_pips) if position_state else profit_pips
            }
            
            trigger = f"Profit threshold ({self.STAGE_DEFINITIONS[new_stage]['threshold_pips']} pips)"
            self.reporter.log_stage_change(
                position, old_stage, new_stage, profit_pips, trigger, bb_data
            )

    def _save_last_run_report(self, updates: List[Dict], positions: List[Dict]):
        """Save last run report if reporter exists"""
        if not self.reporter:
            return
        
        # Prepare summary
        positions_modified = len([u for u in updates if u.get('needs_update', False)])
        tp_modified = len([u for u in updates if u.get('update_tp', False)])
        
        # Calculate protection added in pips
        protection_added_pips = 0.0
        for update in updates:
            if update.get('update_sl'):
                # Get symbol from update
                symbol = update.get('symbol')
                if symbol:
                    # Calculate change in pips using existing method
                    pip_size = self.get_pip_size(symbol)
                    if pip_size > 0:
                        change_price = abs(update.get('new_sl', 0) - update.get('current_sl', 0))
                        if change_price > 0:
                            change_pips = change_price / pip_size
                            protection_added_pips += change_pips
        
        # Positions in profit
        positions_in_profit = len([p for p in positions if self.calculate_profit_pips(p) > 0])
        
        cycle_summary = {
            "positions_processed": len(positions),
            "summary": {
                "positions_modified": positions_modified,
                "sl_tightened": self.sl_update_stats['tightened'],
                "tp_modified": tp_modified,
                "total_protection_added_pips": round(protection_added_pips, 1)
            },
            "system_health": {
                "active_positions": len(positions),
                "positions_in_profit": positions_in_profit,
                "positions_at_risk": len(positions) - positions_in_profit
            }
        }
        
        self.reporter.save_last_run(cycle_summary)