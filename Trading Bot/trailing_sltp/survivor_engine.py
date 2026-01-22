# survivor_engine.py - CORRECTED FOR YOUR JSON STRUCTURE

import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SurvivorEngine:
    """Survivor's Edition v2.6 Engine - CORRECT IMPLEMENTATION"""
    
    def __init__(self, market_data_file: str, hysteresis_config: Dict, safe_distance_config: Dict):
        self.market_data_file = market_data_file
        self.market_data = {}
        self.hysteresis = hysteresis_config
        self.safe_distance = safe_distance_config
        
        # Stage definitions PER SPEC v2.6
        self.stage_definitions = {
            'STAGE_0': {'threshold': 0.25, 'protection': 0.00, 'tp': True,  'description': 'Entry (<25% BB)'},
            'STAGE_1': {'threshold': 0.40, 'protection': 0.25, 'tp': True,  'description': '25% protection'},
            'STAGE_1A': {'threshold': 0.50, 'protection': 0.40, 'tp': True,  'description': '40% protection'},
            'STAGE_2A': {'threshold': 0.60, 'protection': 0.50, 'tp': True,  'description': '50% protection'},
            'STAGE_2B': {'threshold': 0.70, 'protection': 0.60, 'tp': True,  'description': '60% protection'},
            'STAGE_2C': {'threshold': 0.80, 'protection': 0.70, 'tp': False, 'description': '70% protection'},
            'STAGE_3A': {'threshold': 0.90, 'protection': 0.75, 'tp': False, 'description': '75% protection'},
            'STAGE_3B': {'threshold': 1.20, 'protection': 0.80, 'tp': False, 'description': '80% hybrid protection'},
            'STAGE_4':  {'threshold': 1.80, 'protection': 0.85, 'tp': False, 'description': '85% trailing'},
            'STAGE_5':  {'threshold': float('inf'), 'protection': 0.90, 'tp': False, 'description': '90% trailing'}
        }
        
        # Stage thresholds
        self.stage_thresholds = [
            ('STAGE_0', 0.00),
            ('STAGE_1', 0.25),
            ('STAGE_1A', 0.40),
            ('STAGE_2A', 0.50),
            ('STAGE_2B', 0.60),
            ('STAGE_2C', 0.70),
            ('STAGE_3A', 0.80),
            ('STAGE_3B', 0.90),
            ('STAGE_4', 1.20),
            ('STAGE_5', 1.80)
        ]
        
        # Load confirmed stages
        self.confirmed_stages = self._load_confirmed_stages()
    
    def _load_confirmed_stages(self) -> Dict:
        """Load confirmed stages from file"""
        try:
            if os.path.exists("state/confirmed_stages.json"):
                with open("state/confirmed_stages.json", 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def save_confirmed_stages(self):
        """Save confirmed stages to file"""
        try:
            os.makedirs("state", exist_ok=True)
            with open("state/confirmed_stages.json", 'w') as f:
                json.dump(self.confirmed_stages, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save confirmed stages: {e}")
    
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
    
    def load_market_data(self) -> bool:
        """Load market data from JSON file - EXACTLY LIKE YOUR OLD CODE"""
        try:
            if not os.path.exists(self.market_data_file):
                print(f"❌ Market data file not found: {self.market_data_file}")
                return False
            
            with open(self.market_data_file, 'r') as f:
                data = json.load(f)
            
            self.market_data = {}
            
            # Check if data is in 'data' key or is the main list
            if 'data' in data:
                items = data['data']
            else:
                items = data  # Assume data is the list
            
            for item in items:
                symbol = item.get('pair', '')
                if not symbol:
                    continue
                
                # Extract Bollinger Bands - handle different key names
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
            
            print(f"✅ Loaded market data for {len(self.market_data)} symbols")
            return True
            
        except Exception as e:
            print(f"❌ Error loading market data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def calculate_profit_ratio(self, position: Dict, symbol_data: Dict) -> float:
        """Calculate profit ratio: profit_pips / bb_width"""
        try:
            symbol = position['symbol']
            pip_size = self.get_pip_size(symbol)
            
            # Current profit in pips (absolute)
            entry = position['entry_price']
            current = position['current_price']
            profit_pips = abs(current - entry) / pip_size
            
            # BB width in pips
            bb_width = symbol_data['bb_width']
            bb_width_pips = bb_width / pip_size
            
            if bb_width_pips <= 0:
                return 0.0
            
            return profit_pips / bb_width_pips
            
        except Exception as e:
            print(f"Error calculating profit ratio for {position['symbol']}: {e}")
            return 0.0
    
    def determine_stage(self, profit_ratio: float, position_id: str) -> str:
        """Determine current stage based on profit ratio"""
        previous = self.confirmed_stages.get(position_id, 'STAGE_0')
        
        # Find which stage we should be in
        current_stage = 'STAGE_0'
        for stage, threshold in self.stage_thresholds:
            if profit_ratio >= threshold:
                current_stage = stage
            else:
                break
        
        # Apply hysteresis
        if current_stage != previous:
            if current_stage > previous:  # Moving up
                current_threshold = self.stage_definitions[current_stage]['threshold']
                if profit_ratio >= current_threshold - self.hysteresis.get('up_buffer', 0.02):
                    new_stage = current_stage
                else:
                    new_stage = previous
            else:  # Moving down
                prev_threshold = self.stage_definitions[previous]['threshold']
                if profit_ratio <= prev_threshold - self.hysteresis.get('down_buffer', 0.05):
                    new_stage = current_stage
                else:
                    new_stage = previous
        else:
            new_stage = previous
        
        # One-way transition: Can't go back from trailing stages
        trailing_stages = ['STAGE_3B', 'STAGE_4', 'STAGE_5']
        if previous in trailing_stages and new_stage < previous:
            new_stage = previous
        
        # Save confirmed stage
        self.confirmed_stages[position_id] = new_stage
        return new_stage
    
    def calculate_sl(self, position: Dict, stage: str, symbol_data: Dict) -> Optional[float]:
        """Calculate Stop Loss based on stage"""
        try:
            symbol = position['symbol']
            entry = position['entry_price']
            current = position['current_price']
            is_buy = (position['type'] == 0)  # 0 = BUY, 1 = SELL
            pip_size = self.get_pip_size(symbol)
            
            # Current profit in pips
            profit_pips = abs(current - entry) / pip_size
            
            # Get stage info
            stage_info = self.stage_definitions[stage]
            protection = stage_info['protection']
            
            # Stage 0: Fixed 30 pip stop
            if stage == 'STAGE_0':
                if is_buy:
                    sl = entry - (30 * pip_size)
                else:
                    sl = entry + (30 * pip_size)
            
            # Profit-locking stages (1-3A)
            elif stage in ['STAGE_1', 'STAGE_1A', 'STAGE_2A', 'STAGE_2B', 'STAGE_2C', 'STAGE_3A']:
                if is_buy:
                    sl = entry + (protection * profit_pips * pip_size)
                else:
                    sl = entry - (protection * profit_pips * pip_size)
            
            # Stage 3B: Hybrid protection
            elif stage == 'STAGE_3B':
                bb_width = symbol_data['bb_width']
                
                # Method 1: 80% profit lock
                if is_buy:
                    profit_lock_sl = entry + (0.80 * profit_pips * pip_size)
                else:
                    profit_lock_sl = entry - (0.80 * profit_pips * pip_size)
                
                # Method 2: 20% BB trailing
                if is_buy:
                    trailing_sl = current - (0.20 * bb_width)
                else:
                    trailing_sl = current + (0.20 * bb_width)
                
                # Choose better protection
                if is_buy:
                    sl = max(profit_lock_sl, trailing_sl)
                else:
                    sl = min(profit_lock_sl, trailing_sl)
            
            # Price-trailing stages (4-5)
            elif stage in ['STAGE_4', 'STAGE_5']:
                if is_buy:
                    sl = current - (protection * profit_pips * pip_size)
                else:
                    sl = current + (protection * profit_pips * pip_size)
            
            else:
                # Fallback
                if is_buy:
                    sl = entry - (30 * pip_size)
                else:
                    sl = entry + (30 * pip_size)
            
            # Apply safe distance
            sl = self._apply_safe_distance(sl, current, is_buy, pip_size)
            
            return round(sl, 5)
            
        except Exception as e:
            print(f"Error calculating SL for {position['symbol']}: {e}")
            return None
    
    def calculate_tp(self, position: Dict, stage: str, symbol_data: Dict) -> Optional[float]:
        """Calculate Take Profit based on stage"""
        try:
            is_buy = (position['type'] == 0)
            stage_info = self.stage_definitions[stage]
            
            # No TP for stages 2C and above
            if not stage_info['tp']:
                return None
            
            # Use Bollinger Bands for stages with TP
            if is_buy:
                tp = symbol_data['upper_band']
            else:
                tp = symbol_data['lower_band']
            
            return round(tp, 5)
            
        except Exception as e:
            print(f"Error calculating TP: {e}")
            return None
    
    def _apply_safe_distance(self, sl: float, current_price: float, is_buy: bool, pip_size: float) -> float:
        """Ensure SL is at safe distance from current price"""
        min_pips = self.safe_distance.get('min_pips', 10)
        min_distance = min_pips * pip_size
        
        current_distance = abs(current_price - sl)
        
        if current_distance < min_distance:
            if is_buy:
                sl = current_price - min_distance
            else:
                sl = current_price + min_distance
            
            print(f"Adjusted SL for safe distance")
        
        return sl
    
    def is_better_sl(self, new_sl: float, current_sl: float, is_buy: bool) -> bool:
        """Check if new SL provides better protection"""
        if abs(current_sl) < 0.00001:  # No current SL
            return True
        
        if is_buy:
            return new_sl > current_sl  # Higher is better for BUY
        else:
            return new_sl < current_sl  # Lower is better for SELL
    
    def process_all_positions(self, positions: List[Dict]) -> List[Dict]:
        """Process all positions"""
        updates = []
        
        if not self.market_data:
            print("❌ No market data loaded")
            return updates
        
        for position in positions:
            symbol = position['symbol']
            
            if symbol not in self.market_data:
                print(f"⚠️ No market data for {symbol}")
                continue
            
            symbol_data = self.market_data[symbol]
            
            # Calculate profit ratio
            profit_ratio = self.calculate_profit_ratio(position, symbol_data)
            
            # Generate position ID
            position_id = f"{position['ticket']}_{symbol}"
            
            # Determine stage
            stage = self.determine_stage(profit_ratio, position_id)
            
            # Calculate new SL/TP
            new_sl = self.calculate_sl(position, stage, symbol_data)
            new_tp = self.calculate_tp(position, stage, symbol_data)
            
            # Get current values
            current_sl = position.get('sl', 0.0)
            current_tp = position.get('tp', 0.0)
            
            # Check if new SL is better
            is_buy = (position['type'] == 0)
            should_update_sl = False
            
            if new_sl is not None and self.is_better_sl(new_sl, current_sl, is_buy):
                should_update_sl = True
            else:
                new_sl = None  # Don't update
            
            # Check if TP needs update
            should_update_tp = (new_tp is not None and abs(new_tp - current_tp) > 0.00001)
            
            # Determine if update is needed
            needs_update = (should_update_sl or should_update_tp)
            
            # Create update info
            updates.append({
                'ticket': position['ticket'],
                'symbol': symbol,
                'stage': stage,
                'current_sl': current_sl,
                'current_tp': current_tp,
                'new_sl': new_sl,
                'new_tp': new_tp,
                'needs_update': needs_update,
                'protection_percent': int(self.stage_definitions[stage]['protection'] * 100),
                'profit_ratio': round(profit_ratio, 3)
            })
        
        # Save confirmed stages
        self.save_confirmed_stages()
        
        return updates
    
    def get_protection_percent(self, stage: str) -> float:
        """Get protection percentage for a stage"""
        if stage in self.stage_definitions:
            return self.stage_definitions[stage]['protection']
        return 0.0