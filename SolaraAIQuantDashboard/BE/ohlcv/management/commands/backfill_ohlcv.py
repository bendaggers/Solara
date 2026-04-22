"""
python manage.py backfill_ohlcv

Run this ONCE on system startup (or any time you want to fill historical gaps).
It connects to MT5, checks the DB for each symbol/timeframe, and fills missing
candles up to the configured backfill count.
"""

import os
import time
import logging

from django.core.management.base import BaseCommand

from ohlcv import mt5_bridge as mt5
from ohlcv.services import run_backfill

logger = logging.getLogger(__name__)

# ── Default symbols (28 major/minor forex pairs + gold) ──────────────────────
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


class Command(BaseCommand):
    help = "Backfill historical OHLCV data from MT5 on startup"

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbols",
            nargs="+",
            default=None,
            help="Space-separated list of symbols (default: all 28 pairs + XAUUSD)",
        )
        parser.add_argument(
            "--timeframes",
            nargs="+",
            default=None,
            help="Space-separated timeframes, e.g. M1 M5 H1 (default: from .env OHLCV_TIMEFRAMES)",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=None,
            help="Number of candles to backfill per symbol/timeframe (default: from .env OHLCV_BACKFILL_COUNT)",
        )

    def handle(self, *args, **options):
        symbols    = options["symbols"]    or DEFAULT_SYMBOLS
        timeframes = options["timeframes"] or os.environ.get("OHLCV_TIMEFRAMES", "M15,H1,H4,D1,W1").split(",")
        count      = options["count"]      or int(os.environ.get("OHLCV_BACKFILL_COUNT", 500))

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n🚀 OHLCV Backfill — {len(symbols)} symbols × {len(timeframes)} timeframes "
                f"({count} candles max)\n"
            )
        )

        if not mt5.connect():
            self.stderr.write(self.style.ERROR("❌ Failed to connect to MT5. Is the terminal running?"))
            return

        total_inserted = 0
        errors = []

        for symbol in symbols:
            for tf in timeframes:
                try:
                    inserted = run_backfill(symbol, tf, backfill_count=count)
                    total_inserted += inserted
                    status = f"+{inserted}" if inserted else "up-to-date"
                    self.stdout.write(f"  ✓  {symbol:<10} {tf:<4}  {status}")
                except Exception as e:
                    errors.append(f"{symbol} {tf}: {e}")
                    self.stdout.write(self.style.ERROR(f"  ✗  {symbol} {tf}: {e}"))

        mt5.disconnect()

        self.stdout.write("")
        if errors:
            self.stdout.write(self.style.WARNING(f"Completed with {len(errors)} error(s)."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Backfill complete — {total_inserted} total candles inserted.")
            )
