"""
execution/risk_manager.py — Pre-Trade Risk Manager
====================================================
5-check gate before any trade is placed.
Checks run in order — first failure rejects the signal.
See FS Section 8 for full specification.
"""
import structlog
from signals.signal_models import AggregatedSignal
from execution.position_sizer import PositionSizer
import config

log = structlog.get_logger(__name__)


class RiskManager:
    """Enforces all pre-trade risk rules before execution."""

    def __init__(self, mt5_manager) -> None:
        self._mt5 = mt5_manager
        self._sizer = PositionSizer(mt5_manager=mt5_manager)
        self._daily_trade_counts: dict[int, int] = {}   # magic → count today
        self._session_start_equity: float | None = None

    def check(self, signal: AggregatedSignal) -> bool:
        """
        Run all 5 risk checks on a signal.

        Returns:
            True  → signal approved, proceed to execution.
            False → signal rejected, do not trade.
        """
        # ── Check 1: Daily drawdown ───────────────────────────────────────────
        account = self._mt5.get_account_info()
        if self._session_start_equity is None:
            self._session_start_equity = account.equity

        drawdown = (self._session_start_equity - account.equity) / self._session_start_equity
        if drawdown >= config.MAX_DAILY_DRAWDOWN_PCT:
            log.error(
                "risk_rejected_drawdown",
                symbol=signal.symbol,
                drawdown_pct=round(drawdown * 100, 2),
                threshold_pct=config.MAX_DAILY_DRAWDOWN_PCT * 100,
                action="ALL_TRADING_HALTED",
            )
            return False

        # ── Check 2: Daily trade count ────────────────────────────────────────
        trades_today = self._daily_trade_counts.get(signal.magic, 0)
        if trades_today >= config.MAX_DAILY_TRADES:
            log.warning(
                "risk_rejected_daily_limit",
                model=signal.model_name,
                magic=signal.magic,
                trades_today=trades_today,
                limit=config.MAX_DAILY_TRADES,
            )
            return False

        # ── Check 3: Model position limit ────────────────────────────────────
        open_positions = self._mt5.get_positions_by_magic(signal.magic)
        entry = None  # TODO: fetch from registry for max_positions
        # Fallback to 3 if registry not wired here yet
        max_pos = getattr(entry, "max_positions", 3) if entry else 3
        if len(open_positions) >= max_pos:
            log.info(
                "risk_rejected_position_limit",
                model=signal.model_name,
                open=len(open_positions),
                max=max_pos,
            )
            return False

        # ── Check 4 + 5: Lot size and margin ─────────────────────────────────
        lot_size = self._sizer.calculate(symbol=signal.symbol)
        if lot_size <= 0.0:
            log.error(
                "risk_rejected_invalid_lot",
                symbol=signal.symbol,
                lot_size=lot_size,
            )
            return False

        margin_required = self._mt5.get_margin_required(
            symbol=signal.symbol,
            lot_size=lot_size,
            direction=signal.direction,
        )
        if account.margin_free < margin_required:
            log.warning(
                "risk_rejected_insufficient_margin",
                symbol=signal.symbol,
                margin_free=account.margin_free,
                margin_required=margin_required,
            )
            return False

        # ── All checks passed ─────────────────────────────────────────────────
        log.info(
            "risk_approved",
            symbol=signal.symbol,
            direction=signal.direction,
            model=signal.model_name,
            confidence=signal.confidence,
            lot_size=lot_size,
        )
        return True

    def record_trade(self, magic: int) -> None:
        """Increment daily trade counter after a successful placement."""
        self._daily_trade_counts[magic] = self._daily_trade_counts.get(magic, 0) + 1
