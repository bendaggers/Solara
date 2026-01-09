"""
Trade Executor - The Action Taker
"""

import MetaTrader5 as mt5
import json
import time
from datetime import datetime
import config


# ================== SYMBOL HELPER CLASS ==================
class SymbolHelper:
    """Helper class for symbol-specific calculations"""
    
    @staticmethod
    def detect_symbol_type(symbol):
        """Detect what type of symbol this is"""
        symbol_upper = symbol.upper()
        
        # Check for metal symbols
        if "XAU" in symbol_upper or "GOLD" in symbol_upper:
            return "XAU"
        elif "XAG" in symbol_upper or "SILVER" in symbol_upper:
            return "XAG"
        
        # Check for oil symbols
        elif any(oil in symbol_upper for oil in ["OIL", "WTI", "BRENT", "USOIL", "UKOIL"]):
            return "OIL"
        
        # Check for JPY pairs
        elif "JPY" in symbol_upper:
            return "JPY"
        
        # Check for indices
        elif any(index in symbol_upper for index in ["US30", "NAS100", "SPX500", "DAX", "FTSE", "NIKKEI"]):
            return "INDICES"
        
        # Check for crypto
        elif any(crypto in symbol_upper for crypto in ["BTC", "ETH", "XRP", "LTC"]):
            return "CRYPTO"
        
        # Default to Forex
        return "default"
    
    @staticmethod
    def get_pip_size(symbol):
        """Get pip size for a symbol"""
        symbol_type = SymbolHelper.detect_symbol_type(symbol)
        
        # Default pip sizes
        default_pip_sizes = {
            "default": 0.0001,      # Most Forex (EURUSD, GBPUSD, etc.)
            "JPY": 0.01,           # JPY pairs (USDJPY, EURJPY, etc.)
            "XAU": 0.01,           # Gold (XAUUSD)
            "XAG": 0.01,           # Silver (XAGUSD)
            "OIL": 0.01,           # Oil (USOIL, UKOIL)
            "CRYPTO": 0.1,         # Crypto
            "INDICES": 1.0,        # Indices
        }
        
        # Try to get from config first, otherwise use defaults
        if hasattr(config, 'PIP_SIZES'):
            return config.PIP_SIZES.get(symbol_type, config.PIP_SIZES.get("default", 0.0001))
        else:
            return default_pip_sizes.get(symbol_type, 0.0001)
    
    @staticmethod
    def get_min_stop_distance(symbol):
        """Get minimum stop distance for a symbol"""
        symbol_type = SymbolHelper.detect_symbol_type(symbol)
        
        # Reasonable default minimum stops
        default_min_stops = {
            "default": 10,         # 10 pips for most Forex
            "JPY": 20,            # JPY pairs need more
            "XAU": 50,            # Gold needs 50 pips
            "XAG": 50,            # Silver needs 50 pips (not 720!)
            "OIL": 80,            # Oil needs 80 pips
            "CRYPTO": 100,        # Crypto needs 100 pips
            "INDICES": 30,        # Indices need 30 pips
        }
        
        # Try to get from config first, otherwise use defaults
        if hasattr(config, 'MIN_STOP_DISTANCES'):
            return config.MIN_STOP_DISTANCES.get(symbol_type, config.MIN_STOP_DISTANCES.get("default", 10))
        else:
            return default_min_stops.get(symbol_type, 10)
    
    @staticmethod
    def calculate_sl_price(entry_price, sl_pips, symbol, is_buy=True):
        """Calculate SL price correctly"""
        pip_size = SymbolHelper.get_pip_size(symbol)
        if is_buy:
            return entry_price - (sl_pips * pip_size)
        else:  # SELL
            return entry_price + (sl_pips * pip_size)
    
    @staticmethod
    def calculate_tp_price(entry_price, tp_pips, symbol, is_buy=True):
        """Calculate TP price correctly"""
        pip_size = SymbolHelper.get_pip_size(symbol)
        if is_buy:
            return entry_price + (tp_pips * pip_size)
        else:  # SELL
            return entry_price - (tp_pips * pip_size)
    
    @staticmethod
    def adjust_stops_for_symbol(symbol, sl_pips, tp_pips):
        """Adjust stops to meet broker minimum requirements"""
        min_distance = SymbolHelper.get_min_stop_distance(symbol)
        
        # If requested stops are less than minimum, use minimum
        if sl_pips < min_distance:
            print(f"⚠️ {symbol}: SL {sl_pips}pips < minimum {min_distance}pips. Adjusting...")
            sl_pips = min_distance
        
        # TP should be at least 80% of SL or minimum
        min_tp = max(tp_pips, min_distance * 0.8)
        if tp_pips < min_tp:
            print(f"⚠️ {symbol}: TP {tp_pips}pips < recommended {min_tp:.0f}pips. Adjusting...")
            tp_pips = min_tp
        
        return sl_pips, tp_pips


# ================== TRADE EXECUTOR CLASS ==================
class TradeExecutor:
    """Handles MT5 connection and trade execution"""
    
    def __init__(self, login, password, server):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def connect(self):
        """Connect to MT5 terminal with retries"""
        for attempt in range(self.max_retries):
            try:
                print(f"🔌 Attempting MT5 connection (Attempt {attempt + 1}/{self.max_retries})...")
                
                # Initialize MT5
                if not mt5.initialize():
                    error = mt5.last_error()
                    print(f"❌ MT5 initialization failed: {error}")
                    
                    if attempt < self.max_retries - 1:
                        print(f"⏳ Retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        raise Exception(f"MT5 initialization failed after {self.max_retries} attempts: {error}")
                
                # Login to MT5
                authorized = mt5.login(
                    login=self.login,
                    password=self.password,
                    server=self.server
                )
                
                if not authorized:
                    error = mt5.last_error()
                    print(f"❌ MT5 login failed: {error}")
                    
                    if attempt < self.max_retries - 1:
                        print(f"⏳ Retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        raise Exception(f"MT5 login failed after {self.max_retries} attempts: {error}")
                
                # Success!
                self.connected = True
                account_info = mt5.account_info()
                print(f"✅ Connected to MT5!")
                print(f"   Account: {account_info.login}")
                print(f"   Balance: ${account_info.balance:.2f}")
                print(f"   Server: {account_info.server}")
                return True
                
            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    print(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"❌ Failed to connect to MT5 after {self.max_retries} attempts: {str(e)}")
                    return False
        return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("✅ Disconnected from MT5")

    def execute_trades(self, predictions):
        """
        Execute trades based on predictions - CLEAN OUTPUT VERSION
        """
        if not self.connected:
            if not self.connect():
                print("❌ Cannot execute trades without MT5 connection")
                return []
        
        executed_trades = []
        
        print(f"\n💸 Executing {len(predictions)} trades...")
        
        for unique_key, pred_data in predictions.items():
            symbol = pred_data.get('symbol', '')
            if not symbol:
                continue
            
            # Only execute BUY trades
            if pred_data.get('prediction') == 1:
                try:
                    # Get confidence from prediction data
                    confidence = pred_data.get('confidence', 0.0)
                    
                    # Execute the trade
                    result = self.execute_buy(
                        symbol=symbol,
                        sl_pips=config.STOP_LOSS_PIPS,
                        tp_pips=config.TAKE_PROFIT_PIPS,
                        confidence=confidence
                    )
                    
                    # Check if trade was successful
                    if result is not None:
                        # Calculate the actual prices for display
                        symbol_info = mt5.symbol_info(symbol)
                        if symbol_info:
                            tick = mt5.symbol_info_tick(symbol)
                            if tick:
                                ask_price = tick.ask
                                pip_size = SymbolHelper.get_pip_size(symbol)
                                
                                # Calculate SL and TP prices
                                sl_price = round(ask_price - (config.STOP_LOSS_PIPS * pip_size), 5)
                                tp_price = round(ask_price + (config.TAKE_PROFIT_PIPS * pip_size), 5)
                                
                                # Clean display
                                if pip_size == 0.01:  # Metals, JPY
                                    sl_display = f"SL={sl_price:.3f}"
                                    tp_display = f"TP={tp_price:.3f}"
                                elif pip_size == 0.0001:  # Forex
                                    sl_display = f"SL={sl_price:.5f}"
                                    tp_display = f"TP={tp_price:.5f}"
                                else:
                                    sl_display = f"SL={sl_price}"
                                    tp_display = f"TP={tp_price}"
                                
                                print(f"  ✅ {symbol}: BUY executed - {sl_display} ({config.STOP_LOSS_PIPS}pips), {tp_display} ({config.TAKE_PROFIT_PIPS}pips)")
                        
                        executed_trades.append({
                            'symbol': symbol,
                            'result': 'SUCCESS',
                            'confidence': confidence,
                            'prediction': pred_data
                        })
                    else:
                        print(f"  ❌ {symbol}: Failed")
                
                except Exception as e:
                    print(f"  ❌ {symbol}: Error - {str(e)}")
        
        print(f"\n📊 Trade Summary:")
        print(f"   Successful: {len(executed_trades)} of {len(predictions)}")
        
        return executed_trades




    def execute_buy(self, symbol, sl_pips=None, tp_pips=None, confidence=0.0):
        """Execute buy with symbol-specific pip calculations - CLEAN VERSION"""
        try:
            # Use config values if not specified
            if sl_pips is None:
                sl_pips = config.STOP_LOSS_PIPS
            if tp_pips is None:
                tp_pips = config.TAKE_PROFIT_PIPS
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"❌ {symbol}: Symbol not found")
                return None
            
            # Detect symbol type and get pip size
            symbol_type = SymbolHelper.detect_symbol_type(symbol)
            pip_size = SymbolHelper.get_pip_size(symbol)
            
            # Don't automatically adjust stops
            # sl_pips, tp_pips = SymbolHelper.adjust_stops_for_symbol(symbol, sl_pips, tp_pips)
            
            # Ensure symbol is selected
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)
                time.sleep(0.1)
            
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"❌ {symbol}: Cannot get price")
                return None
            
            ask_price = tick.ask
            
            # Calculate SL and TP prices CORRECTLY and round them
            sl_price = round(SymbolHelper.calculate_sl_price(ask_price, sl_pips, symbol, is_buy=True), 5)
            tp_price = round(SymbolHelper.calculate_tp_price(ask_price, tp_pips, symbol, is_buy=True), 5)
            
            # Round ask price too
            ask_price = round(ask_price, 5)
            
            # Prepare trade request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": config.LOT_SIZE,
                "type": mt5.ORDER_TYPE_BUY,
                "price": ask_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": config.SLIPPAGE,
                "magic": 234000,
                "comment": f"{config.MODEL_NAME} - {confidence:.1%}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send trade request
            result = mt5.order_send(request)
            
            # Check result - CLEAN VERSION
            if result is None:
                last_error = mt5.last_error()
                if isinstance(last_error, tuple):
                    error_code, error_msg = last_error
                    if error_code == 0:  # 0 means NO ERROR (success!)
                        # Return success indicator
                        return "SUCCESS"
                    else:
                        print(f"❌ {symbol}: Failed - {error_msg}")
                        return None
                return None
            
            elif hasattr(result, 'retcode'):
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    # Return the result object for execute_trades to handle
                    return result
                else:
                    # If invalid stops, try progressive increase (silently)
                    if hasattr(result, 'comment') and "invalid stops" in str(result.comment).lower():
                        return self._retry_with_larger_stops(symbol, ask_price, sl_pips, tp_pips, 
                                                        symbol_type, pip_size, confidence)
                    print(f"❌ {symbol}: Rejected - Retcode: {result.retcode}")
                    return None
            else:
                # Unexpected result type
                return result
                        
        except Exception as e:
            print(f"❌ {symbol}: Error - {str(e)}")
            return None


    def _retry_with_larger_stops(self, symbol, entry_price, base_sl_pips, base_tp_pips, 
                                symbol_type, pip_size, confidence):
        """Retry with progressively larger stops - SILENT VERSION"""
        multipliers = [1.5, 2, 3, 5, 8, 12, 18, 25, 35, 50]
        
        for i, multiplier in enumerate(multipliers):
            sl_pips = base_sl_pips * multiplier
            tp_pips = base_tp_pips * multiplier
            
            # Calculate new prices
            sl_price = round(entry_price - (sl_pips * pip_size), 5)
            tp_price = round(entry_price + (tp_pips * pip_size), 5)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": config.LOT_SIZE,
                "type": mt5.ORDER_TYPE_BUY,
                "price": entry_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": config.SLIPPAGE,
                "magic": 234000,
                "comment": f"{config.MODEL_NAME} - {confidence:.1%}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result and hasattr(result, 'retcode') and result.retcode == mt5.TRADE_RETCODE_DONE:
                return result
            
            time.sleep(0.1)
        
        return None

    def execute_sell(self, symbol, sl_pips=None, tp_pips=None, comment=""):
        """Execute sell with symbol-specific pip calculations"""
        try:
            # Use config values if not specified
            if sl_pips is None:
                sl_pips = config.STOP_LOSS_PIPS
            if tp_pips is None:
                tp_pips = config.TAKE_PROFIT_PIPS
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"⚠️ Symbol {symbol} not found")
                return None
            
            # Detect symbol type
            symbol_type = SymbolHelper.detect_symbol_type(symbol)
            pip_size = SymbolHelper.get_pip_size(symbol)
            
            print(f"🔍 {symbol} identified as {symbol_type}")
            print(f"   1 pip = {pip_size}")
            
            # Ensure symbol is selected
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)
                time.sleep(0.5)
            
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"⚠️ Cannot get price for {symbol}")
                return None
            
            bid_price = tick.bid
            
            # Calculate SL and TP prices CORRECTLY for SELL
            sl_price = SymbolHelper.calculate_sl_price(bid_price, sl_pips, symbol, is_buy=False)
            tp_price = SymbolHelper.calculate_tp_price(bid_price, tp_pips, symbol, is_buy=False)
            
            # Calculate actual pip distances
            actual_sl_pips = (sl_price - bid_price) / pip_size
            actual_tp_pips = (bid_price - tp_price) / pip_size
            
            print(f"📊 {symbol}: Bid={bid_price}, SL={sl_price} ({actual_sl_pips:.1f}pips), TP={tp_price} ({actual_tp_pips:.1f}pips)")
            
            # Prepare trade request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": config.LOT_SIZE,
                "type": mt5.ORDER_TYPE_SELL,
                "price": bid_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": config.SLIPPAGE,
                "magic": 234000,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send trade request
            result = mt5.order_send(request)
            
            # Check result
            if result is None:
                error = mt5.last_error()
                print(f"❌ Request failed: {error}")
                return None
            
            elif result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"❌ Rejected - Retcode: {result.retcode}")
                print(f"   Comment: {result.comment}")
                return result
            
            else:
                print(f"✅ SELL executed successfully!")
                return result
                    
        except Exception as e:
            print(f"❌ Error executing SELL for {symbol}: {str(e)}")
            return None

    def check_market_conditions(self, symbol):
        """Check if market conditions are favorable for trading"""
        try:
            # Check if symbol exists
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                print(f"❌ Symbol {symbol} not found")
                return False
            
            # Check if symbol is selected
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)
            
            # Check spread
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return False
            
            # Check if market is open
            if not symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
                print(f"⚠️ Trading not allowed for {symbol}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Market check failed for {symbol}: {str(e)}")
            return False
    
    def save_qualified_pairs(self, predictions):
        """Save qualified pairs as JSON backup"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'timeframe': config.TIMEFRAME,
            'predictions': predictions
        }
        
        with open(config.QUALIFIED_PAIRS_PATH, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"💾 Saved qualified pairs to {config.QUALIFIED_PAIRS_PATH}")
    
    def save_trade_history(self, executed_trades):
        """Save trade execution history"""
        if executed_trades:
            history_file = f"trade_history_{datetime.now().strftime('%Y%m%d')}.json"
            with open(history_file, 'w') as f:
                json.dump(executed_trades, f, indent=2, default=str)
            
            print(f"💾 Trade history saved to {history_file}")