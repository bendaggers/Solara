# trailing_sltp/sltp_engine.py
import json
import os
from typing import Dict, List, Optional, Tuple


class SLTPEngine:
    """Implements the trailing SL/TP logic"""
    
    def __init__(self, market_data_file: str):
        self.market_data_file = market_data_file
        self.market_data = {}
        self.pip_sizes = {
            'default': 0.0001,
            'JPY': 0.01,
            'XAU': 0.01,
            'XAG': 0.01,
            'OIL': 0.01,
            'CRYPTO': 1.0,
            'INDICES': 1.0
        }
    
    def load_market_data(self) -> bool:
        try:
            if not os.path.exists(self.market_data_file):
                print(f"❌ Market data file not found: {self.market_data_file}")
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
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading market data: {e}")
            return False
    
    def get_pip_size(self, symbol: str) -> float:
        symbol_upper = symbol.upper()
        
        if "XAU" in symbol_upper or "GOLD" in symbol_upper:
            return self.pip_sizes['XAU']
        elif "XAG" in symbol_upper or "SILVER" in symbol_upper:
            return self.pip_sizes['XAG']
        elif any(oil in symbol_upper for oil in ["OIL", "WTI", "BRENT", "USOIL", "UKOIL"]):
            return self.pip_sizes['OIL']
        elif "JPY" in symbol_upper:
            return self.pip_sizes['JPY']
        elif any(index in symbol_upper for index in ["US30", "NAS100", "SPX500", "DAX", "FTSE", "NIKKEI"]):
            return self.pip_sizes['INDICES']
        elif any(crypto in symbol_upper for crypto in ["BTC", "ETH", "XRP", "LTC"]):
            return self.pip_sizes['CRYPTO']
        
        return self.pip_sizes['default']
    
    def calculate_stage1_sl(self, position: Dict, bb_width: float) -> Optional[float]:
        try:
            symbol = position['symbol']
            pip_size = self.get_pip_size(symbol)
            current_price = position['current_price']
            entry_price = position['entry_price']
            current_sl = position['sl']
            
            if position['type'] == 'BUY':
                pip_profit = (current_price - entry_price) / pip_size
            else:  # SELL
                pip_profit = (entry_price - current_price) / pip_size
            
            if pip_profit < 20:
                return None
            
            lock_distance_pips = min(10, 0.15 * bb_width / pip_size)
            lock_distance_price = lock_distance_pips * pip_size
            
            if position['type'] == 'BUY':
                new_sl = entry_price + lock_distance_price
                if new_sl > current_sl:
                    return new_sl
            else:  # SELL
                new_sl = entry_price - lock_distance_price
                if new_sl < current_sl:
                    return new_sl
            
            return None
            
        except Exception:
            return None
    
    def calculate_stage2_sl(self, position: Dict, bb_data: Dict) -> Optional[float]:
        try:
            bb_width = bb_data['bb_width']
            buffer = 0.10 * bb_width
            current_sl = position['sl']
            
            if position['type'] == 'BUY':
                buffered_sl = bb_data['middle_band'] - buffer
                if buffered_sl > current_sl:
                    return buffered_sl
            else:  # SELL
                buffered_sl = bb_data['middle_band'] + buffer
                if buffered_sl < current_sl:
                    return buffered_sl
            
            return None
            
        except Exception:
            return None
    
    def calculate_catastrophic_tp(self, position: Dict, bb_data: Dict) -> float:
        try:
            tp_distance = 0.90 * bb_data['bb_width']
            
            if position['type'] == 'BUY':
                return position['entry_price'] + tp_distance
            else:  # SELL
                return position['entry_price'] - tp_distance
                
        except Exception:
            return position['tp']
    
    def should_adjust_tp(self, current_tp: float, new_tp: float, position_type: str) -> bool:
        if position_type == 'BUY':
            return new_tp > current_tp
        else:  # SELL
            return new_tp < current_tp
    
    def calculate_new_sl_tp(self, position: Dict) -> Tuple[Optional[float], Optional[float]]:
        symbol = position['symbol']
        
        if symbol not in self.market_data:
            return None, None
        
        bb_data = self.market_data[symbol]
        new_sl = None
        new_tp = None
        
        pip_size = self.get_pip_size(symbol)
        if position['type'] == 'BUY':
            pip_profit = (position['current_price'] - position['entry_price']) / pip_size
        else:  # SELL
            pip_profit = (position['entry_price'] - position['current_price']) / pip_size
        
        if pip_profit >= 20:
            stage2_sl = self.calculate_stage2_sl(position, bb_data)
            if stage2_sl:
                new_sl = stage2_sl
            else:
                stage1_sl = self.calculate_stage1_sl(position, bb_data['bb_width'])
                if stage1_sl:
                    new_sl = stage1_sl
        
        calculated_tp = self.calculate_catastrophic_tp(position, bb_data)
        
        if self.should_adjust_tp(position['tp'], calculated_tp, position['type']):
            new_tp = calculated_tp
        
        return new_sl, new_tp
    
    def process_positions(self, positions: List[Dict]) -> List[Dict]:
        updates_needed = []
        
        for position in positions:
            new_sl, new_tp = self.calculate_new_sl_tp(position)
            
            if new_sl is not None or new_tp is not None:
                update_info = {
                    'ticket': position['ticket'],
                    'symbol': position['symbol'],
                    'type': position['type'],
                    'current_sl': position['sl'],
                    'current_tp': position['tp'],
                    'new_sl': new_sl,
                    'new_tp': new_tp
                }
                updates_needed.append(update_info)
        
        return updates_needed