"""
execution/position_sizer.py — Dynamic Position Sizer
======================================================
Calculates lot size based on account equity and risk parameters.
Formula: lot = (equity * risk_pct) / (sl_pips * pip_value)
"""
import structlog
import config

log = structlog.get_logger(__name__)


class PositionSizer:
    """Calculates dynamic lot size per trade."""

    def __init__(self, mt5_manager) -> None:
        self._mt5 = mt5_manager

    def calculate(
        self,
        symbol: str,
        sl_pips: int | None = None,
    ) -> float:
        """
        Calculate lot size for a trade.

        Args:
            symbol:  MT5 symbol name.
            sl_pips: Stop loss distance in pips.
                     Uses config.DEFAULT_STOP_LOSS_PIPS if not provided.

        Returns:
            Calculated lot size, clamped to broker min/max.
            Returns 0.0 if calculation fails.
        """
        sl_pips = sl_pips or config.DEFAULT_STOP_LOSS_PIPS

        try:
            account_info = self._mt5.get_account_info()
            equity = account_info.equity

            symbol_info = self._mt5.get_symbol_info(symbol)
            pip_value = symbol_info.trade_tick_value / symbol_info.trade_tick_size

            risk_amount = equity * config.MAX_RISK_PER_TRADE
            lot_size = risk_amount / (sl_pips * pip_value)
            lot_size = round(lot_size, 2)

            # Clamp to broker limits
            min_lot = symbol_info.volume_min
            max_lot = symbol_info.volume_max
            lot_size = max(min_lot, min(max_lot, lot_size))

            log.debug(
                "lot_size_calculated",
                symbol=symbol,
                equity=equity,
                sl_pips=sl_pips,
                pip_value=pip_value,
                lot_size=lot_size,
            )
            return lot_size

        except Exception as e:
            log.error("lot_size_calculation_failed", symbol=symbol, error=str(e))
            return 0.0
