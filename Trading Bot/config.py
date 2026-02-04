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
import sys


# Add credentials folder to Python path
current_dir = os.path.dirname(__file__)
credentials_dir = os.path.join(current_dir, 'credentials')
sys.path.insert(0, credentials_dir)

# Now import directly from the file
import mt5_credentials


# ================== MT5 CONNECTION ==================
MT5_LOGIN = mt5_credentials.MT5_LOGIN
MT5_PASSWORD = mt5_credentials.MT5_PASSWORD
MT5_SERVER = mt5_credentials.MT5_SERVER

# ================== PATHS ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# The EA saves files to the terminal's MQL5/Files directory
TERMINAL_PATH = r"C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
#
# WATCHED MARKET DATA FILE
PERIOD = "M5"
MARKET_DATA_FILE = f"marketdata_PERIOD_{PERIOD}.csv"
DATA_PATH = os.path.join(TERMINAL_PATH, "MQL5", "Files", MARKET_DATA_FILE)
# 
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # 


# Models are in the Solara project folder
# Based on your BASE_DIR: C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Trading Bot
# Models folder: C:\Users\Ben Michael Oracion\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\Advisors\Solara\Models

# Go up one level from Trading Bot to Solara folder, then into Models
SOLARA_ROOT = os.path.dirname(BASE_DIR)
MODELS_PATH = os.path.join(SOLARA_ROOT, "Models")


# ================== TRADING SETTINGS ==================
TIMEFRAME = "H4"
LOT_SIZE = 0.02
STOP_LOSS_PIPS = 30
TAKE_PROFIT_PIPS = 40
SLIPPAGE = 10


# ================== RISK MANAGEMENT ==================
MAX_RISK_PER_TRADE = 0.02                 # 2% risk per trade
MAX_DAILY_TRADES = 999                      # Max trades per day
STOP_LOSS_PIPS = 30                       # Default stop loss in pips
TAKE_PROFIT_PIPS = 40                    # Default take profit in pips

# ================== FILE PATHS ==================
QUALIFIED_PAIRS_PATH = os.path.join(BASE_DIR, "qualified_pairs.json")
LOG_PATH = os.path.join(BASE_DIR, "logs/trading.log")

# ================== PREDICTOR CONFIGURATION ==================
# Define all available predictors here
PREDICTOR_CONFIGS = [
    {
        # REMOVE THIS & MODIFY - Temporary! 
        'name': 'Bollinger Band Long Reversal', # CHANGE THIS
        'class_path': 'predictors.bb_reversal_short_predictor.BBReversalShortPredictor', # CHANGE THIS
        'model_file': "BB_SHORT_REVERSAL_Model_v2.pkl",# CHANGE THIS
        'model_type': "LONG", # CHANGE THIS
        'min_confidence': .40, # CHANGE THIS
        'min_signal_strength': "Weak", # CHANGE THIS
        'enabled': True, 
        'weight': 1.0,
        'timeout': 30,
        'magic': 201000, # CHANGE THIS
        'comment': 'BBLongRev' # CHANGE THIS
        # REMOVE THIS - Temporary! 
    },
    {
        'name': 'Bollinger Band Short Reversal', # CHANGE THIS
        'class_path': 'predictors.bb_reversal_short_predictor.BBReversalShortPredictor', # CHANGE THIS
        'model_file': "BB_SHORT_REVERSAL_Model_v2.pkl", # CHANGE THIS
        'model_type': "SHORT", # CHANGE THIS
        'min_confidence': .20, # CHANGE THIS
        'min_signal_strength': "Weak", # CHANGE THIS
        'enabled': True, # CHANGE THIS
        'weight': 1.0,
        'timeout': 30,
        'magic': 202000, # CHANGE THIS
        'comment': 'BBShortRev' # CHANGE THIS
    },

]

# Get only enabled predictors
ENABLED_PREDICTORS = [p for p in PREDICTOR_CONFIGS if p['enabled']]

# ================== SYMBOL-SPECIFIC SETTINGS ==================
# Pip sizes (1 pip = ?)
PIP_SIZES = {
    "default": 0.0001,      # Most Forex
    "JPY": 0.01,           # JPY pairs
    "XAU": 0.01,           # Gold
    "XAG": 0.01,           # Silver
    "OIL": 0.01,           # Oil
    "BTC": 1.0,            # Bitcoin
}

# Minimum required stop distances (in pips)
MIN_STOP_DISTANCES = {
    "default": 10,         # 10 pips for most Forex
    "JPY": 20,            # JPY pairs need more
    "XAU": 200,           # Gold needs 200 pips
    "XAG": 50,           # Silver needs 720 pips (!)
    "OIL": 150,           # Oil needs 150 pips
}

# Symbol type detection patterns
SYMBOL_PATTERNS = {
    "JPY": ["JPY"],        # Any symbol containing JPY
    "XAU": ["XAU", "GOLD"],
    "XAG": ["XAG", "SILVER"],
    "OIL": ["OIL", "WTI", "BRENT", "USOIL", "UKOIL"],
    "BTC": ["BTC"],
    "ETH": ["ETH"],
    "INDICES": ["US30", "NAS100", "SPX500", "DAX", "FTSE", "NIKKEI"],
}



# Add to config.py (at the end):
def get_data_path(use_temp=None):
    """
    Get the data path to use.
    If use_temp is provided and exists, use that temp file.
    Otherwise, use the default DATA_PATH.
    """
    import os
    if use_temp and os.path.exists(use_temp):
        return use_temp
    return DATA_PATH


def get_predictor_class(class_path):
    """
    Dynamically import and return a predictor class from its path.
    Example: 'predictors.bb_reversal_long_predictor.BBReversalLongPredictor'
    """
    try:
        module_path, class_name = class_path.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        predictor_class = getattr(module, class_name)
        return predictor_class
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Failed to import predictor class '{class_path}': {str(e)}")