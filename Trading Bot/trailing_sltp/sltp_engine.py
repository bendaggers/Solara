import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SLTPEngine:
    """Enhanced SL/TP engine with stage-based definitions"""
    
    def __init__(self, market_data_file: str, stage_hysteresis: Dict, safe_distance_config: Dict):
        self.market_data_file = market_data_file
        self.market_data = {}
        self.stage_hysteresis = stage_hysteresis
        self.safe_distance_config = safe_distance_config
        
        # Pip sizes
        self.pip_sizes = {
            'default': 0.0001, 'JPY': 0.01, 'XAU': 0.01, 'XAG': 0.01,
            'OIL': 0.01, 'CRYPTO': 1.0, 'INDICES': 1.0
        }
        
        # Enhanced 10-stage thresholds
        self.stage_thresholds = {
            'STAGE_0': 0.25,
            'STAGE_1': 0.40,
            'STAGE_1A': 0.50,
            'STAGE_2A': 0.60,
            'STAGE_2B': 0.70,
            'STAGE_2C': 0.80,
            'STAGE_3A': 0.90,
            'STAGE_3B': 1.20,
            'STAGE_4': 1.80,
            'STAGE_5': float('inf')
        }
        
        # Stage definitions (BUY and SELL versions)
        self.stage_definitions = self._create_stage_definitions()
        
        # Load confirmed stages
        self.confirmed_stages = self.load_confirmed_stages()
        self.stage_entry_times = {}
    
    def _create_stage_definitions(self) -> Dict:
        """Create stage definitions once"""
        return {
            'STAGE_0': {
                'buy': {
                    'sl_formula': 'entry - (30 × pip_size)',
                    'tp_formula': 'entry + (40 × pip_size)',
                    'profit_threshold': 0.25,
                    'description': 'Initial position: profit < 25% of BB width'
                },
                'sell': {
                    'sl_formula': 'entry + (30 × pip_size)',
                    'tp_formula': 'entry - (40 × pip_size)',
                    'profit_threshold': 0.25,
                    'description': 'Initial position: profit < 25% of BB width'
                }
            },
            'STAGE_1': {
                'buy': {
                    'sl_formula': 'entry + (0.40 × profit_pips × pip_size)',
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.40,
                    'protection_percent': 0.40,
                    'description': '25-39% profit: protect 40% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.40 × profit_pips × pip_size)',
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.40,
                    'protection_percent': 0.40,
                    'description': '25-39% profit: protect 40% of gains'
                }
            },
            'STAGE_1A': {
                'buy': {
                    'sl_formula': 'entry + (0.55 × profit_pips × pip_size)',
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.50,
                    'protection_percent': 0.55,
                    'description': '40-49% profit: protect 55% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.55 × profit_pips × pip_size)',
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.50,
                    'protection_percent': 0.55,
                    'description': '40-49% profit: protect 55% of gains'
                }
            },
            'STAGE_2A': {
                'buy': {
                    'sl_formula': 'max(entry + (0.65 × profit_pips × pip_size), middle_bb - (0.04 × bb_width))',
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.60,
                    'protection_percent': 0.65,
                    'bb_buffer': -0.04,
                    'description': '50-59% profit: 65% protection OR middle BB - 4%'
                },
                'sell': {
                    'sl_formula': 'min(entry - (0.65 × profit_pips × pip_size), middle_bb + (0.04 × bb_width))',
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.60,
                    'protection_percent': 0.65,
                    'bb_buffer': 0.04,
                    'description': '50-59% profit: 65% protection OR middle BB + 4%'
                }
            },
            'STAGE_2B': {
                'buy': {
                    'sl_formula': 'max(entry + (0.75 × profit_pips × pip_size), middle_bb + (0.05 × bb_width))',
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.70,
                    'protection_percent': 0.75,
                    'bb_buffer': 0.05,
                    'description': '60-69% profit: 75% protection OR middle BB + 5%'
                },
                'sell': {
                    'sl_formula': 'min(entry - (0.75 × profit_pips × pip_size), middle_bb - (0.05 × bb_width))',
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.70,
                    'protection_percent': 0.75,
                    'bb_buffer': -0.05,
                    'description': '60-69% profit: 75% protection OR middle BB - 5%'
                }
            },
            'STAGE_2C': {
                'buy': {
                    'sl_formula': 'max(entry + (0.80 × profit_pips × pip_size), current_price - (0.08 × bb_width))',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.80,
                    'protection_percent': 0.80,
                    'trailing_percent': 0.08,
                    'description': '70-79% profit: 80% protection OR price - 8% trailing'
                },
                'sell': {
                    'sl_formula': 'min(entry - (0.80 × profit_pips × pip_size), current_price + (0.08 × bb_width))',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.80,
                    'protection_percent': 0.80,
                    'trailing_percent': 0.08,
                    'description': '70-79% profit: 80% protection OR price + 8% trailing'
                }
            },
            'STAGE_3A': {
                'buy': {
                    'sl_formula': 'max(entry + (0.85 × profit_pips × pip_size), current_price - (0.06 × bb_width))',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.90,
                    'protection_percent': 0.85,
                    'trailing_percent': 0.06,
                    'description': '80-89% profit: 85% protection OR price - 6% trailing'
                },
                'sell': {
                    'sl_formula': 'min(entry - (0.85 × profit_pips × pip_size), current_price + (0.06 × bb_width))',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.90,
                    'protection_percent': 0.85,
                    'trailing_percent': 0.06,
                    'description': '80-89% profit: 85% protection OR price + 6% trailing'
                }
            },
            'STAGE_3B': {
                'buy': {
                    'sl_formula': 'current_price - (0.03 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.20,
                    'trailing_percent': 0.03,
                    'description': '90-119% profit: 3% trailing stop'
                },
                'sell': {
                    'sl_formula': 'current_price + (0.03 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.20,
                    'trailing_percent': 0.03,
                    'description': '90-119% profit: 3% trailing stop'
                }
            },
            'STAGE_4': {
                'buy': {
                    'sl_formula': 'current_price - (0.02 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.80,
                    'trailing_percent': 0.02,
                    'description': '120-179% profit: 2% trailing stop'
                },
                'sell': {
                    'sl_formula': 'current_price + (0.02 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.80,
                    'trailing_percent': 0.02,
                    'description': '120-179% profit: 2% trailing stop'
                }
            },
            'STAGE_5': {
                'buy': {
                    'sl_formula': 'current_price - (0.015 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': float('inf'),
                    'trailing_percent': 0.015,
                    'description': '180%+ profit: 1.5% ultra-tight trailing'
                },
                'sell': {
                    'sl_formula': 'current_price + (0.015 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': float('inf'),
                    'trailing_percent': 0.015,
                    'description': '180%+ profit: 1.5% ultra-tight trailing'
                }
            }
        }
    
    def load_confirmed_stages(self) -> Dict:
        """Load confirmed stages from file"""
        state_file = "state/confirmed_stages.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_confirmed_stages(self):
        """Save confirmed stages to file"""
        state_file = "state/confirmed_stages.json"
        try:
            os.makedirs("state", exist_ok=True)
            with open(state_file, 'w') as f:
                json.dump(self.confirmed_stages, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save confirmed stages: {e}")
    
    def get_pip_size(self, symbol: str) -> float:
        """Get pip size"""
        symbol_upper = symbol.upper()
        
        if "JPY" in symbol_upper and not any(x in symbol_upper for x in ['XAUJPY', 'XAGJPY']):
            return 0.01
        elif any(x in symbol_upper for x in ['XAU', 'GOLD', 'XAG', 'SILVER', 'OIL', 'WTI', 'BRENT']):
            return 0.01
        elif any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOT']):
            return 1.0
        elif any(x in symbol_upper for x in ['US30', 'NAS100', 'SPX500', 'DAX', 'FTSE', 'NIKKEI']):
            return 1.0
        
        return 0.0001
    
    def calculate_profit_ratio(self, position: Dict, bb_data: Dict) -> float:
        """Calculate profit ratio"""
        try:
            symbol = position['symbol']
            pip_size = self.get_pip_size(symbol)
            current_price = position['current_price']
            entry_price = position['entry_price']
            
            # Profit in pips
            if position['type'] == 'BUY':
                profit_pips = (current_price - entry_price) / pip_size
            else:
                profit_pips = (entry_price - current_price) / pip_size
            
            # BB width in pips
            bb_width_pips = bb_data['bb_width'] / pip_size
            
            if bb_width_pips <= 0:
                return 0.0
            
            return profit_pips / bb_width_pips
            
        except Exception as e:
            logger.error(f"Error calculating profit ratio: {e}")
            return 0.0
    
    def determine_stage(self, profit_ratio: float, position_id: str) -> Tuple[str, str]:
        """Determine stage with hysteresis"""
        previous_stage = self.confirmed_stages.get(position_id, 'STAGE_0')
        
        # Find current stage based on profit ratio
        current_stage = 'STAGE_0'
        for stage_name, threshold in self.stage_thresholds.items():
            if profit_ratio >= threshold:
                current_stage = stage_name
            else:
                break
        
        # Apply hysteresis for stage changes
        if current_stage != previous_stage:
            # Check if we should actually change
            if current_stage > previous_stage:  # Moving up
                threshold = self.stage_thresholds[current_stage]
                if profit_ratio >= threshold - self.stage_hysteresis['up_buffer']:
                    new_stage = current_stage
                else:
                    new_stage = previous_stage
            else:  # Moving down
                threshold = self.stage_thresholds[previous_stage]
                if profit_ratio <= threshold - self.stage_hysteresis['down_buffer']:
                    new_stage = current_stage
                else:
                    new_stage = previous_stage
        else:
            new_stage = previous_stage
        
        self.confirmed_stages[position_id] = new_stage
        return new_stage, previous_stage
    
    def ensure_safe_distance(self, new_sl: float, current_price: float, 
                            bb_width: float, position_type: str, 
                            symbol: str, bb_width_pips: float) -> Tuple[float, Optional[Dict]]:
        """Ensure SL is a safe distance from current price"""
        pip_size = self.get_pip_size(symbol)
        
        # Calculate dynamic safe distance
        safe_distance_pips = max(
            self.safe_distance_config['min_pips'],
            bb_width_pips * self.safe_distance_config['bb_percentage']
        )
        
        safe_distance = safe_distance_pips * pip_size
        
        if position_type == 'BUY':
            min_allowed_sl = current_price - safe_distance
            if new_sl > min_allowed_sl:
                adjustment_pips = (new_sl - min_allowed_sl) / pip_size
                new_sl = min_allowed_sl
                return round(new_sl, 7), {
                    'reason': f'SL too close to price. Added {adjustment_pips:.1f} pips buffer.',
                    'adjustment_pips': round(adjustment_pips, 1)
                }
        else:  # SELL
            max_allowed_sl = current_price + safe_distance
            if new_sl < max_allowed_sl:
                adjustment_pips = (max_allowed_sl - new_sl) / pip_size
                new_sl = max_allowed_sl
                return round(new_sl, 7), {
                    'reason': f'SL too close to price. Added {adjustment_pips:.1f} pips buffer.',
                    'adjustment_pips': round(adjustment_pips, 1)
                }
        
        return round(new_sl, 7), None
    
    def calculate_stage_sl(self, position: Dict, stage: str, 
                          bb_data: Dict, profit_pips: float) -> float:
        """Calculate SL based on stage"""
        symbol = position['symbol']
        entry_price = position['entry_price']
        current_price = position['current_price']
        position_type = position['type'].lower()  # 'buy' or 'sell'
        pip_size = self.get_pip_size(symbol)
        bb_width = bb_data['bb_width']
        middle_bb = bb_data['middle_band']
        
        # Get stage definition
        stage_def = self.stage_definitions[stage][position_type]
        formula = stage_def['sl_formula']
        
        # Calculate based on formula
        if stage in ['STAGE_0']:
            if position_type == 'buy':
                sl = entry_price - (30 * pip_size)
            else:
                sl = entry_price + (30 * pip_size)
        
        elif stage in ['STAGE_1', 'STAGE_1A']:
            protection = stage_def['protection_percent']
            if position_type == 'buy':
                sl = entry_price + (protection * profit_pips * pip_size)
            else:
                sl = entry_price - (protection * profit_pips * pip_size)
        
        elif stage in ['STAGE_2A', 'STAGE_2B']:
            protection = stage_def['protection_percent']
            bb_buffer = stage_def['bb_buffer']
            
            option_a = entry_price + (protection * profit_pips * pip_size) if position_type == 'buy' else entry_price - (protection * profit_pips * pip_size)
            option_b = middle_bb + (bb_buffer * bb_width)
            
            if position_type == 'buy':
                sl = max(option_a, option_b)
            else:
                sl = min(option_a, option_b)
        
        elif stage in ['STAGE_2C', 'STAGE_3A']:
            protection = stage_def['protection_percent']
            trailing = stage_def['trailing_percent']
            
            option_a = entry_price + (protection * profit_pips * pip_size) if position_type == 'buy' else entry_price - (protection * profit_pips * pip_size)
            option_b = current_price - (trailing * bb_width) if position_type == 'buy' else current_price + (trailing * bb_width)
            
            if position_type == 'buy':
                sl = max(option_a, option_b)
            else:
                sl = min(option_a, option_b)
        
        elif stage in ['STAGE_3B', 'STAGE_4', 'STAGE_5']:
            trailing = stage_def['trailing_percent']
            if position_type == 'buy':
                sl = current_price - (trailing * bb_width)
            else:
                sl = current_price + (trailing * bb_width)
        
        else:
            # Fallback
            if position_type == 'buy':
                sl = entry_price - (30 * pip_size)
            else:
                sl = entry_price + (30 * pip_size)
        
        return round(sl, 7)
    
    def calculate_stage_tp(self, position: Dict, stage: str, bb_data: Dict) -> Optional[float]:
        """Calculate TP based on stage"""
        symbol = position['symbol']
        current_price = position['current_price']
        position_type = position['type'].lower()
        pip_size = self.get_pip_size(symbol)
        bb_width = bb_data['bb_width']
        
        # Get stage definition
        stage_def = self.stage_definitions[stage][position_type]
        
        # Stages 2C and above: TP removed
        if stage in ['STAGE_2C', 'STAGE_3A', 'STAGE_3B', 'STAGE_4', 'STAGE_5']:
            return 0.0
        
        elif stage in ['STAGE_0']:
            if position_type == 'buy':
                tp = position['entry_price'] + (40 * pip_size)
            else:
                tp = position['entry_price'] - (40 * pip_size)
        
        elif stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B']:
            if position_type == 'buy':
                tp = bb_data['upper_band']
                # Ensure TP is above current price
                if tp <= current_price:
                    tp = current_price + (0.05 * bb_width)
            else:
                tp = bb_data['lower_band']
                # Ensure TP is below current price
                if tp >= current_price:
                    tp = current_price - (0.05 * bb_width)
        
        else:
            return None
        
        return round(tp, 7)
    
    def load_market_data(self) -> bool:
        """Load market data"""
        try:
            if not os.path.exists(self.market_data_file):
                logger.error(f"Market data file not found: {self.market_data_file}")
                return False
            
            with open(self.market_data_file, 'r') as f:
                data = json.load(f)
            
            self.market_data = {}
            for item in data.get('data', []):
                symbol = item['pair']
                self.market_data[symbol] = {
                    'lower_band': round(item['lower_band'], 7),
                    'middle_band': round(item['middle_band'], 7),
                    'upper_band': round(item['upper_band'], 7),
                    'bb_width': round(item['upper_band'] - item['lower_band'], 7)
                }
            
            logger.info(f"Loaded market data for {len(self.market_data)} symbols")
            return True
            
        except Exception as e:
            logger.error(f"Error loading market data: {e}")
            return False
    
    def create_position_log(self, position: Dict, stage: str, previous_stage: str,
                           profit_ratio: float, profit_pips: float,
                           bb_data: Dict, new_sl: Optional[float], new_tp: Optional[float],
                           safe_adjustment: Optional[Dict]) -> Dict:
        """Create a minimal position log entry with verification"""
        
        symbol = position['symbol']
        pip_size = self.get_pip_size(symbol)
        position_type = position['type'].lower()
        stage_def = self.stage_definitions[stage][position_type]
        
        # Helper for rounding
        def round7(val):
            return round(float(val), 7) if val is not None else 0.0
        
        def round4(val):
            return round(float(val), 4) if val is not None else 0.0
        
        # Calculate verification strings
        sl_verification = ""
        tp_verification = ""
        
        if new_sl is not None:
            # Create human-readable verification
            entry = position['entry_price']
            current = position['current_price']
            
            if stage == 'STAGE_0':
                if position['type'] == 'BUY':
                    sl_verification = f"{entry:.5f} - (30 × {pip_size}) = {new_sl:.5f}"
                else:
                    sl_verification = f"{entry:.5f} + (30 × {pip_size}) = {new_sl:.5f}"
            elif stage in ['STAGE_1', 'STAGE_1A']:
                protection = stage_def['protection_percent']
                if position['type'] == 'BUY':
                    sl_verification = f"{entry:.5f} + ({protection} × {profit_pips:.1f} × {pip_size}) = {new_sl:.5f}"
                else:
                    sl_verification = f"{entry:.5f} - ({protection} × {profit_pips:.1f} × {pip_size}) = {new_sl:.5f}"
        
        if new_tp is not None and new_tp != 0.0:
            if stage == 'STAGE_0':
                if position['type'] == 'BUY':
                    tp_verification = f"{position['entry_price']:.5f} + (40 × {pip_size}) = {new_tp:.5f}"
                else:
                    tp_verification = f"{position['entry_price']:.5f} - (40 × {pip_size}) = {new_tp:.5f}"
            elif stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B']:
                if position['type'] == 'BUY':
                    tp_verification = f"Upper BB = {new_tp:.5f}"
                else:
                    tp_verification = f"Lower BB = {new_tp:.5f}"
        
        # Create minimal log entry
        log_entry = {
            'ticket': position['ticket'],
            'symbol': symbol,
            'type': position['type'],
            'stage': stage,
            'stage_changed': stage != previous_stage,
            'previous_stage': previous_stage if stage != previous_stage else None,
            
            # Values needed for verification
            'values': {
                'entry': round7(position['entry_price']),
                'current': round7(position['current_price']),
                'pip_size': pip_size,
                'profit_pips': round4(profit_pips),
                'profit_ratio': round4(profit_ratio),
                'bb_width_pips': round4(bb_data['bb_width'] / pip_size),
                'stage_threshold': round4(stage_def.get('profit_threshold', 0)),
                
                'sl_before': round7(position['sl']),
                'tp_before': round7(position['tp']),
                'sl_after': round7(new_sl) if new_sl is not None else round7(position['sl']),
                'tp_after': round7(new_tp) if new_tp is not None else round7(position['tp'])
            },
            
            # Verification (key for backtracking)
            'verification': {
                'sl_formula': stage_def['sl_formula'],
                'sl_calculation': sl_verification if sl_verification else "No change",
                'tp_formula': stage_def['tp_formula'],
                'tp_calculation': tp_verification if tp_verification else "No change",
                'stage_reason': f"{profit_ratio:.4f} {'<' if profit_ratio < stage_def.get('profit_threshold', 0) else '>='} {stage_def.get('profit_threshold', 0):.4f}"
            }
        }
        
        # Add safety adjustment if any
        if safe_adjustment:
            log_entry['safety_adjustment'] = safe_adjustment
        
        return log_entry
    
    def calculate_new_sl_tp(self, position: Dict) -> Tuple[Optional[float], Optional[float], str, str, Dict]:
        """Calculate new SL/TP"""
        symbol = position['symbol']
        
        if symbol not in self.market_data:
            return None, None, 'NO_DATA', 'NO_DATA', {}
        
        bb_data = self.market_data[symbol]
        
        # Calculate profit and stage
        profit_ratio = self.calculate_profit_ratio(position, bb_data)
        
        # Generate position ID
        position_id = f"{position['ticket']}_{symbol}"
        
        # Determine stage
        stage, previous_stage = self.determine_stage(profit_ratio, position_id)
        
        # Calculate profit in pips
        pip_size = self.get_pip_size(symbol)
        if position['type'] == 'BUY':
            profit_pips = (position['current_price'] - position['entry_price']) / pip_size
        else:
            profit_pips = (position['entry_price'] - position['current_price']) / pip_size
        
        # Calculate SL
        new_sl = self.calculate_stage_sl(position, stage, bb_data, profit_pips)
        
        # Apply safe distance
        bb_width_pips = bb_data['bb_width'] / pip_size
        new_sl, safe_adjustment = self.ensure_safe_distance(
            new_sl, position['current_price'], bb_data['bb_width'],
            position['type'], symbol, bb_width_pips
        )
        
        # Calculate TP
        new_tp = self.calculate_stage_tp(position, stage, bb_data)
        
        # Check if changes are needed
        current_sl = position['sl'] if abs(position['sl']) > 0.00001 else 0.0
        current_tp = position['tp'] if abs(position['tp']) > 0.00001 else 0.0
        
        sl_changed = abs(new_sl - current_sl) > 0.00001 if new_sl is not None else False
        tp_changed = abs(new_tp - current_tp) > 0.00001 if new_tp is not None else False
        
        # Only return changes if needed
        final_sl = new_sl if sl_changed else None
        final_tp = new_tp if tp_changed else None
        
        # Create log entry
        log_entry = self.create_position_log(
            position, stage, previous_stage,
            profit_ratio, profit_pips,
            bb_data, final_sl, final_tp,
            safe_adjustment
        )
        
        return final_sl, final_tp, stage, previous_stage, log_entry
    
    def process_positions(self, positions: List[Dict]) -> List[Dict]:
        """Process all positions"""
        updates_needed = []
        
        if not self.market_data:
            logger.error("No market data loaded")
            return updates_needed
        
        for position in positions:
            symbol = position['symbol']
            
            if symbol not in self.market_data:
                continue
            
            new_sl, new_tp, stage, previous_stage, log_entry = self.calculate_new_sl_tp(position)
            
            # Add to updates if anything changed
            if new_sl is not None or new_tp is not None:
                update_info = {
                    'ticket': position['ticket'],
                    'symbol': symbol,
                    'type': position['type'],
                    'stage': stage,
                    'previous_stage': previous_stage,
                    'current_sl': position['sl'],
                    'current_tp': position['tp'],
                    'new_sl': new_sl,
                    'new_tp': new_tp,
                    'log_entry': log_entry
                }
                
                updates_needed.append(update_info)
        
        return updates_needed
    
    def get_stage_definitions(self) -> Dict:
        """Get stage definitions for logging"""
        # Return a simplified version for logging
        simplified_defs = {}
        for stage, directions in self.stage_definitions.items():
            simplified_defs[stage] = {}
            for direction, defs in directions.items():
                simplified_defs[stage][direction] = {
                    'sl_formula': defs['sl_formula'],
                    'tp_formula': defs['tp_formula'],
                    'profit_threshold': defs.get('profit_threshold', 0),
                    'description': defs.get('description', '')
                }
        return simplified_defs