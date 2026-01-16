import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SLTPEngine:
    """Enhanced SL/TP engine with entry-agnostic stage-based protection"""
    
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
        
        # Enhanced 10-stage thresholds (Entry-Agnostic)
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
        
        # Stage definitions (BUY and SELL versions) - ENTRY-AGNOSTIC
        self.stage_definitions = self._create_stage_definitions()
        
        # Load confirmed stages
        self.confirmed_stages = self.load_confirmed_stages()
        self.stage_entry_times = {}
    
    def _create_stage_definitions(self) -> Dict:
        """Create entry-agnostic stage definitions"""
        return {
            'STAGE_0': {
                'buy': {
                    'sl_formula': 'entry - (30 × pip_size)',
                    'tp_formula': 'entry + (40 × pip_size)',
                    'profit_threshold': 0.25,
                    'protection_percent': 0.0,  # Static stop
                    'description': 'Initial position: profit < 25% of BB width'
                },
                'sell': {
                    'sl_formula': 'entry + (30 × pip_size)',
                    'tp_formula': 'entry - (40 × pip_size)',
                    'profit_threshold': 0.25,
                    'protection_percent': 0.0,  # Static stop
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
                    'sl_formula': 'entry + (0.65 × profit_pips × pip_size)',
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.60,
                    'protection_percent': 0.65,
                    'description': '50-59% profit: protect 65% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.65 × profit_pips × pip_size)',
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.60,
                    'protection_percent': 0.65,
                    'description': '50-59% profit: protect 65% of gains'
                }
            },
            'STAGE_2B': {
                'buy': {
                    'sl_formula': 'entry + (0.75 × profit_pips × pip_size)',
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.70,
                    'protection_percent': 0.75,
                    'description': '60-69% profit: protect 75% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.75 × profit_pips × pip_size)',
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.70,
                    'protection_percent': 0.75,
                    'description': '60-69% profit: protect 75% of gains'
                }
            },
            'STAGE_2C': {
                'buy': {
                    'sl_formula': 'entry + (0.80 × profit_pips × pip_size)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.80,
                    'protection_percent': 0.80,
                    'description': '70-79% profit: protect 80% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.80 × profit_pips × pip_size)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.80,
                    'protection_percent': 0.80,
                    'description': '70-79% profit: protect 80% of gains'
                }
            },
            'STAGE_3A': {
                'buy': {
                    'sl_formula': 'entry + (0.85 × profit_pips × pip_size)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.90,
                    'protection_percent': 0.85,
                    'description': '80-89% profit: protect 85% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.85 × profit_pips × pip_size)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.90,
                    'protection_percent': 0.85,
                    'description': '80-89% profit: protect 85% of gains'
                }
            },
            'STAGE_3B': {
                'buy': {
                    'sl_formula': 'current_price - (0.03 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.20,
                    'trailing_percent': 0.03,
                    'description': '90-119% profit: 3% trailing stop from price'
                },
                'sell': {
                    'sl_formula': 'current_price + (0.03 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.20,
                    'trailing_percent': 0.03,
                    'description': '90-119% profit: 3% trailing stop from price'
                }
            },
            'STAGE_4': {
                'buy': {
                    'sl_formula': 'current_price - (0.02 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.80,
                    'trailing_percent': 0.02,
                    'description': '120-179% profit: 2% trailing stop from price'
                },
                'sell': {
                    'sl_formula': 'current_price + (0.02 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 1.80,
                    'trailing_percent': 0.02,
                    'description': '120-179% profit: 2% trailing stop from price'
                }
            },
            'STAGE_5': {
                'buy': {
                    'sl_formula': 'current_price - (0.015 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': float('inf'),
                    'trailing_percent': 0.015,
                    'description': '180%+ profit: 1.5% ultra-tight trailing from price'
                },
                'sell': {
                    'sl_formula': 'current_price + (0.015 × bb_width)',
                    'tp_formula': 'REMOVED',
                    'profit_threshold': float('inf'),
                    'trailing_percent': 0.015,
                    'description': '180%+ profit: 1.5% ultra-tight trailing from price'
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
        """Calculate profit ratio (entry-agnostic)"""
        try:
            symbol = position['symbol']
            pip_size = self.get_pip_size(symbol)
            current_price = position['current_price']
            entry_price = position['entry_price']
            
            # Profit in pips (absolute value)
            profit_pips = abs(current_price - entry_price) / pip_size
            
            # BB width in pips
            bb_width_pips = bb_data['bb_width'] / pip_size
            
            if bb_width_pips <= 0:
                return 0.0
            
            return profit_pips / bb_width_pips
            
        except Exception as e:
            logger.error(f"Error calculating profit ratio: {e}")
            return 0.0
    
    def determine_stage(self, profit_ratio: float, position_id: str) -> Tuple[str, str]:
        """Determine stage with hysteresis and one-way transition"""
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
            # One-way transition: Once in trailing stages (3B+), cannot go back to profit-locking
            if previous_stage in ['STAGE_3B', 'STAGE_4', 'STAGE_5'] and current_stage < previous_stage:
                # Stay in trailing stage (one-way transition)
                new_stage = previous_stage
                logger.debug(f"One-way transition enforced: staying in {previous_stage}")
            elif current_stage > previous_stage:  # Moving up
                threshold = self.stage_thresholds[current_stage]
                if profit_ratio >= threshold - self.stage_hysteresis['up_buffer']:
                    new_stage = current_stage
                else:
                    new_stage = previous_stage
            else:  # Moving down (only possible before trailing stages)
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
                            symbol: str, bb_width_pips: float, 
                            stage: str, position: Dict) -> Tuple[float, Optional[Dict]]:
        """Enhanced safe distance with profit preservation"""
        pip_size = self.get_pip_size(symbol)
        current_sl = position.get('sl', 0.0)
        
        # Calculate stage-specific safe distance
        stage_min_pips = self.safe_distance_config['stage_specific_mins'].get(stage, 10)
        
        safe_distance_pips = max(
            self.safe_distance_config['min_pips'],
            bb_width_pips * self.safe_distance_config['bb_percentage'],
            stage_min_pips,
            bb_width_pips * 0.05  # Minimum 5% of BB width
        )
        
        safe_distance = safe_distance_pips * pip_size
        
        if position_type == 'BUY':
            # For BUY: SL must be at least safe_distance BELOW current price
            max_allowed_sl = current_price - safe_distance  # This is the highest SL we can have safely
            
            # Check if calculated SL is too high (too close to current price)
            if new_sl > max_allowed_sl:
                # SL needs to be lowered for safety
                adjustment_pips = (new_sl - max_allowed_sl) / pip_size
                
                # Calculate how much profit we'd give back by moving SL up to max_allowed_sl
                # Note: For BUY, moving SL UP gives back profit
                # Only calculate giveback if we have an existing SL
                if abs(current_sl) > 0.00001:  # Has existing SL
                    profit_giveback_pips = (max_allowed_sl - current_sl) / pip_size
                    current_profit_pips = (current_price - position['entry_price']) / pip_size
                    max_allowed_giveback = current_profit_pips * self.safe_distance_config.get('max_profit_giveback', 0.10)
                    
                    if profit_giveback_pips > max_allowed_giveback:
                        # Too much profit would be given back
                        logger.info(f"Safety adjustment rejected for {symbol}: would give back {profit_giveback_pips:.1f} pips (>10% of profit)")
                        return current_sl, {
                            'reason': f'Safety adjustment rejected: would give back {profit_giveback_pips:.1f} pips profit',
                            'adjustment_pips': 0.0,
                            'decision': 'keep_current_sl'
                        }
                
                # Safe to adjust SL down to safe distance
                # ALWAYS apply safe distance when current_sl is 0.0 (no SL set)
                new_sl = max_allowed_sl
                decision_reason = 'adjusted_for_safe_distance'
                if abs(current_sl) < 0.00001:
                    decision_reason = 'initial_sl_with_safe_distance'
                
                return round(new_sl, 7), {
                    'reason': f'SL adjusted for safe distance: {adjustment_pips:.1f} pips buffer added',
                    'adjustment_pips': round(adjustment_pips, 1),
                    'decision': decision_reason
                }
        
        else:  # SELL
            # For SELL: SL must be at least safe_distance ABOVE current price  
            min_allowed_sl = current_price + safe_distance  # This is the lowest SL we can have safely
            
            # Check if calculated SL is too low (too close to current price)
            if new_sl < min_allowed_sl:
                # SL needs to be raised for safety
                adjustment_pips = (min_allowed_sl - new_sl) / pip_size
                
                # Calculate how much profit we'd give back by moving SL down to min_allowed_sl
                # Note: For SELL, moving SL DOWN gives back profit
                # Only calculate giveback if we have an existing SL
                if abs(current_sl) > 0.00001:  # Has existing SL
                    profit_giveback_pips = (current_sl - min_allowed_sl) / pip_size
                    current_profit_pips = (position['entry_price'] - current_price) / pip_size
                    max_allowed_giveback = current_profit_pips * self.safe_distance_config.get('max_profit_giveback', 0.10)
                    
                    if profit_giveback_pips > max_allowed_giveback:
                        # Too much profit would be given back
                        logger.info(f"Safety adjustment rejected for {symbol}: would give back {profit_giveback_pips:.1f} pips (>10% of profit)")
                        return current_sl, {
                            'reason': f'Safety adjustment rejected: would give back {profit_giveback_pips:.1f} pips profit',
                            'adjustment_pips': 0.0,
                            'decision': 'keep_current_sl'
                        }
                
                # Safe to adjust SL up to safe distance
                # ALWAYS apply safe distance when current_sl is 0.0 (no SL set)
                new_sl = min_allowed_sl
                decision_reason = 'adjusted_for_safe_distance'
                if abs(current_sl) < 0.00001:
                    decision_reason = 'initial_sl_with_safe_distance'
                
                return round(new_sl, 7), {
                    'reason': f'SL adjusted for safe distance: {adjustment_pips:.1f} pips buffer added',
                    'adjustment_pips': round(adjustment_pips, 1),
                    'decision': decision_reason
                }
        
        # If no adjustment needed
        return round(new_sl, 7), None


    def calculate_stage_sl(self, position: Dict, stage: str, 
                          bb_data: Dict, profit_pips: float) -> float:
        """Calculate SL based on stage (entry-agnostic)"""
        symbol = position['symbol']
        entry_price = position['entry_price']
        current_price = position['current_price']
        position_type = position['type'].lower()
        pip_size = self.get_pip_size(symbol)
        bb_width = bb_data['bb_width']
        
        # Get stage definition
        stage_def = self.stage_definitions[stage][position_type]
        
        try:
            # Calculate SL based on formula type
            if stage == 'STAGE_0':
                if position_type == 'buy':
                    sl = entry_price - (30 * pip_size)
                else:
                    sl = entry_price + (30 * pip_size)
            
            elif stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A']:
                # Profit-locking stages
                protection = stage_def['protection_percent']
                if position_type == 'buy':
                    sl = entry_price + (protection * profit_pips * pip_size)
                else:
                    sl = entry_price - (protection * profit_pips * pip_size)
            
            elif stage in ['STAGE_3B', 'STAGE_4', 'STAGE_5']:
                # Price-trailing stages
                trailing = stage_def['trailing_percent']
                if position_type == 'buy':
                    sl = current_price - (trailing * bb_width)
                else:
                    sl = current_price + (trailing * bb_width)
            
            else:
                # Fallback to stage 0
                if position_type == 'buy':
                    sl = entry_price - (30 * pip_size)
                else:
                    sl = entry_price + (30 * pip_size)
            
            return round(sl, 7)
            
        except Exception as e:
            logger.error(f"Error calculating SL for stage {stage}: {e}")
            # Fallback to static stop
            if position_type == 'buy':
                return round(entry_price - (30 * pip_size), 7)
            else:
                return round(entry_price + (30 * pip_size), 7)
    
    def calculate_stage_tp(self, position: Dict, stage: str, bb_data: Dict) -> Optional[float]:
        """Calculate TP based on stage"""
        symbol = position['symbol']
        current_price = position['current_price']
        position_type = position['type'].lower()
        pip_size = self.get_pip_size(symbol)
        bb_width = bb_data['bb_width']
        
        # Stages 2C and above: TP removed (let winners run)
        if stage in ['STAGE_2C', 'STAGE_3A', 'STAGE_3B', 'STAGE_4', 'STAGE_5']:
            return 0.0
        
        elif stage == 'STAGE_0':
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
        """Create a position log entry with verification"""
        
        symbol = position['symbol']
        pip_size = self.get_pip_size(symbol)
        position_type = position['type'].lower()
        stage_def = self.stage_definitions[stage][position_type]
        
        # Helper for rounding
        def round7(val):
            return round(float(val), 7) if val is not None else 0.0
        
        def round4(val):
            return round(float(val), 4) if val is not None else 0.0
        
        # Create human-readable verification
        sl_verification = ""
        tp_verification = ""
        
        entry = position['entry_price']
        current = position['current_price']
        
        if stage == 'STAGE_0':
            if position['type'] == 'BUY':
                sl_verification = f"{entry:.5f} - (30 × {pip_size}) = {new_sl:.5f}" if new_sl else "No change"
            else:
                sl_verification = f"{entry:.5f} + (30 × {pip_size}) = {new_sl:.5f}" if new_sl else "No change"
        
        elif stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A']:
            protection = stage_def['protection_percent']
            if position['type'] == 'BUY':
                sl_verification = f"{entry:.5f} + ({protection} × {profit_pips:.1f} × {pip_size}) = {new_sl:.5f}" if new_sl else "No change"
            else:
                sl_verification = f"{entry:.5f} - ({protection} × {profit_pips:.1f} × {pip_size}) = {new_sl:.5f}" if new_sl else "No change"
        
        elif stage in ['STAGE_3B', 'STAGE_4', 'STAGE_5']:
            trailing = stage_def.get('trailing_percent', 0.03)
            if position['type'] == 'BUY':
                sl_verification = f"{current:.5f} - ({trailing} × {bb_data['bb_width']:.5f}) = {new_sl:.5f}" if new_sl else "No change"
            else:
                sl_verification = f"{current:.5f} + ({trailing} × {bb_data['bb_width']:.5f}) = {new_sl:.5f}" if new_sl else "No change"
        
        if new_tp is not None and new_tp != 0.0:
            if stage == 'STAGE_0':
                if position['type'] == 'BUY':
                    tp_verification = f"{entry:.5f} + (40 × {pip_size}) = {new_tp:.5f}"
                else:
                    tp_verification = f"{entry:.5f} - (40 × {pip_size}) = {new_tp:.5f}"
            elif stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B']:
                if position['type'] == 'BUY':
                    tp_verification = f"Upper BB = {new_tp:.5f}"
                else:
                    tp_verification = f"Lower BB = {new_tp:.5f}"
            elif stage in ['STAGE_2C', 'STAGE_3A', 'STAGE_3B', 'STAGE_4', 'STAGE_5']:
                tp_verification = "TP Removed (0.0)"
        
        # Create log entry
        log_entry = {
            'ticket': position['ticket'],
            'symbol': symbol,
            'type': position['type'],
            'stage': stage,
            'stage_changed': stage != previous_stage,
            'previous_stage': previous_stage if stage != previous_stage else None,
            'protection_phase': 'profit-locking' if stage in ['STAGE_0', 'STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A'] else 'price-trailing',
            
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
            
            # Verification
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
        """Calculate new SL/TP with entry-agnostic protection"""
        symbol = position['symbol']
        
        if symbol not in self.market_data:
            return None, None, 'NO_DATA', 'NO_DATA', {}
        
        bb_data = self.market_data[symbol]
        
        # Calculate profit ratio (entry-agnostic)
        profit_ratio = self.calculate_profit_ratio(position, bb_data)
        
        # Generate position ID
        position_id = f"{position['ticket']}_{symbol}"
        
        # Determine stage
        stage, previous_stage = self.determine_stage(profit_ratio, position_id)
        
        # Calculate profit in pips (absolute value)
        pip_size = self.get_pip_size(symbol)
        profit_pips = abs(position['current_price'] - position['entry_price']) / pip_size
        
        # Calculate SL
        new_sl = self.calculate_stage_sl(position, stage, bb_data, profit_pips)
        
        # Apply enhanced safe distance with profit preservation
        bb_width_pips = bb_data['bb_width'] / pip_size
        new_sl, safe_adjustment = self.ensure_safe_distance(
            new_sl, position['current_price'], bb_data['bb_width'],
            position['type'], symbol, bb_width_pips, stage, position
        )
        
        # Calculate TP
        new_tp = self.calculate_stage_tp(position, stage, bb_data)
        
        # Check if changes are needed
        current_sl = position['sl'] if abs(position['sl']) > 0.00001 else 0.0
        current_tp = position['tp'] if abs(position['tp']) > 0.00001 else 0.0
        
        # Always set SL if current SL is 0.0 and we have a valid calculated SL
        if abs(current_sl) < 0.00001 and new_sl is not None:
            sl_changed = True
        else:
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
        """Process all positions with entry-agnostic protection"""
        updates_needed = []
        
        if not self.market_data:
            logger.error("No market data loaded")
            return updates_needed
        
        for position in positions:
            symbol = position['symbol']
            
            if symbol not in self.market_data:
                logger.warning(f"No market data for {symbol}")
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
                    'protection_phase': log_entry['protection_phase'],
                    'current_sl': position['sl'],
                    'current_tp': position['tp'],
                    'new_sl': new_sl,
                    'new_tp': new_tp,
                    'log_entry': log_entry
                }
                
                updates_needed.append(update_info)
        
        # Save confirmed stages after processing
        self.save_confirmed_stages()
        
        return updates_needed
    
    def get_stage_definitions(self) -> Dict:
        """Get stage definitions for logging"""
        simplified_defs = {}
        for stage, directions in self.stage_definitions.items():
            simplified_defs[stage] = {}
            for direction, defs in directions.items():
                simplified_defs[stage][direction] = {
                    'sl_formula': defs['sl_formula'],
                    'tp_formula': defs['tp_formula'],
                    'profit_threshold': defs.get('profit_threshold', 0),
                    'protection_percent': defs.get('protection_percent', 0),
                    'trailing_percent': defs.get('trailing_percent', 0),
                    'description': defs.get('description', ''),
                    'protection_phase': 'profit-locking' if stage in ['STAGE_0', 'STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A'] else 'price-trailing'
                }
        return simplified_defs
    
    def get_stage_statistics(self, positions: List[Dict]) -> Dict:
        """Get statistics about current stage distribution"""
        stats = {
            'total_positions': len(positions),
            'stage_distribution': {},
            'phase_distribution': {
                'profit_locking': 0,
                'price_trailing': 0
            }
        }
        
        profit_locking_stages = ['STAGE_0', 'STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A']
        
        for position in positions:
            symbol = position['symbol']
            position_id = f"{position['ticket']}_{symbol}"
            
            if symbol in self.market_data and position_id in self.confirmed_stages:
                stage = self.confirmed_stages[position_id]
                stats['stage_distribution'][stage] = stats['stage_distribution'].get(stage, 0) + 1
                
                if stage in profit_locking_stages:
                    stats['phase_distribution']['profit_locking'] += 1
                else:
                    stats['phase_distribution']['price_trailing'] += 1
        
        return stats