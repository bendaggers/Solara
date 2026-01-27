#!/usr/bin/env python3
# mt5_interface.py - Clean MT5 Interface with minimal logging

import MetaTrader5 as mt5
from typing import Dict, List, Optional
import logging

# Set up quiet logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # Only show warnings and errors


class MT5SimpleInterface:
    """Clean MT5 interface with minimal logging"""
    
    def __init__(self, login: int, password: str, server: str):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to MT5 - minimal output"""
        if not mt5.initialize():
            print(f"❌ MT5 initialize failed")
            return False
        
        authorized = mt5.login(
            login=self.login,
            password=self.password,
            server=self.server
        )
        
        if authorized:
            self.connected = True
            return True
        else:
            print(f"❌ MT5 login failed")
            mt5.shutdown()
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions - no debug output"""
        if not self.connected:
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            result = []
            for pos in positions:
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': pos.type,
                    'entry_price': pos.price_open,
                    'current_price': pos.price_current,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'volume': pos.volume,
                    'profit': pos.profit,
                    'magic': pos.magic,
                    'comment': pos.comment or ''
                })
            
            # Only show summary
            if result:
                print(f"Found {len(result)} positions")
            
            return result
            
        except Exception as e:
            return []
    
    def modify_position(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        """Modify position SL/TP - clean version"""
        if not self.connected:
            return False
        
        try:
            # Get position
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                return False
            
            position = positions[0]
            symbol = position.symbol
            current_sl = position.sl
            current_tp = position.tp
            
            # Check if changes are needed
            sl_changed = False
            tp_changed = False
            
            # SL logic: only update if new SL is better AND different
            if sl is not None:
                # If no current SL, set it
                if current_sl == 0.0 and sl != 0.0:
                    sl_changed = True
                # If current SL exists, only update if new SL is better (tighter)
                elif current_sl != 0.0:
                    is_buy = (position.type == 0)
                    if is_buy:
                        if sl > current_sl and abs(sl - current_sl) > 0.00001:
                            sl_changed = True
                    else:
                        if sl < current_sl and abs(sl - current_sl) > 0.00001:
                            sl_changed = True
            
            # TP logic: update if different
            if tp is not None:
                if abs(tp - current_tp) > 0.00001:
                    tp_changed = True
            
            # If no changes needed
            if not sl_changed and not tp_changed:
                return True
            
            # Prepare request
            request = {
                'action': mt5.TRADE_ACTION_SLTP,
                'position': ticket,
                'symbol': symbol,
                'sl': sl if sl_changed else current_sl,
                'tp': tp if tp_changed else current_tp,
                'magic': position.magic,
                'comment': 'Auto adjust'
            }
            
            # Send request
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                # Show what was updated
                updates = []
                if sl_changed:
                    updates.append(f"SL: {current_sl:.5f}→{sl:.5f}")
                if tp_changed:
                    updates.append(f"TP: {current_tp:.5f}→{tp:.5f}")
                
                if updates:
                    print(f"#{ticket} {symbol}: {', '.join(updates)}")
                return True
            else:
                return False
            
        except Exception:
            return False
    
    def _get_pip_size(self, symbol: str) -> float:
        """Get pip size - no output"""
        symbol_upper = symbol.upper()
        
        if "JPY" in symbol_upper and not any(x in symbol_upper for x in ['XAUJPY', 'XAGJPY']):
            return 0.01
        elif any(x in symbol_upper for x in ['XAU', 'GOLD', 'XAG', 'SILVER', 'OIL']):
            return 0.01
        elif any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'ADA', 'US30', 'NAS', 'SPX', 'DAX', 'FTSE']):
            return 1.0
        else:
            return 0.0001