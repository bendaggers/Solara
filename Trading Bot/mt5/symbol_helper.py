import config

class SymbolHelper:
    """Helper class for symbol-specific calculations"""
    
    @staticmethod
    def detect_symbol_type(symbol):
        """Detect what type of symbol this is"""
        symbol_upper = symbol.upper()
        
        if "XAU" in symbol_upper or "GOLD" in symbol_upper:
            return "XAU"
        elif "XAG" in symbol_upper or "SILVER" in symbol_upper:
            return "XAG"
        elif any(oil in symbol_upper for oil in ["OIL", "WTI", "BRENT", "USOIL", "UKOIL"]):
            return "OIL"
        elif "JPY" in symbol_upper:
            return "JPY"
        elif any(index in symbol_upper for index in ["US30", "NAS100", "SPX500", "DAX", "FTSE", "NIKKEI"]):
            return "INDICES"
        elif any(crypto in symbol_upper for crypto in ["BTC", "ETH", "XRP", "LTC"]):
            return "CRYPTO"
        return "default"
    
    @staticmethod
    def get_pip_size(symbol):
        """Get pip size for a symbol"""
        symbol_type = SymbolHelper.detect_symbol_type(symbol)
        
        default_pip_sizes = {
            "default": 0.0001, "JPY": 0.01, "XAU": 0.01, "XAG": 0.01,
            "OIL": 0.01, "CRYPTO": 0.1, "INDICES": 1.0
        }
        
        if hasattr(config, 'PIP_SIZES'):
            return config.PIP_SIZES.get(symbol_type, config.PIP_SIZES.get("default", 0.0001))
        else:
            return default_pip_sizes.get(symbol_type, 0.0001)
    
    @staticmethod
    def get_min_stop_distance(symbol):
        """Get minimum stop distance for a symbol"""
        symbol_type = SymbolHelper.detect_symbol_type(symbol)
        
        default_min_stops = {
            "default": 10, "JPY": 20, "XAU": 50, "XAG": 50,
            "OIL": 80, "CRYPTO": 100, "INDICES": 30
        }
        
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
