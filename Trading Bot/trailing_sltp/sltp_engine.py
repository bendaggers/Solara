# SLTP_Engine.py

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SLTPEngine:
    """Enhanced SL/TP engine with entry-agnostic stage-based protection - Survivor's Edition"""
    
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
            'STAGE_0': 0.00,    # STAGE_0: 0% to 25%
            'STAGE_1': 0.25,    # STAGE_1: 25% to 40%
            'STAGE_1A': 0.40,   # STAGE_1A: 40% to 50%
            'STAGE_2A': 0.50,   # STAGE_2A: 50% to 60%
            'STAGE_2B': 0.60,   # STAGE_2B: 60% to 70%
            'STAGE_2C': 0.70,   # STAGE_2C: 70% to 80%
            'STAGE_3A': 0.80,   # STAGE_3A: 80% to 90%
            'STAGE_3B': 0.90,   # STAGE_3B: 90% to 120%
            'STAGE_4': 1.20,    # STAGE_4: 120% to 180%
            'STAGE_5': 1.80     # STAGE_5: 180% and above
        }
        
        # Stage definitions (BUY and SELL versions) - SURVIVOR'S EDITION
        self.stage_definitions = self._create_stage_definitions()
        
        # Load confirmed stages
        self.confirmed_stages = self.load_confirmed_stages()
        self.stage_entry_times = {}
    
    def _create_stage_definitions(self) -> Dict:
        """Create entry-agnostic stage definitions - SURVIVOR'S EDITION"""
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
                    'sl_formula': 'entry + (0.25 × profit_pips × pip_size)',  # 25% protection
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.40,
                    'protection_percent': 0.25,  # CHANGED: 25% protection
                    'description': '25-39% profit: protect 25% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.25 × profit_pips × pip_size)',  # 25% protection
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.40,
                    'protection_percent': 0.25,  # CHANGED: 25% protection
                    'description': '25-39% profit: protect 25% of gains'
                }
            },
            'STAGE_1A': {
                'buy': {
                    'sl_formula': 'entry + (0.40 × profit_pips × pip_size)',  # 40% protection
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.50,
                    'protection_percent': 0.40,  # CHANGED: 40% protection
                    'description': '40-49% profit: protect 40% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.40 × profit_pips × pip_size)',  # 40% protection
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.50,
                    'protection_percent': 0.40,  # CHANGED: 40% protection
                    'description': '40-49% profit: protect 40% of gains'
                }
            },
            'STAGE_2A': {
                'buy': {
                    'sl_formula': 'entry + (0.50 × profit_pips × pip_size)',  # 50% protection
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.60,
                    'protection_percent': 0.50,  # CHANGED: 50% protection
                    'description': '50-59% profit: protect 50% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.50 × profit_pips × pip_size)',  # 50% protection
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.60,
                    'protection_percent': 0.50,  # CHANGED: 50% protection
                    'description': '50-59% profit: protect 50% of gains'
                }
            },
            'STAGE_2B': {
                'buy': {
                    'sl_formula': 'entry + (0.60 × profit_pips × pip_size)',  # 60% protection
                    'tp_formula': 'upper_bollinger_band',
                    'profit_threshold': 0.70,
                    'protection_percent': 0.60,  # CHANGED: 60% protection
                    'description': '60-69% profit: protect 60% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.60 × profit_pips × pip_size)',  # 60% protection
                    'tp_formula': 'lower_bollinger_band',
                    'profit_threshold': 0.70,
                    'protection_percent': 0.60,  # CHANGED: 60% protection
                    'description': '60-69% profit: protect 60% of gains'
                }
            },
            'STAGE_2C': {
                'buy': {
                    'sl_formula': 'entry + (0.70 × profit_pips × pip_size)',  # 70% protection
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.80,
                    'protection_percent': 0.70,  # CHANGED: 70% protection
                    'description': '70-79% profit: protect 70% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.70 × profit_pips × pip_size)',  # 70% protection
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.80,
                    'protection_percent': 0.70,  # CHANGED: 70% protection
                    'description': '70-79% profit: protect 70% of gains'
                }
            },
            'STAGE_3A': {
                'buy': {
                    'sl_formula': 'entry + (0.75 × profit_pips × pip_size)',  # 75% protection
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.90,
                    'protection_percent': 0.75,  # CHANGED: 75% protection
                    'description': '80-89% profit: protect 75% of gains'
                },
                'sell': {
                    'sl_formula': 'entry - (0.75 × profit_pips × pip_size)',  # 75% protection
                    'tp_formula': 'REMOVED',
                    'profit_threshold': 0.90,
                    'protection_percent': 0.75,  # CHANGED: 75% protection
                    'description': '80-89% profit: protect 75% of gains'
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
        
        # Get sorted stage names and thresholds
        stage_items = list(self.stage_thresholds.items())
        
        # Check each stage
        for i, (stage_name, threshold) in enumerate(stage_items):
            is_last_stage = (i == len(stage_items) - 1)
            
            if is_last_stage:
                # Last stage (STAGE_5): always qualify if we get here
                current_stage = stage_name
                break
            
            next_threshold = stage_items[i + 1][1]
            
            if threshold <= profit_ratio < next_threshold:
                current_stage = stage_name
                break
            elif profit_ratio >= next_threshold:
                # Profit is higher than this stage's range, check next
                continue
            else:
                # Profit is below this stage's minimum
                break
        
        # Apply hysteresis for stage changes
        if current_stage != previous_stage:
            # One-way transition: Once in trailing stages (3B+), cannot go back to profit-locking
            if previous_stage in ['STAGE_3B', 'STAGE_4', 'STAGE_5'] and current_stage < previous_stage:
                # Stay in trailing stage (one-way transition)
                new_stage = previous_stage
                logger.debug(f"One-way transition enforced: staying in {previous_stage}")
            elif current_stage > previous_stage:  # Moving up
                # Get the minimum threshold for this stage
                move_up_threshold = self.stage_thresholds[current_stage]
                
                if profit_ratio >= move_up_threshold - self.stage_hysteresis['up_buffer']:
                    new_stage = current_stage
                else:
                    new_stage = previous_stage
            else:  # Moving down (only possible before trailing stages)
                # Get the threshold for the previous stage
                move_down_threshold = self.stage_thresholds[previous_stage]
                
                if profit_ratio <= move_down_threshold - self.stage_hysteresis['down_buffer']:
                    new_stage = current_stage
                else:
                    new_stage = previous_stage
        else:
            new_stage = previous_stage
        
        self.confirmed_stages[position_id] = new_stage
        return new_stage, previous_stage

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
                # Profit-locking stages - USING SURVIVOR'S PROTECTION PERCENTAGES
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
        
        # ... existing code ...
        
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
        
        # Apply SURVIVOR'S RULE: Check if new SL is worse than current SL
        current_sl = position['sl'] if abs(position['sl']) > 0.00001 else 0.0
        
        # Determine if new SL is worse
        is_worse_sl = False
        sl_comparison = ""
        
        if new_sl is not None and abs(current_sl) > 0.00001:
            if position['type'] == 'BUY':
                # For BUY: New SL is worse if it's LOWER than current SL
                if new_sl < current_sl:
                    is_worse_sl = True
                    sl_comparison = f"New SL {new_sl:.5f} < Current SL {current_sl:.5f} (worse protection)"
            else:  # SELL
                # For SELL: New SL is worse if it's HIGHER than current SL
                if new_sl > current_sl:
                    is_worse_sl = True
                    sl_comparison = f"New SL {new_sl:.5f} > Current SL {current_sl:.5f} (worse protection)"
        
        # If new SL is worse, keep current SL (don't modify)
        final_sl = None
        if is_worse_sl:
            final_sl = None  # Don't change SL
            sl_comparison_note = f"Skipping SL update: {sl_comparison}"
        else:
            final_sl = new_sl if new_sl is not None else None
            sl_comparison_note = "OK to update"
        
        # NO safe distance calculations - MT5Interface will handle brute-force adjustment
        safe_adjustment = None
        
        # Calculate TP
        new_tp = self.calculate_stage_tp(position, stage, bb_data)
        
        # Check if changes are needed
        current_tp = position['tp'] if abs(position['tp']) > 0.00001 else 0.0
        
        # Always set SL if current SL is 0.0 and we have a valid calculated SL
        if abs(current_sl) < 0.00001 and final_sl is not None:
            sl_changed = True
        else:
            sl_changed = final_sl is not None and abs(final_sl - current_sl) > 0.00001
        
        tp_changed = abs(new_tp - current_tp) > 0.00001 if new_tp is not None else False
        
        # Only return changes if needed
        final_sl_out = final_sl if sl_changed else None
        final_tp = new_tp if tp_changed else None
        
        # Create log entry - pass the sl comparison info
        log_entry = self.create_position_log(
            position, stage, previous_stage,
            profit_ratio, profit_pips,
            bb_data, final_sl_out, final_tp,
            safe_adjustment
        )
        
        # Add SL comparison info to log
        if is_worse_sl:
            log_entry['sl_comparison'] = {
                'decision': 'keep_current_sl',
                'reason': sl_comparison,
                'current_sl': round(current_sl, 7),
                'calculated_sl': round(new_sl, 7) if new_sl else None,
                'comparison_note': sl_comparison_note
            }
        
        return final_sl_out, final_tp, stage, previous_stage, log_entry


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
            
            # Check if we should skip due to worse SL
            skip_sl_update = 'sl_comparison' in log_entry and log_entry['sl_comparison']['decision'] == 'keep_current_sl'
            
            # Determine if updates are needed
            needs_update = False
            
            if not skip_sl_update:
                # Only update SL if not worse than current
                needs_update = (new_sl is not None) or (new_tp is not None)
            else:
                # Only update TP if any, but not SL
                needs_update = new_tp is not None
            
            # ALWAYS add to updates for logging, even if no changes
            update_info = {
                'ticket': position['ticket'],
                'symbol': symbol,
                'type': position['type'],
                'stage': stage,
                'previous_stage': previous_stage,
                'protection_phase': log_entry['protection_phase'],
                'current_sl': position['sl'],
                'current_tp': position['tp'],
                'new_sl': new_sl,  # Could be None (no change)
                'new_tp': new_tp,  # Could be None (no change)
                'log_entry': log_entry,
                'needs_update': needs_update,  # Flag for modification
                'skip_reason': 'worse_sl' if skip_sl_update else None
            }
            
            # Always add to updates for logging
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