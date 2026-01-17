# mt5_interface.py

import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Clear Message Dictionary
CLEAR_MESSAGES = {
    "modified_first_attempt": "Modified (first attempt accepted)",
    "modified_after_adjustments": "Modified after {} adjustment attempts",
    "already_optimal": "Already optimal - no modification",
    "mt5_rejected": "MT5 rejected: {}",
    "connection_error": "Not connected to MT5",
    "position_not_found": "Position {} not found",
    "max_attempts_reached": "Failed after {} adjustment attempts",
    "generic_error": "Error: {}"
}


class MT5Interface:
    """MT5 interface with brute-force incremental adjustment"""
    
    def __init__(self, login: int, password: str, server: str):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.spread_cache = {}
        
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
                pip_size = 0.0001 if symbol.find("JPY") == -1 else 0.01
                spread_pips = spread * pip_size * 10
                
                self.spread_cache[symbol] = spread_pips
                return spread_pips
        except:
            pass
        
        return 2.0
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        if not self.connected:
            logger.error(CLEAR_MESSAGES["connection_error"])
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
            
            logger.info(f"Found {len(positions_list)} open positions")
            return positions_list
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def modify_position(self, ticket: int, sl: float, tp: float) -> Tuple[bool, str]:
        """
        Modify position with brute-force 1-pip adjustment
        
        Process:
        1. Try original SL/TP
        2. If MT5 rejects, adjust 1 pip and retry
        3. Continue until MT5 accepts or max attempts reached
        4. Adjust SL away from current price, TP further in profit direction
        """
        if not self.connected:
            return False, CLEAR_MESSAGES["connection_error"]
        
        # Store original values
        original_sl = sl
        original_tp = tp
        
        try:
            # Get position info
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return False, CLEAR_MESSAGES["position_not_found"].format(ticket)
            
            position = position[0]
            symbol = position.symbol
            current_price = position.price_current
            
            # Check if position already has the same SL/TP
            if sl is not None and abs(position.sl - sl) < 0.00001:
                if tp is not None and abs(position.tp - tp) < 0.00001:
                    return True, CLEAR_MESSAGES["already_optimal"]
            
            # Get pip size
            pip_size = 0.0001 if symbol.find("JPY") == -1 else 0.01
            
            # Determine adjustment direction
            position_type = position.type  # 0=BUY, 1=SELL
            
            # Try up to 15 adjustments
            for attempt in range(16):  # 0 to 15 (16 attempts total)
                # Calculate adjusted values for this attempt
                adjusted_sl = None
                adjusted_tp = None
                
                # Adjust SL if provided
                if sl is not None:
                    adjusted_sl = self._adjust_value(
                        original_sl, position_type, current_price, 
                        pip_size, attempt, is_sl=True
                    )
                
                # Adjust TP if provided  
                if tp is not None:
                    adjusted_tp = self._adjust_value(
                        original_tp, position_type, current_price,
                        pip_size, attempt, is_sl=False
                    )
                
                # Build request
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "symbol": symbol,
                    "magic": position.magic,
                    "comment": f"Auto SL/TP - Attempt {attempt + 1}"
                }
                
                # Set SL/TP (use current if not changing)
                if adjusted_sl is not None:
                    request["sl"] = adjusted_sl
                else:
                    request["sl"] = position.sl if position.sl is not None else 0.0
                
                if adjusted_tp is not None:
                    request["tp"] = adjusted_tp
                else:
                    request["tp"] = position.tp if position.tp is not None else 0.0
                
                # Log attempt
                if attempt == 0:
                    logger.info(f"🔧 Attempting to modify position {ticket}: SL={original_sl}, TP={original_tp}")
                else:
                    sl_diff = (adjusted_sl - original_sl) / pip_size if adjusted_sl is not None else 0
                    tp_diff = (adjusted_tp - original_tp) / pip_size if adjusted_tp is not None else 0
                    logger.info(f"📐 Adjustment #{attempt}: SL={adjusted_sl} ({sl_diff:+} pips), TP={adjusted_tp} ({tp_diff:+} pips)")
                
                # Send request
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    if attempt == 0:
                        logger.info(f"✅ Position {ticket} modified successfully (no adjustment needed)")
                        return True, CLEAR_MESSAGES["modified_first_attempt"]
                    else:
                        logger.info(f"✅ Position {ticket} modified successfully after {attempt} pip adjustments")
                        return True, CLEAR_MESSAGES["modified_after_adjustments"].format(attempt)
                
                # Check if it's an invalid stops error
                error_msg = f"{result.retcode} - {result.comment}"
                
                if "Invalid stops" in error_msg or "10027" in error_msg:
                    # This is the error we expect - continue to next adjustment
                    logger.debug(f"Attempt {attempt + 1} failed: {error_msg}. Adjusting 1 pip...")
                    continue
                else:
                    # Some other error - bail out
                    logger.error(f"❌ Failed to modify position {ticket}: {error_msg}")
                    return False, CLEAR_MESSAGES["mt5_rejected"].format(error_msg)
            
            # If we get here, we've tried 16 times (0-15)
            logger.error(f"❌ Failed to modify position {ticket} after 16 attempts")
            return False, CLEAR_MESSAGES["max_attempts_reached"].format(16)
                
        except Exception as e:
            error_msg = f"Error modifying position {ticket}: {str(e)}"
            logger.error(f"❌ Exception: {error_msg}")
            return False, CLEAR_MESSAGES["generic_error"].format(error_msg)
    
    def _adjust_value(self, original_value: float, position_type: int, 
                     current_price: float, pip_size: float, 
                     attempt: int, is_sl: bool) -> float:
        """
        Adjust a value (SL or TP) by 1 pip per attempt
        
        Rules:
        - SL: Move AWAY from current price (safer)
        - TP: Move FURTHER in profit direction (more conservative)
        """
        adjustment_pips = attempt  # 1 pip per attempt
        
        if is_sl:
            # Stop Loss adjustment
            if position_type == 0:  # BUY
                # Move SL LOWER (further from current price)
                return original_value - (adjustment_pips * pip_size)
            else:  # SELL
                # Move SL HIGHER (further from current price)
                return original_value + (adjustment_pips * pip_size)
        else:
            # Take Profit adjustment
            if position_type == 0:  # BUY
                # Move TP HIGHER (further in profit direction)
                return original_value + (adjustment_pips * pip_size)
            else:  # SELL
                # Move TP LOWER (further in profit direction)
                return original_value - (adjustment_pips * pip_size)
    
    def brute_force_modify(self, ticket: int, sl: float, tp: float, max_attempts: int = 15) -> Tuple[bool, str]:
        """
        Alternative brute-force method with explicit max attempts
        
        Same logic as modify_position but with configurable attempts
        """
        if not self.connected:
            return False, CLEAR_MESSAGES["connection_error"]
        
        original_sl = sl
        original_tp = tp
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return False, CLEAR_MESSAGES["position_not_found"].format(ticket)
            
            position = position[0]
            symbol = position.symbol
            current_price = position.price_current
            pip_size = 0.0001 if symbol.find("JPY") == -1 else 0.01
            position_type = position.type
            
            # Check if position already has the same SL/TP
            if sl is not None and abs(position.sl - sl) < 0.00001:
                if tp is not None and abs(position.tp - tp) < 0.00001:
                    return True, CLEAR_MESSAGES["already_optimal"]
            
            for attempt in range(max_attempts + 1):  # +1 for original attempt
                # Calculate adjusted values
                adjusted_sl = sl
                adjusted_tp = tp
                
                if sl is not None:
                    adjusted_sl = self._adjust_value(sl, position_type, current_price, 
                                                   pip_size, attempt, is_sl=True)
                
                if tp is not None:
                    adjusted_tp = self._adjust_value(tp, position_type, current_price,
                                                   pip_size, attempt, is_sl=False)
                
                # Build request
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "symbol": symbol,
                    "magic": position.magic,
                    "sl": adjusted_sl if adjusted_sl is not None else 0.0,
                    "tp": adjusted_tp if adjusted_tp is not None else 0.0,
                    "comment": f"Brute force attempt {attempt}"
                }
                
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    if attempt == 0:
                        return True, CLEAR_MESSAGES["modified_first_attempt"]
                    else:
                        return True, CLEAR_MESSAGES["modified_after_adjustments"].format(attempt)
                
                # Only continue for invalid stops errors
                error_msg = f"{result.retcode} - {result.comment}"
                if not ("Invalid stops" in error_msg or "10027" in error_msg):
                    return False, CLEAR_MESSAGES["mt5_rejected"].format(error_msg)
            
            return False, CLEAR_MESSAGES["max_attempts_reached"].format(max_attempts)
            
        except Exception as e:
            return False, CLEAR_MESSAGES["generic_error"].format(str(e))
    
    def safe_modify_position(self, ticket: int, sl: float, tp: float) -> Tuple[bool, str]:
        """Wrapper for backward compatibility - calls the main modify_position method"""
        logger.info(f"🔧 safe_modify_position called for ticket {ticket}")
        return self.modify_position(ticket, sl, tp)