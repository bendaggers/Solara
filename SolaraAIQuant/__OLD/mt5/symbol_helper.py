"""
mt5/symbol_helper.py — Symbol Utilities
=========================================
Pip sizes, minimum stop distances, and lot step info per symbol.
"""
import structlog

log = structlog.get_logger(__name__)

# Symbols with 3 decimal places (JPY pairs, etc.)
JPY_SYMBOLS = {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY"}
# Gold has its own pip convention
GOLD_SYMBOLS = {"XAUUSD", "GOLD"}


def get_pip_size(symbol: str, point: float) -> float:
    """
    Return pip size for a symbol based on its point value.
    Most pairs: 1 pip = 0.00010 (point * 10)
    JPY pairs:  1 pip = 0.01000 (point * 100 where point = 0.001)
    Gold:       1 pip = 0.10000 (point * 10 where point = 0.01)
    """
    symbol_upper = symbol.upper()
    if any(s in symbol_upper for s in JPY_SYMBOLS):
        return point * 100
    if any(s in symbol_upper for s in GOLD_SYMBOLS):
        return point * 10
    return point * 10


def pips_to_price(symbol: str, pips: float, point: float) -> float:
    """Convert a pip distance to a price distance."""
    return pips * get_pip_size(symbol, point)


def price_to_pips(symbol: str, price_distance: float, point: float) -> float:
    """Convert a price distance to pips."""
    pip = get_pip_size(symbol, point)
    if pip == 0:
        return 0.0
    return price_distance / pip
