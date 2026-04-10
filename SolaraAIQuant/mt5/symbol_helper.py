"""
Solara AI Quant - Symbol Helper

Utilities for symbol-specific calculations (pip value, lot sizing, etc.)
"""

import logging
from typing import Optional
from dataclasses import dataclass

from .mt5_manager import mt5_manager, MT5SymbolInfo

logger = logging.getLogger(__name__)


@dataclass
class PipInfo:
    """Pip calculation info for a symbol."""
    symbol: str
    pip_size: float      # Size of 1 pip (e.g., 0.0001 for EURUSD)
    pip_value: float     # Value of 1 pip per lot in account currency
    digits: int          # Price digits


class SymbolHelper:
    """
    Helper for symbol-specific calculations.
    
    Handles:
    - Pip size detection (JPY pairs, metals, etc.)
    - Pip value calculation
    - Lot size calculation for risk %
    """
    
    # Special pip sizes
    JPY_PAIRS = {'JPY', 'XJP'}
    METALS = {'XAU', 'XAG', 'GOLD', 'SILVER'}
    INDICES = {'US30', 'US500', 'NAS100', 'GER40', 'UK100'}
    
    def __init__(self):
        self._pip_cache: dict = {}
    
    def get_pip_size(self, symbol: str) -> float:
        """
        Get pip size for a symbol.
        
        Standard forex: 0.0001
        JPY pairs: 0.01
        Gold: 0.01 or 0.1
        """
        symbol_upper = symbol.upper()
        
        # JPY pairs
        if any(jpy in symbol_upper for jpy in self.JPY_PAIRS):
            return 0.01
        
        # Metals (Gold usually 0.1, Silver 0.001)
        if 'XAU' in symbol_upper or 'GOLD' in symbol_upper:
            return 0.1
        if 'XAG' in symbol_upper or 'SILVER' in symbol_upper:
            return 0.01
        
        # Indices (varies, default to point)
        if any(idx in symbol_upper for idx in self.INDICES):
            info = mt5_manager.get_symbol_info(symbol)
            if info:
                return info.point * 10  # Usually 10 points = 1 index pip
            return 1.0
        
        # Standard forex
        return 0.0001
    
    def get_pip_info(self, symbol: str) -> Optional[PipInfo]:
        """
        Get complete pip information for a symbol.
        
        Returns:
            PipInfo with pip size, value, and digits
        """
        # Check cache
        if symbol in self._pip_cache:
            return self._pip_cache[symbol]
        
        # Get symbol info from MT5
        info = mt5_manager.get_symbol_info(symbol)
        if info is None:
            logger.warning(f"Cannot get symbol info for {symbol}")
            # Return estimate based on symbol name
            pip_size = self.get_pip_size(symbol)
            return PipInfo(
                symbol=symbol,
                pip_size=pip_size,
                pip_value=10.0,  # Default estimate
                digits=5 if pip_size == 0.0001 else 3
            )
        
        pip_size = self.get_pip_size(symbol)
        
        # Calculate pip value per lot
        # pip_value = tick_value * (pip_size / tick_size)
        if info.trade_tick_size > 0:
            pip_value = info.trade_tick_value * (pip_size / info.trade_tick_size)
        else:
            pip_value = 10.0  # Default fallback
        
        pip_info = PipInfo(
            symbol=symbol,
            pip_size=pip_size,
            pip_value=pip_value,
            digits=info.digits
        )
        
        # Cache it
        self._pip_cache[symbol] = pip_info
        
        return pip_info
    
    def calculate_lot_size(
        self,
        symbol: str,
        risk_amount: float,
        sl_pips: float
    ) -> float:
        """
        Calculate lot size for a given risk amount and stop loss.
        
        Args:
            symbol: Symbol name
            risk_amount: Maximum risk in account currency
            sl_pips: Stop loss distance in pips
            
        Returns:
            Lot size (rounded to broker's step)
        """
        if sl_pips <= 0:
            logger.error("SL pips must be positive")
            return 0.0
        
        pip_info = self.get_pip_info(symbol)
        if pip_info is None:
            return 0.0
        
        # lot_size = risk_amount / (sl_pips * pip_value)
        lot_size = risk_amount / (sl_pips * pip_info.pip_value)
        
        # Round to broker's lot step
        info = mt5_manager.get_symbol_info(symbol)
        if info:
            step = info.volume_step
            lot_size = round(lot_size / step) * step
            
            # Clamp to min/max
            lot_size = max(info.volume_min, min(info.volume_max, lot_size))
        else:
            # Default rounding
            lot_size = round(lot_size, 2)
            lot_size = max(0.01, min(10.0, lot_size))
        
        return lot_size
    
    def pips_to_price(self, symbol: str, pips: float) -> float:
        """
        Convert pips to price difference.
        
        Args:
            symbol: Symbol name
            pips: Number of pips
            
        Returns:
            Price difference
        """
        pip_info = self.get_pip_info(symbol)
        if pip_info is None:
            return pips * 0.0001  # Default
        
        return pips * pip_info.pip_size
    
    def price_to_pips(self, symbol: str, price_diff: float) -> float:
        """
        Convert price difference to pips.
        
        Args:
            symbol: Symbol name
            price_diff: Price difference
            
        Returns:
            Number of pips
        """
        pip_info = self.get_pip_info(symbol)
        if pip_info is None:
            return price_diff / 0.0001  # Default
        
        return price_diff / pip_info.pip_size


# Global instance
symbol_helper = SymbolHelper()
