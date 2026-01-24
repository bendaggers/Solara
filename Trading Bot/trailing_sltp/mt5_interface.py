#!/usr/bin/env python3
# mt5_interface.py - MT5 Interface with position handling - FIXED VERSION

import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MT5SimpleInterface:
    """Simple MT5 interface with correct position handling - FIXED"""
    
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
        """Get all open positions with correct type handling - FIXED"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            result = []
            for pos in positions:
                # CRITICAL FIX: Handle SL/TP properly
                # MT5 returns 0.0 for no SL/TP, but we need to distinguish
                current_sl = pos.sl
                current_tp = pos.tp
                
                # Debug: Check what MT5 is returning
                print(f"DEBUG: Position {pos.ticket} - MT5 SL: {current_sl}, TP: {current_tp}")
                
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': pos.type,  # 0 = BUY, 1 = SELL
                    'entry_price': pos.price_open,
                    'current_price': pos.price_current,
                    'sl': current_sl,  # Keep as-is, even if 0.0
                    'tp': current_tp,  # Keep as-is, even if 0.0
                    'volume': pos.volume,
                    'profit': pos.profit,
                    'magic': pos.magic,
                    'comment': pos.comment or ''
                })
            
            print(f"📊 Found {len(result)} positions")
            
            # Debug: Show which positions have SL/TP
            for pos in result:
                has_sl = "✅" if pos['sl'] != 0.0 else "❌"
                has_tp = "✅" if pos['tp'] != 0.0 else "❌"
                print(f"   {pos['symbol']} #{pos['ticket']}: SL={has_sl}({pos['sl']:.5f}), TP={has_tp}({pos['tp']:.5f})")
            
            return result
            
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def modify_position(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        """Modify position SL/TP with brute-force adjustment - FIXED V2"""
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
            current_sl = position.sl
            current_tp = position.tp
            
            # Get pip size
            pip_size = self._get_pip_size(symbol)
            
            print(f"\n📝 Modifying position {ticket} ({symbol}):")
            print(f"   Current SL: {current_sl:.5f}, New SL: {sl if sl is not None else 'No change'}")
            print(f"   Current TP: {current_tp:.5f}, New TP: {tp if tp is not None else 'No change'}")
            
            # CRITICAL FIX: Always set SL if provided (even if current is 0.0)
            # CRITICAL FIX: Never set SL to 0.0 unless explicitly intended
            
            should_modify_sl = False
            should_modify_tp = False
            
            # Check SL - NEW LOGIC
            if sl is not None:
                # ALWAYS set SL if provided and different from current
                if abs(sl - current_sl) > 0.00001:
                    should_modify_sl = True
                    print(f"   SL change: {current_sl:.5f} → {sl:.5f}")
                elif current_sl == 0.0 and sl != 0.0:
                    # CRITICAL: Current has no SL, but we calculated one - MUST SET IT!
                    should_modify_sl = True
                    print(f"   🔥 SETTING SL: No current SL → {sl:.5f}")
                else:
                    print(f"   SL unchanged: {sl:.5f}")
            
            # Check TP
            if tp is not None:
                if abs(tp - current_tp) > 0.00001:
                    should_modify_tp = True
                    print(f"   TP change: {current_tp:.5f} → {tp:.5f}")
                else:
                    print(f"   TP unchanged: {tp:.5f}")
            
            # If no changes needed, return success
            if not should_modify_sl and not should_modify_tp:
                print(f"⚠️ Position {ticket}: No changes needed")
                return True
            
            # Try up to 20 adjustments if needed
            for attempt in range(20):
                # Calculate adjusted values
                adjusted_sl = None
                adjusted_tp = None
                
                if should_modify_sl and sl is not None:
                    adjusted_sl = self._adjust_value(sl, position.type, current_price, pip_size, attempt, is_sl=True)
                if should_modify_tp and tp is not None:
                    adjusted_tp = self._adjust_value(tp, position.type, current_price, pip_size, attempt, is_sl=False)
                
                # CRITICAL FIX: Never send 0.0 for SL unless explicitly intended
                # Build request
                request = {
                    'action': mt5.TRADE_ACTION_SLTP,
                    'position': ticket,
                    'symbol': symbol,
                }
                
                # Add SL if we're modifying it
                if should_modify_sl:
                    request['sl'] = adjusted_sl if adjusted_sl is not None else sl
                else:
                    request['sl'] = current_sl  # Keep existing
                
                # Add TP if we're modifying it
                if should_modify_tp:
                    request['tp'] = adjusted_tp if adjusted_tp is not None else tp
                else:
                    request['tp'] = current_tp  # Keep existing
                
                request['magic'] = position.magic
                request['comment'] = f'Auto adjust {attempt}'
                
                # Debug: Show request
                print(f"   Attempt {attempt+1}: SL={request.get('sl'):.5f}, TP={request.get('tp'):.5f}")
                
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
                    print(f"   Attempt {attempt + 1}: Invalid stops, adjusting...")
                    continue
                elif "no changes" in str(result.comment).lower():
                    print(f"⚠️ Position {ticket}: No changes needed")
                    return True
                else:
                    # Other error
                    print(f"❌ Position {ticket} failed: {result.comment}")
                    return False
            
            print(f"❌ Position {ticket} failed after 20 attempts")
            return False
            
        except Exception as e:
            print(f"❌ Error modifying position {ticket}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_pip_size(self, symbol: str) -> float:
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
    
    def _adjust_value(self, value: float, position_type: int, current_price: float, 
                     pip_size: float, attempt: int, is_sl: bool) -> float:
        """
        Adjust SL/TP by 1 pip per attempt
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
    
    def emergency_set_sl(self, ticket: int, sl_pips: float = 30) -> bool:
        """Emergency function to set SL for positions without one"""
        if not self.connected:
            return False
        
        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                print(f"❌ Position {ticket} not found")
                return False
            
            position = positions[0]
            symbol = position.symbol
            entry_price = position.price_open
            position_type = position.type
            current_sl = position.sl
            
            # Check if SL already exists (not 0.0)
            if current_sl != 0.0:
                print(f"⚠️ Position {ticket} already has SL: {current_sl:.5f}")
                return True
            
            # Calculate SL
            pip_size = self._get_pip_size(symbol)
            if position_type == 0:  # BUY
                sl = entry_price - (sl_pips * pip_size)
            else:  # SELL
                sl = entry_price + (sl_pips * pip_size)
            
            print(f"🚨 EMERGENCY: Setting {sl_pips}-pip SL for {symbol} #{ticket}")
            print(f"   Entry: {entry_price:.5f}, SL: {sl:.5f}")
            
            # Set SL
            request = {
                'action': mt5.TRADE_ACTION_SLTP,
                'position': ticket,
                'symbol': symbol,
                'sl': sl,
                'tp': position.tp if position.tp != 0.0 else 0.0,
                'magic': position.magic,
                'comment': 'Emergency SL set'
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ Emergency SL set for position {ticket}")
                return True
            else:
                print(f"❌ Failed to set emergency SL: {result.comment}")
                return False
                
        except Exception as e:
            print(f"❌ Error in emergency_set_sl: {e}")
            return False
    
    def ensure_all_positions_have_sl(self, default_sl_pips: float = 30) -> Dict:
        """Ensure all positions have at least a basic SL"""
        positions = self.get_positions()
        results = {'total': len(positions), 'updated': 0, 'already_have_sl': 0}
        
        for pos in positions:
            if pos['sl'] == 0.0:
                print(f"🚨 Position {pos['ticket']} ({pos['symbol']}) has no SL!")
                if self.emergency_set_sl(pos['ticket'], default_sl_pips):
                    results['updated'] += 1
            else:
                results['already_have_sl'] += 1
        
        print(f"\n📊 SL Status: {results['updated']} updated, {results['already_have_sl']} already have SL")
        return results