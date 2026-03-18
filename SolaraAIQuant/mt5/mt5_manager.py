"""
Solara AI Quant - MT5 Connection Manager

Thread-safe MT5 connection handling with automatic reconnection.
"""

import threading
import time
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import logging

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None

from config import mt5_config, IS_WINDOWS

logger = logging.getLogger(__name__)


@dataclass
class MT5AccountInfo:
    """MT5 account information snapshot."""
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    leverage: int
    currency: str
    company: str
    connected_at: datetime


@dataclass
class MT5SymbolInfo:
    """Symbol information."""
    name: str
    point: float
    digits: int
    spread: int
    volume_min: float
    volume_max: float
    volume_step: float
    trade_contract_size: float
    trade_tick_value: float
    trade_tick_size: float
    currency_base: str
    currency_profit: str


class MT5Manager:
    """
    Thread-safe MT5 connection manager.
    
    Provides:
    - Singleton connection management
    - Automatic reconnection
    - Thread-safe operations
    - Account and symbol info caching
    """
    
    _instance: Optional['MT5Manager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize MT5 manager."""
        if self._initialized:
            return
        
        self._connection_lock = threading.Lock()
        self._connected = False
        self._account_info: Optional[MT5AccountInfo] = None
        self._symbol_cache: Dict[str, MT5SymbolInfo] = {}
        self._initial_equity: Optional[float] = None
        self._initialized = True
        
        logger.info("MT5Manager initialized")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to MT5."""
        return self._connected and mt5 is not None and mt5.terminal_info() is not None
    
    def connect(self) -> bool:
        """
        Connect to MT5 terminal.
        
        Returns:
            True if connection successful
        """
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 package not installed")
            return False
        
        if not IS_WINDOWS:
            logger.error("MT5 only available on Windows")
            return False
        
        with self._connection_lock:
            # Check if already connected
            if self.is_connected:
                logger.debug("Already connected to MT5")
                return True
            
            # Initialize MT5
            logger.info("Connecting to MT5...")
            
            init_params = {
                'path': str(mt5_config.terminal_path) if mt5_config.terminal_path else None,
                'login': mt5_config.login,
                'password': mt5_config.password,
                'server': mt5_config.server,
                'timeout': mt5_config.timeout,
                'portable': mt5_config.portable
            }
            
            # Remove None values
            init_params = {k: v for k, v in init_params.items() if v is not None}
            
            if not mt5.initialize(**init_params):
                error = mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                return False
            
            # Verify connection
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                logger.error("Failed to get terminal info after initialization")
                mt5.shutdown()
                return False
            
            # Get account info
            account = mt5.account_info()
            if account is None:
                logger.error("Failed to get account info")
                mt5.shutdown()
                return False
            
            # Store account info
            self._account_info = MT5AccountInfo(
                login=account.login,
                server=account.server,
                balance=account.balance,
                equity=account.equity,
                margin=account.margin,
                free_margin=account.margin_free,
                margin_level=account.margin_level,
                leverage=account.leverage,
                currency=account.currency,
                company=account.company,
                connected_at=datetime.now()
            )
            
            # Store initial equity for drawdown calculation
            self._initial_equity = account.equity
            
            self._connected = True
            
            logger.info(f"Connected to MT5: {account.server}")
            logger.info(f"Account: {account.login} | Balance: {account.balance} {account.currency}")
            logger.info(f"Leverage: 1:{account.leverage}")
            
            return True
    
    def disconnect(self):
        """Disconnect from MT5."""
        with self._connection_lock:
            if mt5 is not None:
                mt5.shutdown()
            self._connected = False
            self._account_info = None
            logger.info("Disconnected from MT5")
    
    def ensure_connected(self) -> bool:
        """
        Ensure connection is active, reconnect if needed.
        
        Returns:
            True if connected (or reconnected successfully)
        """
        if self.is_connected:
            return True
        
        logger.warning("MT5 connection lost, attempting reconnection...")
        return self.connect()
    
    def get_account_info(self, refresh: bool = False) -> Optional[MT5AccountInfo]:
        """
        Get account information.
        
        Args:
            refresh: Force refresh from MT5
            
        Returns:
            MT5AccountInfo or None if not connected
        """
        if not self.ensure_connected():
            return None
        
        if refresh or self._account_info is None:
            account = mt5.account_info()
            if account is None:
                return None
            
            self._account_info = MT5AccountInfo(
                login=account.login,
                server=account.server,
                balance=account.balance,
                equity=account.equity,
                margin=account.margin,
                free_margin=account.margin_free,
                margin_level=account.margin_level,
                leverage=account.leverage,
                currency=account.currency,
                company=account.company,
                connected_at=datetime.now()
            )
        
        return self._account_info
    
    def get_equity(self) -> Optional[float]:
        """Get current equity."""
        info = self.get_account_info(refresh=True)
        return info.equity if info else None
    
    def get_free_margin(self) -> Optional[float]:
        """Get free margin."""
        info = self.get_account_info(refresh=True)
        return info.free_margin if info else None
    
    def get_initial_equity(self) -> Optional[float]:
        """Get initial equity (at connection time)."""
        return self._initial_equity
    
    def get_symbol_info(self, symbol: str, use_cache: bool = True) -> Optional[MT5SymbolInfo]:
        """
        Get symbol information.
        
        Args:
            symbol: Symbol name (e.g., 'EURUSD')
            use_cache: Use cached info if available
            
        Returns:
            MT5SymbolInfo or None
        """
        if not self.ensure_connected():
            return None
        
        # Check cache
        if use_cache and symbol in self._symbol_cache:
            return self._symbol_cache[symbol]
        
        # Get from MT5
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning(f"Symbol not found: {symbol}")
            return None
        
        symbol_info = MT5SymbolInfo(
            name=info.name,
            point=info.point,
            digits=info.digits,
            spread=info.spread,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            trade_contract_size=info.trade_contract_size,
            trade_tick_value=info.trade_tick_value,
            trade_tick_size=info.trade_tick_size,
            currency_base=info.currency_base,
            currency_profit=info.currency_profit
        )
        
        # Cache it
        self._symbol_cache[symbol] = symbol_info
        
        return symbol_info
    
    def get_positions(self, symbol: Optional[str] = None, magic: Optional[int] = None) -> List[Any]:
        """
        Get open positions.
        
        Args:
            symbol: Filter by symbol (optional)
            magic: Filter by magic number (optional)
            
        Returns:
            List of position objects
        """
        if not self.ensure_connected():
            return []
        
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()
        
        if positions is None:
            return []
        
        positions = list(positions)
        
        # Filter by magic if specified
        if magic is not None:
            positions = [p for p in positions if p.magic == magic]
        
        return positions
    
    def get_position_count(self, magic: Optional[int] = None) -> int:
        """Get count of open positions."""
        return len(self.get_positions(magic=magic))
    
    def get_today_trades_count(self, magic: Optional[int] = None) -> int:
        """
        Get count of trades executed today.
        
        Args:
            magic: Filter by magic number (optional)
            
        Returns:
            Number of trades today
        """
        if not self.ensure_connected():
            return 0
        
        # Get today's start
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get deals from today
        deals = mt5.history_deals_get(today, datetime.now())
        
        if deals is None:
            return 0
        
        deals = list(deals)
        
        # Filter entry deals only (not exits)
        entry_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
        
        # Filter by magic if specified
        if magic is not None:
            entry_deals = [d for d in entry_deals if d.magic == magic]
        
        return len(entry_deals)
    
    def place_order(
        self,
        symbol: str,
        order_type: int,
        volume: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        magic: int = 0,
        comment: str = ""
    ) -> Optional[Any]:
        """
        Place an order.
        
        Args:
            symbol: Symbol name
            order_type: MT5 order type (ORDER_TYPE_BUY, ORDER_TYPE_SELL, etc.)
            volume: Lot size
            price: Entry price (for pending orders)
            sl: Stop loss price
            tp: Take profit price
            magic: Magic number
            comment: Order comment
            
        Returns:
            OrderSendResult or None on failure
        """
        if not self.ensure_connected():
            return None
        
        # Get current price if not specified
        if price is None:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.error(f"Failed to get tick for {symbol}")
                return None
            
            if order_type == mt5.ORDER_TYPE_BUY:
                price = tick.ask
            else:
                price = tick.bid
        
        # Build request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 30,  # Max slippage in points
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if sl is not None:
            request["sl"] = sl
        if tp is not None:
            request["tp"] = tp
        
        # Send order
        result = mt5.order_send(request)
        
        if result is None:
            error = mt5.last_error()
            logger.error(f"Order send failed: {error}")
            return None
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order rejected: {result.retcode} - {result.comment}")
            return None
        
        logger.info(f"Order placed: {symbol} {volume} lots @ {price}, ticket={result.order}")
        
        return result
    
    def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> bool:
        """
        Modify an existing position's SL/TP.
        
        Args:
            ticket: Position ticket
            sl: New stop loss (or None to keep current)
            tp: New take profit (or None to keep current)
            
        Returns:
            True if successful
        """
        if not self.ensure_connected():
            return False
        
        # Get current position
        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.error(f"Position not found: {ticket}")
            return False
        
        position = position[0]
        
        # Build request
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": position.symbol,
        }
        
        if sl is not None:
            request["sl"] = sl
        else:
            request["sl"] = position.sl
        
        if tp is not None:
            request["tp"] = tp
        else:
            request["tp"] = position.tp
        
        # Send modification
        result = mt5.order_send(request)
        
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = mt5.last_error() if result is None else result.comment
            logger.error(f"Position modify failed: {error}")
            return False
        
        logger.debug(f"Position {ticket} modified: SL={sl}, TP={tp}")
        return True


# Global instance
mt5_manager = MT5Manager()
