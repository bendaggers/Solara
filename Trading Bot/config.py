"""
Configuration - The Control Panel

This is your trading system's control panel - imagine it as the dashboard 
where you adjust all the settings before launch. Here you tell the system 
where to find your MT5 credentials, which currency pairs to monitor, how 
much risk to take per trade, and where all the important files are located. 
It's like setting up a navigation system before a journey: you input your 
destination, preferred route, and safety parameters, and the entire system 
follows these instructions. Changing values here lets you completely 
reconfigure how your bot behaves without touching any of the complex logic.
"""

import os

# ================== PATHS ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Adjust based on your EA output location (assuming MQL5 folder is at same level as Trading Bot)
DATA_PATH = os.path.join(os.path.dirname(BASE_DIR), "MQL5/Files/marketdata_H4.json")

# Models are in separate folder at same level as Trading Bot
MODELS_PATH = os.path.join(os.path.dirname(BASE_DIR), "Models")

# ================== MODEL FILE NAMES ==================
BB_REVERSAL_LONG_MODEL = "BB_LONG_REVERSAL_Model.pkl"

# ================== MT5 CONNECTION ==================
MT5_LOGIN = 12345678           # Your MT5 account number
MT5_PASSWORD = "your_password" # Your MT5 password
MT5_SERVER = "YourBrokerServer" # Your broker's server

# ================== TRADING SETTINGS ==================
SYMBOLS = ["EURUSD", "AUDUSD", "GBPUSD"]  # Symbols to trade
TIMEFRAME = "H4"                          # Trading timeframe
LOT_SIZE = 0.1                            # Default lot size
MAX_SPREAD = 20                           # Max spread in points
SLIPPAGE = 10                             # Allowed slippage in points

# ================== MODEL SETTINGS ==================
BB_REVERSAL_LONG_THRESHOLD = 0.7          # Confidence threshold for BB reversal long trades
MIN_CONFIDENCE = 0.6                      # Minimum confidence to take any trade

# ================== RISK MANAGEMENT ==================
MAX_RISK_PER_TRADE = 0.02                 # 2% risk per trade
MAX_DAILY_TRADES = 5                      # Max trades per day
STOP_LOSS_PIPS = 50                       # Default stop loss in pips
TAKE_PROFIT_PIPS = 100                    # Default take profit in pips

# ================== FILE PATHS ==================
QUALIFIED_PAIRS_PATH = os.path.join(BASE_DIR, "qualified_pairs.json")
LOG_PATH = os.path.join(BASE_DIR, "logs/trading.log")