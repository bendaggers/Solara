"""
Trade Executor - The Action Taker

If the predictor is the advisor saying "we should buy," the executor is the 
trader who actually places the order. This module connects directly to your 
MT5 terminal, checking current prices, calculating stop losses, and sending 
the trade requests. But it's not reckless - it first checks market conditions 
like spreads and trading hours, ensures you're not risking too much, and 
keeps detailed records of every action. After placing trades, it writes a 
'flight recorder' log so you can always review what happened. It transforms 
predictions into actual market positions with careful risk management, 
turning theoretical opportunities into real executed trades.
"""

import MetaTrader5 as mt5
import json
import time
from datetime import datetime
import config


class TradeExecutor:
    """Handles MT5 connection and trade execution"""
    
    def __init__(self, login, password, server):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
    
    def connect(self):
        """Connect to MT5 terminal"""
        if not mt5.initialize():
            raise Exception(f"MT5 initialization failed: {mt5.last_error()}")
        
        authorized = mt5.login(
            login=self.login,
            password=self.password,
            server=self.server
        )
        
        if not authorized:
            raise Exception(f"MT5 login failed: {mt5.last_error()}")
        
        self.connected = True
        print(f"✅ Connected to MT5 account {self.login}")
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("✅ Disconnected from MT5")
    
    def execute_trades(self, predictions):
        """
        Execute trades based on predictions
        Args:
            predictions: dict from LongPredictor
        """
        if not self.connected:
            raise Exception("Not connected to MT5")
        
        executed_trades = []
        
        for symbol, pred_data in predictions.items():
            # Check if symbol is in our trading list
            if symbol not in config.SYMBOLS:
                print(f"⚠️ Skipping {symbol} - not in trading list")
                continue
            
            # Check market conditions
            if not self.check_market_conditions(symbol):
                print(f"⚠️ Market conditions not favorable for {symbol}")
                continue
            
            # Execute trade based on prediction
            try:
                if pred_data['prediction'] == 1:  # BUY signal
                    trade_result = self.execute_buy(symbol, pred_data)
                else:  # SELL signal
                    trade_result = self.execute_sell(symbol, pred_data)
                
                if trade_result:
                    executed_trades.append({
                        'symbol': symbol,
                        'result': trade_result._asdict(),
                        'prediction': pred_data
                    })
                    print(f"✅ Trade executed for {symbol}")
            
            except Exception as e:
                print(f"❌ Trade execution failed for {symbol}: {str(e)}")
        
        # Save qualified pairs as backup
        self.save_qualified_pairs(predictions)
        
        # Save trade history
        self.save_trade_history(executed_trades)
        
        return executed_trades
    
    def execute_buy(self, symbol, pred_data):
        """Execute a BUY order"""
        price = mt5.symbol_info_tick(symbol).ask
        
        # Calculate stop loss and take profit
        sl = price - config.STOP_LOSS_PIPS * 0.0001
        tp = price + config.TAKE_PROFIT_PIPS * 0.0001
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": config.LOT_SIZE,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": config.SLIPPAGE,
            "magic": 234000,
            "comment": f"Solara_Buy_{pred_data['confidence']:.2f}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        return result
    
    def execute_sell(self, symbol, pred_data):
        """Execute a SELL order"""
        price = mt5.symbol_info_tick(symbol).bid
        
        # Calculate stop loss and take profit
        sl = price + config.STOP_LOSS_PIPS * 0.0001
        tp = price - config.TAKE_PROFIT_PIPS * 0.0001
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": config.LOT_SIZE,
            "type": mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": config.SLIPPAGE,
            "magic": 234000,
            "comment": f"Solara_Sell_{pred_data['confidence']:.2f}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        return result
    
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
            spread = (tick.ask - tick.bid) * 10000  # Convert to pips
            if spread > config.MAX_SPREAD:
                print(f"⚠️ Spread too high for {symbol}: {spread:.1f} pips")
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