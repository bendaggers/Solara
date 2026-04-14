"""
Celery tasks for OHLCV — event-driven, not polling.

Startup sequence (automatic via worker_ready signal in celery.py):
  1. backfill_all_ohlcv  → catch up ALL missed candles since last shutdown
  2. check_and_fix_gaps  → fill any holes in stored history

Ongoing schedule (via Celery Beat):
  insert_m15/h1/h4/d1/w1 → fires exactly when each candle closes
  check_and_fix_gaps      → daily safety net at 23:00 UTC
"""

import os
import logging
from datetime import datetime, timezone, timedelta

from celery import shared_task
from celery.schedules import crontab

from . import mt5_bridge as mt5
from .services import sync_symbol_timeframe, fix_gaps, run_backfill, bulk_insert_candles, get_last_stored_time

logger = logging.getLogger(__name__)

ALL_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "NZDJPY", "NZDCHF", "NZDCAD",
    "CADJPY", "CADCHF", "CHFJPY",
    "XAUUSD",
]

TF_MINUTES = {
    "M15": 15,
    "H1":  60,
    "H4":  240,
    "D1":  1440,
    "W1":  10080,
}

def get_timeframes():
    return os.environ.get("OHLCV_TIMEFRAMES", "M15,H1,H4,D1,W1").split(",")

def get_backfill_count():
    return int(os.environ.get("OHLCV_BACKFILL_COUNT", 500))


def _candles_since_last_stored(symbol: str, timeframe: str) -> int:
    """
    Calculate how many candles to fetch to cover from last stored time to now.
    Adds a 20-candle buffer for safety.
    Minimum 10, maximum 500.
    """
    last_time = get_last_stored_time(symbol, timeframe)
    if last_time is None:
        return get_backfill_count()

    minutes_per_candle = TF_MINUTES.get(timeframe, 60)
    now_utc = datetime.now(tz=timezone.utc)
    minutes_elapsed = (now_utc - last_time).total_seconds() / 60
    candles_needed = int(minutes_elapsed / minutes_per_candle) + 20

    return max(10, min(candles_needed, 500))


# ── Startup catch-up ──────────────────────────────────────────────────────────

@shared_task(name="ohlcv.backfill_all", bind=True, max_retries=3)
def backfill_all_ohlcv(self):
    """
    Runs automatically on worker startup (via worker_ready signal in celery.py).
    Also safe to run manually: python manage.py backfill_ohlcv

    For each symbol/timeframe:
      - Empty table  → fetch OHLCV_BACKFILL_COUNT candles (initial history)
      - Has data     → calculate exact number of candles needed to cover
                       the gap since last stored time → fetch exactly that many

    This ensures ALL missed candles are recovered regardless of how long
    the system was offline (weekend, overnight, multi-day downtime).
    """
    if not mt5.connect():
        logger.error("backfill_all: MT5 connection failed")
        raise self.retry(countdown=30)

    timeframes     = get_timeframes()
    total_inserted = 0

    try:
        for symbol in ALL_SYMBOLS:
            for tf in timeframes:
                try:
                    last_time = get_last_stored_time(symbol, tf)

                    if last_time is None:
                        # First ever run — fetch full history
                        count = get_backfill_count()
                    else:
                        # Calculate exactly how many candles we need
                        count = _candles_since_last_stored(symbol, tf)

                    inserted = run_backfill(symbol, tf, backfill_count=count)
                    total_inserted += inserted

                    if inserted:
                        logger.info(
                            "Catch-up: %s %s +%d (fetched %d)",
                            symbol, tf, inserted, count
                        )
                except Exception as e:
                    logger.error("Backfill error %s %s: %s", symbol, tf, e)
    finally:
        mt5.disconnect()

    logger.info("Startup catch-up complete — %d total candle(s) inserted", total_inserted)
    return {"inserted": total_inserted}


# ── Gap check ─────────────────────────────────────────────────────────────────

@shared_task(name="ohlcv.check_and_fix_gaps", bind=True, max_retries=3)
def check_and_fix_gaps(self):
    """
    Runs automatically on worker startup (chained after backfill_all).
    Also runs daily at 23:00 UTC as a safety net.

    Scans all symbols/timeframes for genuine gaps between stored candles.
    Skips: forex weekend windows, KnownClosure entries (holidays/halts).
    Records unfillable slots in KnownClosure permanently — never retried.
    """
    if not mt5.connect():
        raise self.retry(countdown=60)

    timeframes  = get_timeframes()
    total_fixed = 0

    try:
        for symbol in ALL_SYMBOLS:
            for tf in timeframes:
                try:
                    fixed = fix_gaps(symbol, tf)
                    total_fixed += fixed
                except Exception as e:
                    logger.error("Gap fix error %s %s: %s", symbol, tf, e)
    finally:
        mt5.disconnect()

    logger.info("Gap check complete — %d candle(s) filled", total_fixed)
    return {"gaps_fixed": total_fixed}


# ── Per-timeframe close-time inserts ─────────────────────────────────────────

def _insert_for_tf(timeframe: str) -> dict:
    """Insert just-closed candles for all symbols on the given timeframe."""
    if not mt5.connect():
        logger.error("MT5 connection failed for %s insert", timeframe)
        return {"inserted": 0}

    total = 0
    try:
        for symbol in ALL_SYMBOLS:
            try:
                inserted = sync_symbol_timeframe(symbol, timeframe, fetch_count=3)
                total += inserted
                if inserted:
                    logger.info("Closed candle: %s %s +%d", symbol, timeframe, inserted)
            except Exception as e:
                logger.error("Insert error %s %s: %s", symbol, timeframe, e)
    finally:
        mt5.disconnect()

    return {"inserted": total}


@shared_task(name="ohlcv.insert_m15")
def insert_m15():
    """Fires at :01 :16 :31 :46 — 1 min after each M15 candle closes."""
    return _insert_for_tf("M15")


@shared_task(name="ohlcv.insert_h1")
def insert_h1():
    """Fires at :01 past every hour — 1 min after H1 closes."""
    return _insert_for_tf("H1")


@shared_task(name="ohlcv.insert_h4")
def insert_h4():
    """Fires at 00:01 04:01 08:01 12:01 16:01 20:01 UTC."""
    return _insert_for_tf("H4")


@shared_task(name="ohlcv.insert_d1")
def insert_d1():
    """Fires at 22:01 UTC daily — 1 min after forex daily close."""
    return _insert_for_tf("D1")


@shared_task(name="ohlcv.insert_w1")
def insert_w1():
    """Fires Friday 22:01 UTC — 1 min after weekly close."""
    return _insert_for_tf("W1")


# ── On-demand (for live charting) ─────────────────────────────────────────────

@shared_task(name="ohlcv.sync_single")
def sync_single_ohlcv(symbol: str, timeframe: str):
    """
    On-demand fetch for a single symbol/timeframe.
    Called by the live charting feature when a user opens a chart.

    Usage:
        from ohlcv.tasks import sync_single_ohlcv
        sync_single_ohlcv.delay("EURUSD", "H1")
    """
    if not mt5.connect():
        return {"error": "MT5 connection failed"}
    try:
        count    = _candles_since_last_stored(symbol, timeframe)
        inserted = sync_symbol_timeframe(symbol, timeframe, fetch_count=count)
        return {"symbol": symbol, "timeframe": timeframe, "inserted": inserted}
    finally:
        mt5.disconnect()
