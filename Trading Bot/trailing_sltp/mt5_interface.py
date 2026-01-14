import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MT5Interface:
    """MT5 interface with enhanced safe distance protection"""
    
    def __init__(self, login: int, password: str, server: str):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.spread_cache = {}  # Cache for spreads to avoid repeated API calls
        
    def connect(self) -> bool:
        """Connect to MT5"""
        if not mt5.initialize():
            logger.error(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        authorized = mt5.login(
            login=self.login,
            password=self.password,
            server=self.server
        )
        
        if authorized:
            self.connected = True
            logger.info(f"✅ Connected to MT5 account {self.login}")
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
            logger.info("Disconnected from MT5")
    
    def get_current_spread(self, symbol: str) -> float:
        """Get current spread in pips"""
        try:
            if symbol in self.spread_cache:
                return self.spread_cache[symbol]
            
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                spread = symbol_info.spread
                # Convert spread to pips
                pip_size = 0.0001 if symbol.find("JPY") == -1 else 0.01
                spread_pips = spread * pip_size * 10  # Convert points to pips
                
                self.spread_cache[symbol] = spread_pips
                return spread_pips
        except:
            pass
        
        # Return default if can't get spread
        return 2.0  # Default 2 pips spread
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        if not self.connected:
            logger.error("Not connected to MT5")
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                logger.info("No open positions found")
                return []
            
            positions_list = []
            for pos in positions:
                position_dict = {
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'entry_price': pos.price_open,
                    'current_price': pos.price_current,
                    'sl': pos.sl if pos.sl is not None else 0.0,
                    'tp': pos.tp if pos.tp is not None else 0.0,
                    'profit': pos.profit,
                    'volume': pos.volume,
                    'magic': pos.magic,
                    'comment': pos.comment,
                }
                positions_list.append(position_dict)
            
            return positions_list
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def modify_position(self, ticket: int, sl: float, tp: float) -> Tuple[bool, str]:
        """Modify position with enhanced validation"""
        if not self.connected:
            return False, "Not connected to MT5"
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return False, f"Position {ticket} not found"
            
            position = position[0]
            current_price = position.price_current
            symbol = position.symbol
            
            # Determine pip size
            pip_size = 0.0001 if symbol.find("JPY") == -1 else 0.01
            
            # Build request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "magic": position.magic,
                "comment": "Auto SL/TP Update"
            }
            
            # Handle SL
            if sl is not None:
                request["sl"] = sl
            else:
                # Use current SL if not changing
                request["sl"] = position.sl if position.sl is not None else 0.0
            
            # Handle TP
            if tp is not None:
                request["tp"] = tp
            else:
                # Use current TP if not changing
                request["tp"] = position.tp if position.tp is not None else 0.0
            
            # Validate SL
            sl_to_check = request["sl"]
            if sl_to_check != 0.0:  # Only validate if SL is not 0.0
                if position.type == mt5.ORDER_TYPE_BUY:
                    if sl_to_check >= current_price:
                        # SL too close or above current price - adjust
                        safe_distance = self.get_current_spread(symbol) * 2  # Double spread
                        new_sl = current_price - (safe_distance * pip_size)
                        logger.warning(f"SL {sl_to_check} too high for BUY, adjusting to {new_sl}")
                        request["sl"] = new_sl
                else:  # SELL
                    if sl_to_check <= current_price:
                        # SL too close or below current price - adjust
                        safe_distance = self.get_current_spread(symbol) * 2  # Double spread
                        new_sl = current_price + (safe_distance * pip_size)
                        logger.warning(f"SL {sl_to_check} too low for SELL, adjusting to {new_sl}")
                        request["sl"] = new_sl
            
            # Validate TP
            tp_to_check = request["tp"]
            if tp_to_check != 0.0:  # Only validate if TP is not 0.0
                if position.type == mt5.ORDER_TYPE_BUY:
                    if tp_to_check <= current_price:
                        # TP below current price - adjust
                        safe_distance = self.get_current_spread(symbol) * 2  # Double spread
                        new_tp = current_price + (safe_distance * pip_size)
                        logger.warning(f"TP {tp_to_check} too low for BUY, adjusting to {new_tp}")
                        request["tp"] = new_tp
                else:  # SELL
                    if tp_to_check >= current_price:
                        # TP above current price - adjust
                        safe_distance = self.get_current_spread(symbol) * 2  # Double spread
                        new_tp = current_price - (safe_distance * pip_size)
                        logger.warning(f"TP {tp_to_check} too high for SELL, adjusting to {new_tp}")
                        request["tp"] = new_tp
            
            # Check if values are actually different
            current_sl = position.sl if position.sl is not None else 0.0
            current_tp = position.tp if position.tp is not None else 0.0
            
            sl_diff = abs(request["sl"] - current_sl)
            tp_diff = abs(request["tp"] - current_tp)
            
            if sl_diff < 0.00001 and tp_diff < 0.00001:
                return False, "10025 - No changes"
            
            # Send request
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return True, "Success"
            else:
                error_msg = f"{result.retcode} - {result.comment}"
                logger.error(f"❌ FAILED: Position {ticket}: {error_msg}")
                
                # If failed due to invalid stops, try emergency fix
                if "Invalid stops" in error_msg or "10027" in error_msg:
                    logger.warning(f"Attempting emergency fix for position {ticket}")
                    return self._emergency_fix(position, sl, tp)
                
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error modifying position {ticket}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _emergency_fix(self, position, sl, tp) -> Tuple[bool, str]:
        """Emergency fix for invalid stops"""
        try:
            current_price = position.price_current
            symbol = position.symbol
            pip_size = 0.0001 if symbol.find("JPY") == -1 else 0.01
            
            # Get current spread
            spread = self.get_current_spread(symbol)
            
            # Build emergency request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": position.ticket,
                "symbol": symbol,
                "magic": position.magic,
                "comment": "Emergency SL/TP Fix"
            }
            
            # Emergency SL calculation with safe distance
            if position.type == mt5.ORDER_TYPE_BUY:
                # BUY: SL below current price with spread buffer
                safe_distance = max(10, spread * 3)  # At least 10 pips or 3x spread
                emergency_sl = current_price - (safe_distance * pip_size)
                request["sl"] = emergency_sl
            else:
                # SELL: SL above current price with spread buffer
                safe_distance = max(10, spread * 3)  # At least 10 pips or 3x spread
                emergency_sl = current_price + (safe_distance * pip_size)
                request["sl"] = emergency_sl
            
            # Emergency TP handling
            if tp is not None and tp != 0.0:
                if position.type == mt5.ORDER_TYPE_BUY and tp > current_price:
                    request["tp"] = tp
                elif position.type == mt5.ORDER_TYPE_SELL and tp < current_price:
                    request["tp"] = tp
                else:
                    # TP is invalid, remove it
                    request["tp"] = 0.0
            else:
                request["tp"] = position.tp if position.tp is not None else 0.0
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ EMERGENCY FIX SUCCESS: Position {position.ticket}")
                return True, "Emergency fix successful"
            else:
                return False, f"Emergency fix failed: {result.retcode} - {result.comment}"
                
        except Exception as e:
            return False, f"Emergency fix error: {str(e)}"