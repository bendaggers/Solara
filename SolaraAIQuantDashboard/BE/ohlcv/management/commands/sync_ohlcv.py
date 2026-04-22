"""
python manage.py sync_ohlcv

Continuous sync loop — runs forever, polling MT5 every 60 seconds.
Each cycle:
  1. Inserts newly closed candles (normal sync)
  2. Detects and fills any gaps in stored history

Usage:
    python manage.py sync_ohlcv                         # uses .env defaults
    python manage.py sync_ohlcv --interval 60           # explicit 60s interval
    python manage.py sync_ohlcv --symbols EURUSD GBPUSD --timeframes H1 D1
    python manage.py sync_ohlcv --once                  # one cycle then exit (testing)
    python manage.py sync_ohlcv --skip-gap-fix          # disable gap fixing
"""

import os
import time
import signal
import logging
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from ohlcv import mt5_bridge as mt5
from ohlcv.services import sync_symbol_timeframe, fix_gaps

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "NZDJPY", "NZDCHF", "NZDCAD",
    "CADJPY", "CADCHF",
    "CHFJPY",
    "XAUUSD",
]

_running = True

def _handle_stop(signum, frame):
    global _running
    _running = False
    print("\n\n Stopping sync loop...")

signal.signal(signal.SIGINT,  _handle_stop)
signal.signal(signal.SIGTERM, _handle_stop)


class Command(BaseCommand):
    help = "Continuously sync closed OHLCV candles from MT5, with automatic gap detection and filling"

    def add_arguments(self, parser):
        parser.add_argument("--symbols",      nargs="+", default=None)
        parser.add_argument("--timeframes",   nargs="+", default=None)
        parser.add_argument(
            "--interval", type=int, default=None,
            help="Poll interval in seconds (default: from .env OHLCV_SYNC_INTERVAL, fallback 60)"
        )
        parser.add_argument(
            "--fetch-count", type=int, default=50,
            help="Candles to fetch per symbol/tf per cycle (default: 50)"
        )
        parser.add_argument(
            "--once", action="store_true",
            help="Run one cycle then exit (for testing)"
        )
        parser.add_argument(
            "--skip-gap-fix", action="store_true",
            help="Disable gap detection/filling (faster cycles, not recommended)"
        )

    def handle(self, *args, **options):
        global _running

        symbols      = options["symbols"]    or DEFAULT_SYMBOLS
        timeframes   = options["timeframes"] or os.environ.get("OHLCV_TIMEFRAMES", "M15,H1,H4,D1,W1").split(",")
        interval     = options["interval"]   or int(os.environ.get("OHLCV_SYNC_INTERVAL", 60))
        fetch_count  = options["fetch_count"]
        run_once     = options["once"]
        skip_gap_fix = options["skip_gap_fix"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n OHLCV Sync Loop\n"
                f"   Symbols:    {len(symbols)}\n"
                f"   Timeframes: {', '.join(timeframes)}\n"
                f"   Interval:   {interval}s (1 minute)\n"
                f"   Gap fixing: {'disabled' if skip_gap_fix else 'enabled'}\n"
                f"   Press Ctrl+C to stop.\n"
            )
        )

        if not mt5.connect():
            self.stderr.write(self.style.ERROR(" Failed to connect to MT5."))
            return

        cycle = 0
        while _running:
            cycle += 1
            cycle_start    = datetime.now(tz=timezone.utc)
            total_inserted = 0
            total_fixed    = 0

            self.stdout.write(
                f"\n[{cycle_start.strftime('%Y-%m-%d %H:%M:%S')} UTC] Cycle #{cycle}"
            )

            for symbol in symbols:
                for tf in timeframes:
                    if not _running:
                        break
                    try:
                        # Step 1 — insert newly closed candles
                        inserted = sync_symbol_timeframe(symbol, tf, fetch_count=fetch_count)
                        total_inserted += inserted

                        # Step 2 — detect and fill any gaps in history
                        fixed = 0
                        if not skip_gap_fix:
                            fixed = fix_gaps(symbol, tf)
                            total_fixed += fixed

                        if inserted or fixed:
                            self.stdout.write(
                                f"  {symbol:<10} {tf:<4}  "
                                f"+{inserted} new  "
                                f"{'gap: +' + str(fixed) if fixed else ''}"
                            )

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"  {symbol} {tf}: {e}")
                        )

            elapsed = (datetime.now(tz=timezone.utc) - cycle_start).total_seconds()
            self.stdout.write(
                f"  Cycle done in {elapsed:.1f}s | "
                f"{total_inserted} new candle(s) | "
                f"{total_fixed} gap(s) filled"
            )

            if run_once:
                break

            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0 and _running:
                time.sleep(sleep_time)

        mt5.disconnect()
        self.stdout.write(self.style.SUCCESS("\n Sync loop stopped cleanly."))
