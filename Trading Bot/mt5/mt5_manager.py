"""
MT5 Manager - Handles MetaTrader 5 connection and trading operations
Clean version without Bollinger Bands
"""

import MetaTrader5 as mt5
import time
import config
from .symbol_helper import SymbolHelper


# ================== MT5 MANAGER CLASS ==================
class MT5Manager:
    """Handles MT5 connection, trading, and account management"""
    
    def __init__(self, login, password, server):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.max_retries = 3
        self.retry_delay = 2
        self.account_info = None
        
        # Performance optimization for batch trading
        self.symbol_cache = {}
    
    def connect(self):
        """Connect to MT5 terminal with retries - returns self for chaining"""
        for attempt in range(self.max_retries):
            try:
                print(f"Connecting to MT5 (attempt {attempt + 1}/{self.max_retries})...")
                
                if not mt5.initialize():
                    error = mt5.last_error()
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        print(f"MT5 initialization failed: {error}")
                        self.connected = False
                        return self
                
                authorized = mt5.login(
                    login=self.login,
                    password=self.password,
                    server=self.server
                )
                
                if not authorized:
                    error = mt5.last_error()
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        print(f"MT5 login failed: {error}")
                        self.connected = False
                        return self
                
                self.connected = True
                self.account_info = mt5.account_info()
                print(f"✅ Connected to MT5 - Account: {self.account_info.login}")
                return self  # Return self for chaining
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    print(f"Failed to connect to MT5: {str(e)}")
        
        self.connected = False
        return self
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            self.symbol_cache.clear()  # Clear cache on disconnect
            print("\n🔌 Disconnected from MT5")
    
    def get_account_info(self):
        """Get account information"""
        if self.connected:
            return self.account_info or mt5.account_info()
        return None
    
    def get_balance(self):
        """Get account balance"""
        if self.connected:
            info = self.get_account_info()
            return info.balance if info else 0
        return 0
    
    def get_equity(self):
        """Get account equity"""
        if self.connected:
            info = self.get_account_info()
            return info.equity if info else 0
        return 0

    def execute_trades(self, predictions):

        """One method that does everything - handles 1 to thousands of trades"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return []
        
        if not predictions:
            print("📭 No predictions")
            return []
        
        total_trades = len(predictions)
        
        executed_trades = []
        failed_trades = []
        
        print(f"💸 Executing {total_trades} trades...")
        
        for idx, (key, pred) in enumerate(predictions.items(), 1):
            # 1. Extract and validate
            symbol = pred.get('symbol', '')
            if not symbol:
                failed_trades.append({'key': key, 'reason': 'No symbol'})
                continue
            
            # 2. Map model_type to trade_type
            model_type = pred.get('model_type', 'LONG').upper()
            if model_type == 'SHORT':
                trade_type = 'SELL'
                emoji = "📉"
            elif model_type == 'LONG':
                trade_type = 'BUY'
                emoji = "📈"
            else:
                failed_trades.append({'key': key, 'reason': f'Unknown model type: {model_type}'})
                continue
            
            # 3. Get other params
            volume = pred.get('volume', config.LOT_SIZE)
            magic = pred.get('magic', 234000)
            comment = pred.get('comment', 'Trading Signal')
            confidence = pred.get('confidence', 0)
            
            try:
                # 4. Get symbol info
                symbol_info = self._get_symbol_info(symbol)
                if not symbol_info:
                    failed_trades.append({'key': key, 'reason': 'Symbol not found'})
                    continue
                
                # 5. Validate and adjust volume
                volume = self._validate_and_adjust_volume(symbol_info, volume)
                
                # 6. Ensure symbol is visible
                if not symbol_info.visible:
                    mt5.symbol_select(symbol, True)
                    time.sleep(0.05)
                
                # 7. Get current tick
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    failed_trades.append({'key': key, 'reason': 'No tick data'})
                    continue
                
                # 8. Determine prices
                is_buy = (trade_type == 'BUY')
                if is_buy:
                    entry_price = tick.ask
                    mt5_order_type = mt5.ORDER_TYPE_BUY
                    default_comment = comment or "LONG Signal"
                else:
                    entry_price = tick.bid
                    mt5_order_type = mt5.ORDER_TYPE_SELL
                    default_comment = comment or "SHORT Signal"
                
                # 9. Calculate SL and TP prices
                sl_price = round(SymbolHelper.calculate_sl_price(
                    entry_price, config.STOP_LOSS_PIPS, symbol, is_buy=is_buy
                ), 5)
                
                tp_price = round(SymbolHelper.calculate_tp_price(
                    entry_price, config.TAKE_PROFIT_PIPS, symbol, is_buy=is_buy
                ), 5)
                
                entry_price = round(entry_price, 5)
                
                # 10. Prepare trade request
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": mt5_order_type,
                    "price": entry_price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "deviation": config.SLIPPAGE,
                    "magic": magic,
                    "comment": default_comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                # 11. Send order
                result = mt5.order_send(request)
                
                # 12. Handle result
                if result is None:
                    error = mt5.last_error()
                    failed_trades.append({'key': key, 'reason': f'MT5 error: {error}'})
                    continue
                
                if hasattr(result, 'retcode'):
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        # Print simplified log format
                        print(f"{emoji} {symbol} ({volume}) - {comment}")
                        
                        executed_trades.append({
                            'symbol': symbol,
                            'trade_type': trade_type,
                            'model_type': model_type,
                            'magic': magic,
                            'volume': volume,
                            'comment': comment,
                            'confidence': confidence,
                            'result': 'SUCCESS',
                            'order_ticket': getattr(result, 'order', None),
                            'order_result': result,
                            'prediction_data': pred
                        })
                    else:
                        error_msg = getattr(result, 'comment', 'Unknown error')
                        
                        # Retry with larger stops if "invalid stops" error
                        if hasattr(result, 'comment') and "invalid stops" in str(result.comment).lower():
                            retry_result = self._retry_with_larger_stops(
                                symbol=symbol,
                                entry_price=entry_price,
                                is_buy=is_buy,
                                magic=magic,
                                comment=default_comment,
                                volume=volume
                            )
                            
                            if retry_result:
                                # Print simplified log format for retry success
                                print(f"{emoji} {symbol} ({volume}) - {comment}")
                                
                                executed_trades.append({
                                    'symbol': symbol,
                                    'trade_type': trade_type,
                                    'model_type': model_type,
                                    'magic': magic,
                                    'volume': volume,
                                    'comment': comment,
                                    'confidence': confidence,
                                    'result': 'SUCCESS_RETRY',
                                    'order_ticket': getattr(retry_result, 'order', None),
                                    'order_result': retry_result,
                                    'prediction_data': pred
                                })
                            else:
                                failed_trades.append({'key': key, 'reason': error_msg})
                        else:
                            failed_trades.append({'key': key, 'reason': error_msg})
                else:
                    failed_trades.append({'key': key, 'reason': 'No retcode in result'})
            
            except Exception as e:
                failed_trades.append({'key': key, 'reason': f'Exception: {str(e)}'})
                continue
            
            # Small delay between trades
            if idx < total_trades:
                time.sleep(0.1)
        
        # Print execution summary
        print(f"\n📊 Execution Summary:")
        print(f"   • Total predictions: {total_trades}")
        print(f"   • Successful: {len(executed_trades)}")
        print(f"   • Failed: {len(failed_trades)}")
        
        if failed_trades:
            print(f"\n⚠️ Failed trades (first 5):")
            for i, fail in enumerate(failed_trades[:5]):
                print(f"   {i+1}. {fail.get('key', 'Unknown')}: {fail.get('reason', 'Unknown')}")
            if len(failed_trades) > 5:
                print(f"   ... and {len(failed_trades) - 5} more")
        
        return executed_trades

    def _validate_and_adjust_volume(self, symbol_info, volume):
        """Validate volume against symbol constraints and adjust if needed"""
        try:
            original_volume = volume
            
            # Ensure minimum volume
            if volume < symbol_info.volume_min:
                print(f"    ⚠️ Volume {volume} below minimum {symbol_info.volume_min}, adjusting")
                volume = symbol_info.volume_min
            
            # Ensure maximum volume
            elif volume > symbol_info.volume_max:
                print(f"    ⚠️ Volume {volume} above maximum {symbol_info.volume_max}, adjusting")
                volume = symbol_info.volume_max
            
            # Round to nearest volume step
            if symbol_info.volume_step > 0:
                volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step
                if volume != original_volume:
                    print(f"    ⚠️ Volume rounded to {volume} (step: {symbol_info.volume_step})")
            
            return volume
            
        except Exception as e:
            print(f"    ⚠️ Volume validation error: {e}, using original: {volume}")
            return volume

    def _get_symbol_info(self, symbol):
        """Get symbol info with caching for performance"""
        if symbol in self.symbol_cache:
            return self.symbol_cache[symbol]
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info:
            self.symbol_cache[symbol] = symbol_info
        return symbol_info

    def _retry_with_larger_stops(self, symbol, entry_price, is_buy, magic, comment=None, volume=None):
        """Retry trade execution with progressively larger stop distances"""
        multipliers = [1.5, 2, 3, 5, 8, 12, 18, 25, 35, 50]
        
        trade_volume = volume or config.LOT_SIZE
        pip_size = SymbolHelper.get_pip_size(symbol)
        trade_type = "BUY" if is_buy else "SELL"
        
        for i, multiplier in enumerate(multipliers):
            larger_sl_pips = config.STOP_LOSS_PIPS * multiplier
            larger_tp_pips = config.TAKE_PROFIT_PIPS * multiplier
            
            # Calculate new SL/TP prices
            if is_buy:
                sl_price = round(entry_price - (larger_sl_pips * pip_size), 5)
                tp_price = round(entry_price + (larger_tp_pips * pip_size), 5)
                mt5_order_type = mt5.ORDER_TYPE_BUY
            else:
                sl_price = round(entry_price + (larger_sl_pips * pip_size), 5)
                tp_price = round(entry_price - (larger_tp_pips * pip_size), 5)
                mt5_order_type = mt5.ORDER_TYPE_SELL
            
            print(f"      └─ Retry {i+1}: SL={larger_sl_pips}pips, TP={larger_tp_pips}pips")
            
            # Prepare retry request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": trade_volume,
                "type": mt5_order_type,
                "price": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": config.SLIPPAGE,
                "magic": magic,
                "comment": comment or f"{trade_type} Signal (retry)",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result and hasattr(result, 'retcode') and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"    ✅ {trade_type} executed on retry #{i+1}")
                return result
            
            time.sleep(0.05)  # Shorter delay for retries
        
        print(f"    ❌ All retry attempts failed")
        return None
    
    def get_open_positions(self, symbol=None):
        """Get all open positions or filter by symbol - returns list of dicts"""
        if not self.connected:
            return []
        
        try:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()
            
            if positions is None:
                return []
            
            # Convert tuple of TradePosition objects to list of dictionaries
            position_list = []
            for position in positions:
                pos_dict = {
                    'ticket': position.ticket,
                    'symbol': position.symbol,
                    'type': 'BUY' if position.type == 0 else 'SELL',
                    'type_code': position.type,
                    'magic': position.magic,
                    'volume': position.volume,
                    'entry_price': position.price_open,
                    'sl': position.sl,
                    'tp': position.tp,
                    'current_price': position.price_current,
                    'swap': position.swap,
                    'profit': position.profit,
                    'comment': position.comment,
                }
                position_list.append(pos_dict)
            
            return position_list
            
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []
    
    def get_symbol_info(self, symbol):
        """Get detailed information about a symbol"""
        if not self.connected:
            return None
        
        info = mt5.symbol_info(symbol)
        if info:
            return {
                'symbol': info.name,
                'bid': info.bid,
                'ask': info.ask,
                'spread': info.ask - info.bid,
                'trade_mode': info.trade_mode,
                'trade_allowed': info.trade_allowed,
                'margin_initial': info.margin_initial,
                'margin_maintenance': info.margin_maintenance,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step,
            }
        return None

    def modify_position(self, ticket, sl=None, tp=None, silent=False):
        """
        Modify an existing position's stop loss and/or take profit
        
        Args:
            ticket (int): Position ticket number
            sl (float, optional): New stop loss price
            tp (float, optional): New take profit price
            silent (bool): If True, don't print individual modification logs
            
        Returns:
            bool: True if modification was successful, False otherwise
        """
        if not self.connected:
            if not silent:
                print(f"❌ Cannot modify position - MT5 not connected")
            return False
        
        try:
            # Get the position by ticket
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                if not silent:
                    print(f"❌ Position #{ticket} not found")
                return False
            
            position = positions[0]
            symbol = position.symbol
            
            if not silent:
                print(f"🔄 Modifying position #{ticket} ({symbol})")
            
            # Prepare modification request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": ticket,
                "sl": float(sl) if sl is not None else float(position.sl),
                "tp": float(tp) if tp is not None else float(position.tp),
                "magic": position.magic,
                "comment": position.comment,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            
            # Send modification request
            result = mt5.order_send(request)
            
            if result is None:
                error = mt5.last_error()
                if not silent:
                    print(f"❌ Modification failed for #{ticket}: {error}")
                return False
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                if not silent:
                    print(f"✅ Modified position #{ticket}: SL={sl or 'unchanged'}, TP={tp or 'unchanged'}")
                return True
            else:
                if not silent:
                    print(f"❌ Modification rejected for #{ticket}: {result.comment}")
                return False
                
        except Exception as e:
            if not silent:
                print(f"❌ Error modifying position #{ticket}: {str(e)}")
            return False