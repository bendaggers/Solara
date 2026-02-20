"""
mt5/mt5_manager.py — MT5 Interface
=====================================
Single abstraction layer for all MetaTrader 5 Python API calls.
All broker/version-specific logic lives here only.
"""
import structlog
import config
from execution.execution_models import TradeOrder

log = structlog.get_logger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    log.warning("mt5_package_not_installed", message="MetaTrader5 package not found — running in stub mode")


class MT5Manager:
    """Thread-safe wrapper for MetaTrader5 Python API calls."""

    def __init__(self) -> None:
        self._connected = False

    def connect(self) -> bool:
        """Initialize and connect to MT5 terminal."""
        if not MT5_AVAILABLE:
            log.warning("mt5_stub_mode", message="MT5 not available — stub mode active")
            self._connected = True   # allow dev testing without MT5
            return True

        initialized = mt5.initialize(
            path=str(config.MT5_TERMINAL_PATH),
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        )
        if not initialized:
            log.error("mt5_init_failed", error=mt5.last_error())
            return False

        self._connected = True
        return True

    def disconnect(self) -> None:
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False

    def get_account_info(self):
        """Return MT5 account info object."""
        if not MT5_AVAILABLE:
            # Dev stub
            class _AccountStub:
                equity = 10000.0
                balance = 10000.0
                margin_free = 9000.0
            return _AccountStub()
        return mt5.account_info()

    def get_symbol_info(self, symbol: str):
        """Return MT5 symbol info object."""
        if not MT5_AVAILABLE:
            class _SymbolStub:
                point = 0.00001
                digits = 5
                trade_tick_value = 1.0
                trade_tick_size = 0.00001
                volume_min = 0.01
                volume_max = 100.0
            return _SymbolStub()
        return mt5.symbol_info(symbol)

    def get_positions_by_magic(self, magic: int) -> list:
        """Return all open positions with the given magic number."""
        if not MT5_AVAILABLE:
            return []
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [p for p in positions if p.magic == magic]

    def get_all_positions(self) -> list:
        """Return all open positions regardless of magic."""
        if not MT5_AVAILABLE:
            return []
        return list(mt5.positions_get() or [])

    def get_margin_required(self, symbol: str, lot_size: float, direction: str) -> float:
        """Calculate required margin for a potential trade."""
        if not MT5_AVAILABLE:
            return 100.0  # stub
        order_type = mt5.ORDER_TYPE_BUY if direction == "LONG" else mt5.ORDER_TYPE_SELL
        margin = mt5.order_calc_margin(order_type, symbol, lot_size, mt5.symbol_info_tick(symbol).ask)
        return margin or 0.0

    def place_order(self, order: TradeOrder) -> tuple[int, int | None]:
        """
        Send a market order to MT5.

        Returns:
            (result_code, ticket) — ticket is None on failure.
        """
        if not MT5_AVAILABLE:
            log.warning("mt5_stub_order", symbol=order.symbol, direction=order.direction)
            return 10009, None   # 10009 = TRADE_RETCODE_DONE in stub

        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(order.symbol)
        price = tick.ask if order.direction == "LONG" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if order.direction == "LONG" else mt5.ORDER_TYPE_SELL

        request = {
            "action":    mt5.TRADE_ACTION_DEAL,
            "symbol":    order.symbol,
            "volume":    order.lot_size,
            "type":      order_type,
            "price":     price,
            "sl":        order.sl,
            "tp":        order.tp or 0.0,
            "deviation": config.MAX_SLIPPAGE_POINTS,
            "magic":     order.magic,
            "comment":   order.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return result.retcode, result.order
        return result.retcode if result else -1, None

    def modify_position_sl_tp(self, ticket: int, new_sl: float, new_tp: float | None) -> bool:
        """Modify stop loss (and optionally TP) for an open position."""
        if not MT5_AVAILABLE:
            return True  # stub always succeeds

        position = mt5.positions_get(ticket=ticket)
        if not position:
            log.error("modify_position_not_found", ticket=ticket)
            return False

        pos = position[0]
        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "symbol":   pos.symbol,
            "position": ticket,
            "sl":       new_sl,
            "tp":       new_tp if new_tp is not None else pos.tp,
        }
        result = mt5.order_send(request)
        success = result and result.retcode == mt5.TRADE_RETCODE_DONE
        if not success:
            log.error("modify_sl_failed", ticket=ticket, retcode=result.retcode if result else -1)
        return success
