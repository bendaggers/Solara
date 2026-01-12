# trailing_sltp/mt5_interface.py
import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple


class MT5Interface:
    """Handles all MT5 interactions for the trailing SL/TP system"""
    
    def __init__(self, login: int, password: str, server: str):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        
    def connect(self) -> bool:
        if not mt5.initialize():
            print(f"❌ MT5 initialization failed: {mt5.last_error()}")
            return False
        
        authorized = mt5.login(
            login=self.login,
            password=self.password,
            server=self.server
        )
        
        if authorized:
            self.connected = True
            print(f"✅ Connected to MT5 account {self.login}")
            return True
        else:
            print(f"❌ MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
    
    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("✅ Disconnected from MT5")
    
    def get_open_positions(self) -> List[Dict]:
        if not self.connected:
            print("❌ Not connected to MT5")
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                print("📭 No open positions found")
                return []
            
            positions_list = []
            for pos in positions:
                position_dict = {
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'entry_price': pos.price_open,
                    'current_price': pos.price_current,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'profit': pos.profit,
                }
                positions_list.append(position_dict)
            
            return positions_list
            
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
            return []
    
    def modify_position(self, ticket: int, sl: float, tp: float) -> Tuple[bool, str]:
        if not self.connected:
            return False, "Not connected to MT5"
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return False, f"Position {ticket} not found"
            
            position = position[0]
            
            # Check if values are actually different
            if abs(sl - position.sl) < 0.00001 and abs(tp - position.tp) < 0.00001:
                return False, "10025 - No changes"
            
            # Validate SL direction
            if position.type == mt5.ORDER_TYPE_BUY and sl >= position.price_current:
                return False, f"Invalid stops: SL ({sl:.5f}) must be below current price ({position.price_current:.5f}) for BUY"
            
            if position.type == mt5.ORDER_TYPE_SELL and sl <= position.price_current:
                return False, f"Invalid stops: SL ({sl:.5f}) must be above current price ({position.price_current:.5f}) for SELL"
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": sl,
                "tp": tp,
                "symbol": position.symbol,
                "magic": position.magic,
                "comment": "Trailing SL/TP Update"
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return True, "Success"
            else:
                return False, f"{result.retcode} - {result.comment}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"