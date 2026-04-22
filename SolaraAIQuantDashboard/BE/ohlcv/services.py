"""
Core OHLCV business logic.

Key rule on which MT5 fetch function to use:
  fetch_candles_from() — backfill, catch-up, gap fixing
                         downloads from broker server, works for all symbols
  fetch_candles()      — close-time inserts only
                         reads local cache, fast, always fresh at close time
"""

import logging
from datetime import datetime, timezone, timedelta

from django.db import connection

from .models import OHLCV, KnownClosure
from . import mt5_bridge as mt5

logger = logging.getLogger(__name__)

TF_MINUTES = {
    "M1":  1,
    "M5":  5,
    "M15": 15,
    "M30": 30,
    "H1":  60,
    "H4":  240,
    "D1":  1440,
    "W1":  10080,
}

# ── Forex market hours ────────────────────────────────────────────────────────

def _is_forex_market_open(dt: datetime) -> bool:
    wd = dt.weekday()  # 0=Mon … 4=Fri, 5=Sat, 6=Sun
    if wd == 5:                        # Saturday — always closed
        return False
    if wd == 6 and dt.hour < 22:      # Sunday before 22:00 UTC
        return False
    if wd == 4 and dt.hour >= 22:     # Friday 22:00 UTC onwards
        return False
    return True

# ── DB helpers ────────────────────────────────────────────────────────────────

def get_last_stored_time(symbol: str, timeframe: str) -> datetime | None:
    return (
        OHLCV.objects
        .filter(symbol=symbol, timeframe=timeframe)
        .order_by("-time")
        .values_list("time", flat=True)
        .first()
    )


def _get_known_closures(symbol: str, timeframe: str) -> set:
    return set(
        KnownClosure.objects
        .filter(symbol=symbol, timeframe=timeframe)
        .values_list("time", flat=True)
    )


def _record_known_closures(symbol: str, timeframe: str, times: list[datetime], reason: str = "no_data"):
    objs = [
        KnownClosure(symbol=symbol, timeframe=timeframe, time=t, reason=reason)
        for t in times
    ]
    KnownClosure.objects.bulk_create(objs, ignore_conflicts=True)


def bulk_insert_candles(symbol: str, timeframe: str, candles: list[dict]) -> int:
    """Insert candles, return count of rows actually written (not attempted)."""
    if not candles:
        return 0

    sql = """
        INSERT INTO ohlcv (symbol, timeframe, time, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, timeframe, time) DO NOTHING
        RETURNING time
    """

    inserted = 0
    with connection.cursor() as cursor:
        for c in candles:
            cursor.execute(sql, (
                symbol, timeframe,
                c["time"], c["open"], c["high"], c["low"], c["close"], c["volume"]
            ))
            inserted += len(cursor.fetchall())

    return inserted

# ── Gap detection ─────────────────────────────────────────────────────────────

def find_gaps(symbol: str, timeframe: str) -> list[datetime]:
    """
    Walk consecutive stored candle pairs — find gaps between them.
    Skips: forex weekends, KnownClosure entries.
    """
    if timeframe not in TF_MINUTES:
        return []

    step = timedelta(minutes=TF_MINUTES[timeframe])

    stored_times = list(
        OHLCV.objects
        .filter(symbol=symbol, timeframe=timeframe)
        .order_by("time")
        .values_list("time", flat=True)
    )

    if len(stored_times) < 2:
        return []

    known_closures = _get_known_closures(symbol, timeframe)
    now_utc        = datetime.now(tz=timezone.utc)
    gaps           = []

    for i in range(len(stored_times) - 1):
        a = stored_times[i]
        b = stored_times[i + 1]

        if b - a <= step:
            continue

        slot = a + step
        while slot < b:
            if (
                slot + step <= now_utc
                and _is_forex_market_open(slot)
                and slot not in known_closures
            ):
                gaps.append(slot)
            slot += step

    if gaps:
        logger.info("%s %s — %d genuine gap(s) found", symbol, timeframe, len(gaps))

    return gaps


def fix_gaps(symbol: str, timeframe: str) -> int:
    """
    Fill genuine gaps using fetch_candles_from() which downloads from
    broker server — works even if the chart is not open in MT5.
    Records unfillable slots in KnownClosure permanently.
    """
    gaps = find_gaps(symbol, timeframe)
    if not gaps:
        return 0

    step           = timedelta(minutes=TF_MINUTES[timeframe])
    total_inserted = 0
    unfillable     = []

    # Group consecutive gaps → one fetch per range
    gap_ranges  = []
    range_start = gaps[0]
    range_end   = gaps[0]

    for gap in gaps[1:]:
        if gap - range_end <= step * 2:
            range_end = gap
        else:
            gap_ranges.append((range_start, range_end))
            range_start = gap
            range_end   = gap
    gap_ranges.append((range_start, range_end))

    for (start, end) in gap_ranges:
        span    = int((end - start) / step) + 5
        count   = max(span, 10)

        # Use fetch_candles_from — downloads from broker server
        candles = mt5.fetch_candles_from(
            symbol, timeframe,
            from_time=start - step,   # small buffer before gap start
            count=count
        )

        in_range = [
            c for c in candles
            if start <= c["time"] <= end
            and mt5.is_closed(c["time"], timeframe)
        ] if candles else []

        inserted = bulk_insert_candles(symbol, timeframe, in_range)
        total_inserted += inserted

        if inserted:
            logger.info(
                "  Fixed: %s %s %s→%s (+%d)",
                symbol, timeframe, start, end, inserted
            )
        else:
            # MT5 server has no data — record as known closure
            slot = start
            while slot <= end:
                unfillable.append(slot)
                slot += step
            logger.info(
                "  Closure: %s %s %s→%s (no data on server)",
                symbol, timeframe, start, end
            )

    if unfillable:
        _record_known_closures(symbol, timeframe, unfillable)

    return total_inserted

# ── Sync — for close-time inserts (uses local cache) ─────────────────────────

def sync_symbol_timeframe(symbol: str, timeframe: str, fetch_count: int = 3) -> int:
    """
    Insert newly closed candles since last stored time.
    Uses fetch_candles() (local cache) — safe at close time when
    the candle just formed and is guaranteed cached.
    """
    last_time = get_last_stored_time(symbol, timeframe)
    candles   = mt5.fetch_candles(symbol, timeframe, count=fetch_count)

    if not candles:
        return 0

    to_insert = [
        c for c in candles
        if (last_time is None or c["time"] > last_time)
        and mt5.is_closed(c["time"], timeframe)
    ]

    return bulk_insert_candles(symbol, timeframe, to_insert)

# ── Backfill — uses server fetch ──────────────────────────────────────────────

def run_backfill(symbol: str, timeframe: str, backfill_count: int = 500) -> int:
    """
    Empty table  → fetch backfill_count candles from start of history
    Has data     → fetch from last stored time to now (catch-up)

    Always uses fetch_candles_from() to download from broker server.
    """
    last_time = get_last_stored_time(symbol, timeframe)

    if last_time is None:
        # Initial backfill — fetch from far back
        from_time = (
            datetime.now(tz=timezone.utc)
            - timedelta(minutes=TF_MINUTES[timeframe] * backfill_count)
        )
        logger.info("Initial backfill: %s %s from %s", symbol, timeframe, from_time)
    else:
        # Catch-up — fetch from just before last stored candle
        from_time = last_time - timedelta(minutes=TF_MINUTES[timeframe])
        logger.debug("Catch-up: %s %s from %s", symbol, timeframe, from_time)

    candles = mt5.fetch_candles_from(
        symbol, timeframe,
        from_time=from_time,
        count=backfill_count
    )

    closed   = [c for c in candles if mt5.is_closed(c["time"], timeframe)]
    inserted = bulk_insert_candles(symbol, timeframe, closed)

    if inserted:
        logger.info("Backfill: %s %s +%d candles", symbol, timeframe, inserted)

    return inserted
