# mt5_simple_interface.py
import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MT5SimpleInterface:
    """Simple MT5 interface with correct position handling"""
    
    def __init__(self, login: int, password: str, server: str):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to MT5"""
        if not mt5.initialize():
            logger.error(f"MT5 initialize failed: {mt5.last_error()}")
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
            logger.error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("Disconnected from MT5")
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions with CORRECT type handling"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            result = []
            for pos in positions:
                # CRITICAL: Use pos.type directly (0=BUY, 1=SELL)
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': pos.type,  # 0 = BUY, 1 = SELL
                    'entry_price': pos.price_open,
                    'current_price': pos.price_current,
                    'sl': pos.sl if pos.sl is not None else 0.0,
                    'tp': pos.tp if pos.tp is not None else 0.0,
                    'volume': pos.volume,
                    'profit': pos.profit,
                    'magic': pos.magic,
                    'comment': pos.comment or ''
                })
            
            print(f"📊 Found {len(result)} positions")
            return result
            
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            return []
    
    def modify_position(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        """Modify position SL/TP with brute-force adjustment"""
        if not self.connected:
            print(f"❌ Not connected to MT5")
            return False
        
        try:
            # Get position info
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                print(f"❌ Position {ticket} not found")
                return False
            
            position = positions[0]
            symbol = position.symbol
            current_price = position.price_current
            
            # Get pip size
            pip_size = 0.0001 if symbol.find("JPY") == -1 else 0.01
            
            # Try up to 20 adjustments
            for attempt in range(20):
                # Calculate adjusted values
                adjusted_sl = self._adjust_value(sl, position.type, current_price, pip_size, attempt, is_sl=True) if sl is not None else None
                adjusted_tp = self._adjust_value(tp, position.type, current_price, pip_size, attempt, is_sl=False) if tp is not None else None
                
                # Build request
                request = {
                    'action': mt5.TRADE_ACTION_SLTP,
                    'position': ticket,
                    'symbol': symbol,
                    'sl': adjusted_sl if adjusted_sl is not None else 0.0,
                    'tp': adjusted_tp if adjusted_tp is not None else 0.0,
                    'magic': position.magic,
                    'comment': f'Auto adjust {attempt}'
                }
                
                # Send request
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    if attempt == 0:
                        print(f"✅ Position {ticket} modified (no adjustment needed)")
                    else:
                        print(f"✅ Position {ticket} modified after {attempt} adjustments")
                    return True
                elif "Invalid stops" in str(result.comment):
                    # Continue adjusting
                    continue
                else:
                    # Other error
                    print(f"❌ Position {ticket} failed: {result.comment}")
                    return False
            
            print(f"❌ Position {ticket} failed after 20 attempts")
            return False
            
        except Exception as e:
            print(f"❌ Error modifying position {ticket}: {e}")
            return False
    
    def _adjust_value(self, value: float, position_type: int, current_price: float, 
                     pip_size: float, attempt: int, is_sl: bool) -> float:
        """
        Adjust SL/TP by 1 pip per attempt
        
        Rules:
        - SL: Move AWAY from current price (safer)
        - TP: Move FURTHER in profit direction (more conservative)
        """
        adjustment = attempt * pip_size
        
        if is_sl:
            # Stop Loss
            if position_type == 0:  # BUY
                return value - adjustment  # Move down (away from price)
            else:  # SELL
                return value + adjustment  # Move up (away from price)
        else:
            # Take Profit
            if position_type == 0:  # BUY
                return value + adjustment  # Move up (further profit)
            else:  # SELL
                return value - adjustment  # Move down (further profit)
    
    def get_account_info(self) -> Dict:
        """Get account information"""
        if not self.connected:
            return {}
        
        try:
            account = mt5.account_info()
            if account:
                return {
                    'balance': account.balance,
                    'equity': account.equity,
                    'margin': account.margin,
                    'free_margin': account.margin_free,
                    'leverage': account.leverage
                }
        except:
            pass
        
        return {}