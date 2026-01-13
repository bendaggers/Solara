import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import logging

logging.basicConfig(level=logging.WARNING)  # Reduce default logging level
logger = logging.getLogger(__name__)


class SLTPEngine:
    """SIMPLE, RELIABLE SL/TP engine - NO COMPLEX LOGIC"""
    
    def __init__(self, market_data_file: str):
        self.market_data_file = market_data_file
        self.market_data = {}
        
        # Pip sizes
        self.pip_sizes = {
            'default': 0.0001, 'JPY': 0.01, 'XAU': 0.01, 'XAG': 0.01,
            'OIL': 0.01, 'CRYPTO': 1.0, 'INDICES': 1.0
        }
        
        # Stage thresholds
        self.stage_thresholds = {
            'STAGE_0': 0.25, 'STAGE_1': 0.50, 'STAGE_2A': 0.65,
            'STAGE_2B': 0.80, 'STAGE_2C': 0.90, 'STAGE_3': 1.50,
            'STAGE_4': float('inf')
        }
    
    # ========== SIMPLE HELPER METHODS ==========
    
    def load_market_data(self) -> bool:
        """Load market data - SIMPLE"""
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
                    'lower_band': item['lower_band'],
                    'middle_band': item['middle_band'],
                    'upper_band': item['upper_band'],
                    'bb_width': item['upper_band'] - item['lower_band']
                }
            
            logger.info(f"Loaded market data for {len(self.market_data)} symbols")
            return True
            
        except Exception as e:
            logger.error(f"Error loading market data: {e}")
            return False
    
    def get_pip_size(self, symbol: str) -> float:
        """Get pip size - SIMPLE"""
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
        """Calculate profit ratio - SIMPLE"""
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
    
    def determine_stage(self, profit_ratio: float) -> str:
        """Determine stage - SIMPLE"""
        if profit_ratio < self.stage_thresholds['STAGE_0']:
            return 'STAGE_0'
        elif profit_ratio < self.stage_thresholds['STAGE_1']:
            return 'STAGE_1'
        elif profit_ratio < self.stage_thresholds['STAGE_2A']:
            return 'STAGE_2A'
        elif profit_ratio < self.stage_thresholds['STAGE_2B']:
            return 'STAGE_2B'
        elif profit_ratio < self.stage_thresholds['STAGE_2C']:
            return 'STAGE_2C'
        elif profit_ratio < self.stage_thresholds['STAGE_3']:
            return 'STAGE_3'
        else:
            return 'STAGE_4'
    
    # ========== CRITICAL: ALWAYS SET SL IF MISSING ==========
    
    def ensure_sl_exists(self, position: Dict, bb_data: Dict, stage: str, profit_pips: float = 0) -> Optional[float]:
        """ENSURE SL EXISTS - ALWAYS returns an SL if missing"""
        symbol = position['symbol']
        entry_price = position['entry_price']
        current_sl = position['sl']
        pip_size = self.get_pip_size(symbol)
        
        # If SL already exists, return None (no change)
        if abs(current_sl) > 0.00001:
            return None
        
        logger.warning(f"🚨 {symbol} has NO SL! Initializing for Stage {stage}")
        
        # Calculate SL based on stage
        if stage == 'STAGE_0':
            # Entry ± 30 pips
            if position['type'] == 'BUY':
                return entry_price - (30 * pip_size)
            else:
                return entry_price + (30 * pip_size)
        
        elif stage == 'STAGE_1':
            # 50% profit lock
            protected_pips = 0.50 * profit_pips
            protected_price = protected_pips * pip_size
            
            if position['type'] == 'BUY':
                return entry_price + protected_price
            else:
                return entry_price - protected_price
        
        elif stage == 'STAGE_2A':
            # Dual-option: 60% profit lock OR Middle BB - 3%
            profit_lock_sl = entry_price + (0.60 * profit_pips * pip_size) if position['type'] == 'BUY' else entry_price - (0.60 * profit_pips * pip_size)
            middle_bb_sl = bb_data['middle_band'] - (0.03 * bb_data['bb_width']) if position['type'] == 'BUY' else bb_data['middle_band'] + (0.03 * bb_data['bb_width'])
            
            if position['type'] == 'BUY':
                return max(profit_lock_sl, middle_bb_sl)
            else:
                return min(profit_lock_sl, middle_bb_sl)
        
        elif stage == 'STAGE_2B':
            # Dual-option with sign flip
            profit_lock_sl = entry_price + (0.70 * profit_pips * pip_size) if position['type'] == 'BUY' else entry_price - (0.70 * profit_pips * pip_size)
            middle_bb_sl = bb_data['middle_band'] + (0.05 * bb_data['bb_width']) if position['type'] == 'BUY' else bb_data['middle_band'] - (0.05 * bb_data['bb_width'])
            
            if position['type'] == 'BUY':
                return max(profit_lock_sl, middle_bb_sl)
            else:
                return min(profit_lock_sl, middle_bb_sl)
        
        elif stage == 'STAGE_2C':
            # Dual-option: 80% profit lock OR Price - 7%
            profit_lock_sl = entry_price + (0.80 * profit_pips * pip_size) if position['type'] == 'BUY' else entry_price - (0.80 * profit_pips * pip_size)
            price_based_sl = position['current_price'] - (0.07 * bb_data['bb_width']) if position['type'] == 'BUY' else position['current_price'] + (0.07 * bb_data['bb_width'])
            
            if position['type'] == 'BUY':
                return max(profit_lock_sl, price_based_sl)
            else:
                return min(profit_lock_sl, price_based_sl)
        
        elif stage == 'STAGE_3':
            # Price-based trailing with 2% buffer
            if position['type'] == 'BUY':
                return position['current_price'] - (0.02 * bb_data['bb_width'])
            else:
                return position['current_price'] + (0.02 * bb_data['bb_width'])
        
        elif stage == 'STAGE_4':
            # Ultra-tight trailing with 1.5% buffer
            if position['type'] == 'BUY':
                return position['current_price'] - (0.015 * bb_data['bb_width'])
            else:
                return position['current_price'] + (0.015 * bb_data['bb_width'])
        
        # Fallback: Stage 0 SL
        logger.error(f"Unknown stage {stage}, using Stage 0 SL")
        if position['type'] == 'BUY':
            return entry_price - (30 * pip_size)
        else:
            return entry_price + (30 * pip_size)
    
    def calculate_tp(self, position: Dict, bb_data: Dict, stage: str) -> Optional[float]:
        """Calculate TP based on stage"""
        symbol = position['symbol']
        entry_price = position['entry_price']
        current_tp = position['tp']
        pip_size = self.get_pip_size(symbol)
        current_price = position['current_price']
        
        # For stages 2C-4: TP = REMOVED
        if stage in ['STAGE_2C', 'STAGE_3', 'STAGE_4']:
            # Only remove TP if it exists
            if abs(current_tp) > 0.00001:
                return 0.0  # Remove TP
            return None  # TP already removed
        
        # For stages 0-2B: Set TP based on rules
        
        # If TP already exists, check if we can improve it
        tp_to_set = None
        
        if stage == 'STAGE_0':
            # Entry ± 40 pips
            if position['type'] == 'BUY':
                tp_to_set = entry_price + (40 * pip_size)
            else:
                tp_to_set = entry_price - (40 * pip_size)
        
        elif stage in ['STAGE_1', 'STAGE_2A', 'STAGE_2B']:
            # TP = Upper BB for BUY, Lower BB for SELL
            # But ensure TP is in correct direction
            if position['type'] == 'BUY':
                tp_to_set = bb_data['upper_band']
                # Ensure TP is above current price
                if tp_to_set <= current_price:
                    tp_to_set = current_price + (0.05 * bb_data['bb_width'])
            else:
                tp_to_set = bb_data['lower_band']
                # Ensure TP is below current price
                if tp_to_set >= current_price:
                    tp_to_set = current_price - (0.05 * bb_data['bb_width'])
        
        # Check if TP needs to be set or improved
        if abs(current_tp) < 0.00001:
            # TP is missing, set it
            return tp_to_set
        else:
            # TP exists, only improve if better
            if position['type'] == 'BUY' and tp_to_set > current_tp:
                return tp_to_set
            elif position['type'] == 'SELL' and tp_to_set < current_tp:
                return tp_to_set
        
        return None
    
    # ========== MAIN METHOD - SIMPLE AND RELIABLE ==========
    
    def calculate_new_sl_tp(self, position: Dict) -> Tuple[Optional[float], Optional[float], str, Dict]:
        """SIMPLE MAIN METHOD - ALWAYS ensures SL exists"""
        symbol = position['symbol']
        
        # Check market data
        if symbol not in self.market_data:
            return None, None, 'NO_DATA', {}
        
        bb_data = self.market_data[symbol]
        
        # Calculate profit and stage
        profit_ratio = self.calculate_profit_ratio(position, bb_data)
        stage = self.determine_stage(profit_ratio)
        
        # Calculate profit in pips for SL calculations
        pip_size = self.get_pip_size(symbol)
        if position['type'] == 'BUY':
            profit_pips = (position['current_price'] - position['entry_price']) / pip_size
        else:
            profit_pips = (position['entry_price'] - position['current_price']) / pip_size
        
        # Debug info
        debug_info = {
            'profit_ratio': profit_ratio,
            'profit_pips': profit_pips,
            'stage': stage,
            'original_sl': position['sl'],
            'original_tp': position['tp'],
            'upper_bb': bb_data['upper_band'],
            'lower_bb': bb_data['lower_band'],
            'bb_width': bb_data['bb_width']
        }
        
        # ===== CRITICAL: ALWAYS ENSURE SL EXISTS =====
        new_sl = self.ensure_sl_exists(position, bb_data, stage, profit_pips)
        
        # ===== CALCULATE TP =====
        new_tp = self.calculate_tp(position, bb_data, stage)
        
        debug_info['calculated_sl'] = new_sl
        debug_info['calculated_tp'] = new_tp
        
        # Final values
        final_sl = new_sl
        final_tp = new_tp
        
        debug_info['final_sl'] = final_sl
        debug_info['final_tp'] = final_tp
        
        # REMOVED: Individual log messages for each position
        # The cycle summary will provide the necessary information
        
        return final_sl, final_tp, stage, debug_info
    
    def process_positions(self, positions: List[Dict]) -> List[Dict]:
        """Process all positions - SIMPLE"""
        updates_needed = []
        
        if not self.market_data:
            logger.error("No market data loaded")
            return updates_needed
        
        # Count missing SL/TP
        missing_sl = sum(1 for p in positions if abs(p['sl']) < 0.00001)
        missing_tp = sum(1 for p in positions if abs(p['tp']) < 0.00001)
        
        if missing_sl > 0:
            logger.warning(f"🚨 Found {missing_sl} positions WITHOUT SL")
        if missing_tp > 0:
            logger.warning(f"⚠️  Found {missing_tp} positions WITHOUT TP")
        
        for position in positions:
            symbol = position['symbol']
            
            if symbol not in self.market_data:
                continue
            
            new_sl, new_tp, stage, debug_info = self.calculate_new_sl_tp(position)
            
            # Add to updates if anything changed
            if new_sl is not None or new_tp is not None:
                update_info = {
                    'ticket': position['ticket'],
                    'symbol': symbol,
                    'type': position['type'],
                    'stage': stage,
                    'current_sl': position['sl'],
                    'current_tp': position['tp'],
                    'new_sl': new_sl,
                    'new_tp': new_tp,
                    'debug_info': debug_info
                }
                updates_needed.append(update_info)
        
        return updates_needed