"""
execution/trade_executor.py — Trade Executor
=============================================
Places trades via MT5 Python API with retry logic and ticket confirmation.
"""
import time
import structlog
from signals.signal_models import AggregatedSignal
from execution.execution_models import TradeOrder, ExecutionResult, TradeStatus
from execution.position_sizer import PositionSizer
import config

log = structlog.get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0

# MT5 retryable return codes
RETRYABLE_CODES = {10004, 10006, 10007, 10016}


class TradeExecutor:
    """Executes approved signals via the MT5 manager with retry."""

    def __init__(self, mt5_manager) -> None:
        self._mt5 = mt5_manager
        self._sizer = PositionSizer(mt5_manager=mt5_manager)

    def execute(self, signal: AggregatedSignal) -> ExecutionResult:
        """
        Place a trade for an approved signal.

        Returns:
            ExecutionResult with ticket on success, failure_reason on failure.
        """
        lot_size = self._sizer.calculate(symbol=signal.symbol)

        # Build SL / TP
        symbol_info = self._mt5.get_symbol_info(signal.symbol)
        pip_size = symbol_info.point * 10  # 1 pip = 10 points for most pairs

        if signal.direction == "LONG":
            sl = signal.price - (config.DEFAULT_STOP_LOSS_PIPS * pip_size)
            tp = signal.price + (config.DEFAULT_TAKE_PROFIT_PIPS * pip_size)
        else:
            sl = signal.price + (config.DEFAULT_STOP_LOSS_PIPS * pip_size)
            tp = signal.price - (config.DEFAULT_TAKE_PROFIT_PIPS * pip_size)

        order = TradeOrder(
            symbol=signal.symbol,
            direction=signal.direction,
            lot_size=lot_size,
            sl=round(sl, symbol_info.digits),
            tp=round(tp, symbol_info.digits),
            magic=signal.magic,
            comment=signal.comment,
            price=signal.price,
        )

        for attempt in range(1, MAX_RETRIES + 1):
            result_code, ticket = self._mt5.place_order(order)

            if ticket:
                log.info(
                    "trade_placed",
                    symbol=order.symbol,
                    direction=order.direction,
                    lot=order.lot_size,
                    sl=order.sl,
                    tp=order.tp,
                    magic=order.magic,
                    ticket=ticket,
                    attempts=attempt,
                )
                return ExecutionResult(
                    order=order,
                    status=TradeStatus.PLACED,
                    ticket=ticket,
                    fill_price=signal.price,
                    mt5_result_code=result_code,
                    attempts=attempt,
                )

            if result_code not in RETRYABLE_CODES:
                break

            log.warning(
                "trade_retry",
                symbol=order.symbol,
                attempt=attempt,
                result_code=result_code,
            )
            time.sleep(RETRY_DELAY_SECONDS)

        log.error(
            "trade_failed",
            symbol=order.symbol,
            direction=order.direction,
            result_code=result_code,
            attempts=MAX_RETRIES,
        )
        return ExecutionResult(
            order=order,
            status=TradeStatus.FAILED,
            mt5_result_code=result_code,
            failure_reason=f"MT5 result code: {result_code}",
            attempts=MAX_RETRIES,
        )
