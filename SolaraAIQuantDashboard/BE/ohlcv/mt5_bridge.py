"""
MT5 Bridge — all MetaTrader5 interaction lives here.

fetch_candles_from() is the primary function used for backfill/catchup.
It uses copy_rates_from() which downloads from the broker server,
not just local cache — critical for symbols without open charts.

fetch_candles() uses copy_rates_from_pos() for lightweight recent fetches
(close-time inserts) where data is guaranteed to be cached.
"""

import os
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not found. Running in MOCK mode.")

TF_MAP = {
    "M1":  (mt5.TIMEFRAME_M1  if MT5_AVAILABLE else 1,     1),
    "M5":  (mt5.TIMEFRAME_M5  if MT5_AVAILABLE else 5,     5),
    "M15": (mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15,    15),
    "M30": (mt5.TIMEFRAME_M30 if MT5_AVAILABLE else 30,    30),
    "H1":  (mt5.TIMEFRAME_H1  if MT5_AVAILABLE else 60,    60),
    "H4":  (mt5.TIMEFRAME_H4  if MT5_AVAILABLE else 240,   240),
    "D1":  (mt5.TIMEFRAME_D1  if MT5_AVAILABLE else 1440,  1440),
    "W1":  (mt5.TIMEFRAME_W1  if MT5_AVAILABLE else 10080, 10080),
}

# ── Connection ────────────────────────────────────────────────────────────────

def connect() -> bool:
    if not MT5_AVAILABLE:
        logger.warning("MT5 not available — skipping connect()")
        return False

    login    = int(os.environ.get("MT5_LOGIN",    0))
    password = os.environ.get("MT5_PASSWORD", "")
    server   = os.environ.get("MT5_SERVER",   "")

    if not mt5.initialize():
        logger.error("mt5.initialize() failed: %s", mt5.last_error())
        return False

    if login and password and server:
        authorized = mt5.login(login, password=password, server=server)
        if not authorized:
            logger.error("mt5.login() failed: %s", mt5.last_error())
            mt5.shutdown()
            return False

    info = mt5.account_info()
    logger.info("MT5 connected — account %s on %s", info.login if info else "?", server)
    return True


def disconnect():
    if MT5_AVAILABLE:
        mt5.shutdown()


# ── Raw rate → dict ───────────────────────────────────────────────────────────

def _rate_to_dict(r) -> dict:
    return {
        "time":   datetime.fromtimestamp(r["time"], tz=timezone.utc),
        "open":   round(float(r["open"]),        5),
        "high":   round(float(r["high"]),        5),
        "low":    round(float(r["low"]),         5),
        "close":  round(float(r["close"]),       5),
        "volume": round(float(r["tick_volume"]), 2),
    }


# ── Primary fetch — downloads from broker server ──────────────────────────────

def fetch_candles_from(symbol: str, timeframe: str,
                       from_time: datetime, count: int = 500) -> list[dict]:
    """
    Fetch up to `count` candles starting FROM `from_time`.
    Uses copy_rates_from() which downloads data from the broker server
    if not cached locally — required for symbols without open charts.

    Use this for: backfill, catch-up, gap fixing.
    """
    if not MT5_AVAILABLE:
        return []

    if timeframe not in TF_MAP:
        logger.error("Unknown timeframe: %s", timeframe)
        return []

    mt5_tf, _ = TF_MAP[timeframe]

    # Ensure from_time is timezone-aware
    if from_time.tzinfo is None:
        from_time = from_time.replace(tzinfo=timezone.utc)

    rates = mt5.copy_rates_from(symbol, mt5_tf, from_time, count)

    if rates is None or len(rates) == 0:
        logger.warning(
            "No rates from server for %s %s from %s — %s",
            symbol, timeframe, from_time, mt5.last_error()
        )
        return []

    return [_rate_to_dict(r) for r in rates]


# ── Secondary fetch — from local cache (recent candles only) ──────────────────

def fetch_candles(symbol: str, timeframe: str, count: int = 3) -> list[dict]:
    """
    Fetch the last `count` candles from local cache (pos=0).
    Uses copy_rates_from_pos() — fast but only works for cached data.

    Use this for: close-time inserts where the candle just formed
                  and is guaranteed to be in local cache.
    """
    if not MT5_AVAILABLE:
        return []

    if timeframe not in TF_MAP:
        return []

    mt5_tf, _ = TF_MAP[timeframe]

    rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)

    if rates is None or len(rates) == 0:
        logger.warning(
            "No rates in local cache for %s %s — %s",
            symbol, timeframe, mt5.last_error()
        )
        return []

    return [_rate_to_dict(r) for r in rates]


# ── Closed candle detection ───────────────────────────────────────────────────

def is_closed(candle_time: datetime, timeframe: str) -> bool:
    if timeframe not in TF_MAP:
        return False
    _, minutes = TF_MAP[timeframe]
    close_time = candle_time + timedelta(minutes=minutes)
    return datetime.now(tz=timezone.utc) >= close_time
