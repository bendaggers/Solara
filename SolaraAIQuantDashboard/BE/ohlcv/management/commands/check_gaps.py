"""
Management command: python manage.py check_gaps

Scans all symbols/timeframes for missing candles, skips weekends and
KnownClosure slots, fills real gaps from MT5, and prints a clear summary.

Usage:
  python manage.py check_gaps           # check + fix
  python manage.py check_gaps --dry-run # report only, no inserts
"""

from django.core.management.base import BaseCommand
from ohlcv.services import find_gaps, fix_gaps
from ohlcv import mt5_bridge as mt5
import os


ALL_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
    "NZDJPY", "NZDCHF", "NZDCAD",
    "CADJPY", "CADCHF", "CHFJPY",
    "XAUUSD",
]


class Command(BaseCommand):
    help = "Check for OHLCV gaps, skip weekends + known closures, fill from MT5"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report gaps only — do not connect to MT5 or insert anything",
        )

    def handle(self, *args, **options):
        dry_run    = options["dry_run"]
        timeframes = os.environ.get("OHLCV_TIMEFRAMES", "M15,H1,H4,D1").split(",")

        self.stdout.write("\n========================================")
        self.stdout.write(f"  Solara Gap Check{'  (DRY RUN)' if dry_run else ''}")
        self.stdout.write("========================================")

        if not dry_run:
            if not mt5.connect():
                self.stderr.write(
                    "\n❌  MT5 connection failed — cannot fill gaps.\n"
                    "    Run with --dry-run to just check without MT5.\n"
                )
                return

        total_gaps  = 0
        total_fixed = 0

        try:
            for symbol in ALL_SYMBOLS:
                for tf in timeframes:
                    gaps = find_gaps(symbol, tf)
                    if not gaps:
                        continue

                    total_gaps += len(gaps)

                    if dry_run:
                        self.stdout.write(f"  [ ] {symbol} {tf}: {len(gaps)} gap(s) found")
                        continue

                    fixed        = fix_gaps(symbol, tf)
                    total_fixed += fixed
                    remaining    = len(gaps) - fixed

                    if fixed == len(gaps):
                        self.stdout.write(f"  [✓] {symbol} {tf}: {len(gaps)} gap(s) — all fixed")
                    elif fixed > 0:
                        self.stdout.write(
                            f"  [~] {symbol} {tf}: {len(gaps)} gap(s) — "
                            f"{fixed} fixed, {remaining} recorded as KnownClosure (holiday/halt)"
                        )
                    else:
                        self.stdout.write(
                            f"  [K] {symbol} {tf}: {len(gaps)} gap(s) — "
                            f"MT5 has no data, all recorded as KnownClosure"
                        )

        finally:
            if not dry_run:
                mt5.disconnect()

        self.stdout.write("========================================")

        if total_gaps == 0:
            self.stdout.write("  ✅  No gaps found — data is clean!")
        elif dry_run:
            self.stdout.write(
                f"  ℹ️   {total_gaps} gap(s) found across all symbols.\n"
                f"      Run without --dry-run to fix them."
            )
        else:
            remaining = total_gaps - total_fixed
            if remaining == 0:
                self.stdout.write(f"  ✅  All {total_fixed} gap(s) filled successfully!")
            else:
                self.stdout.write(
                    f"  ✅  {total_fixed} gap(s) filled.\n"
                    f"  📋  {remaining} slot(s) had no MT5 data — recorded as KnownClosure (won't retry)."
                )

        self.stdout.write("========================================\n")
