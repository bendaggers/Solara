"""
Usage:
    python manage.py seed_trades           # insert dummy data (skips existing tickets)
    python manage.py seed_trades --flush   # delete all trades first, then insert
"""

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from trades.models import Trade


# ── Dummy data (mirrors FE/src/data/trades.js) ────────────────────────────────
OPEN_TRADES = [
    {
        "ticket":        1040231,
        "symbol":        "EURUSD",
        "open_time":     "2025-01-15 08:32:14",
        "type":          "buy",
        "volume":        0.10,
        "entry":         1.08320,
        "sl":            1.07800,
        "tp":            1.09100,
        "profit":        42.50,
        "current_price": 1.08745,
        "magic":         20240101,
        "comment":       "TI V2 LONG",
        "status":        "open",
    },
    {
        "ticket":        1040232,
        "symbol":        "GBPUSD",
        "open_time":     "2025-01-15 09:15:02",
        "type":          "sell",
        "volume":        0.20,
        "entry":         1.27150,
        "sl":            1.27800,
        "tp":            1.26200,
        "profit":        -18.40,
        "current_price": 1.27242,
        "magic":         20240101,
        "comment":       "TI V2 SHORT",
        "status":        "open",
    },
    {
        "ticket":        1040233,
        "symbol":        "XAUUSD",
        "open_time":     "2025-01-15 10:05:33",
        "type":          "buy",
        "volume":        0.05,
        "entry":         2648.50,
        "sl":            2635.00,
        "tp":            2680.00,
        "profit":        123.75,
        "current_price": 2673.25,
        "magic":         20240102,
        "comment":       "TI V2 GOLD LONG",
        "status":        "open",
    },
    {
        "ticket":        1040234,
        "symbol":        "USDJPY",
        "open_time":     "2025-01-15 11:22:45",
        "type":          "buy",
        "volume":        0.15,
        "entry":         157.820,
        "sl":            157.200,
        "tp":            158.900,
        "profit":        67.30,
        "current_price": 158.265,
        "magic":         20240101,
        "comment":       "TI V2 LONG",
        "status":        "open",
    },
    {
        "ticket":        1040235,
        "symbol":        "AUDUSD",
        "open_time":     "2025-01-15 12:44:18",
        "type":          "sell",
        "volume":        0.10,
        "entry":         0.62340,
        "sl":            0.62800,
        "tp":            0.61800,
        "profit":        -5.20,
        "current_price": 0.62392,
        "magic":         20240103,
        "comment":       "TI V2 SHORT",
        "status":        "open",
    },
    {
        "ticket":        1040236,
        "symbol":        "EURUSD",
        "open_time":     "2025-01-15 13:30:00",
        "type":          "sell",
        "volume":        0.10,
        "entry":         1.08900,
        "sl":            1.09400,
        "tp":            1.08100,
        "profit":        15.50,
        "current_price": 1.08745,
        "magic":         20240101,
        "comment":       "TI V2 SHORT",
        "status":        "open",
    },
    {
        "ticket":        1040237,
        "symbol":        "GBPJPY",
        "open_time":     "2025-01-15 14:10:55",
        "type":          "buy",
        "volume":        0.10,
        "entry":         200.450,
        "sl":            199.800,
        "tp":            201.500,
        "profit":        28.90,
        "current_price": 200.739,
        "magic":         20240102,
        "comment":       "TI V2 LONG",
        "status":        "open",
    },
    {
        "ticket":        1040238,
        "symbol":        "USDCAD",
        "open_time":     "2025-01-15 15:05:22",
        "type":          "buy",
        "volume":        0.20,
        "entry":         1.43250,
        "sl":            1.42700,
        "tp":            1.44100,
        "profit":        -12.80,
        "current_price": 1.43186,
        "magic":         20240103,
        "comment":       "TI V2 LONG",
        "status":        "open",
    },
]

CLOSED_TRADES = [
    {
        "ticket":        1040200,
        "symbol":        "EURUSD",
        "open_time":     "2025-01-14 08:00:00",
        "close_time":    "2025-01-14 16:30:00",
        "type":          "buy",
        "volume":        0.10,
        "entry":         1.08100,
        "sl":            1.07600,
        "tp":            1.08800,
        "profit":        68.00,
        "current_price": 1.08780,
        "magic":         20240101,
        "comment":       "TI V2 LONG",
        "status":        "closed",
    },
    {
        "ticket":        1040201,
        "symbol":        "GBPUSD",
        "open_time":     "2025-01-14 09:30:00",
        "close_time":    "2025-01-14 18:00:00",
        "type":          "sell",
        "volume":        0.15,
        "entry":         1.27500,
        "sl":            1.28000,
        "tp":            1.26700,
        "profit":        -22.50,
        "current_price": 1.27000,
        "magic":         20240101,
        "comment":       "TI V2 SHORT",
        "status":        "closed",
    },
    {
        "ticket":        1040202,
        "symbol":        "XAUUSD",
        "open_time":     "2025-01-13 10:00:00",
        "close_time":    "2025-01-13 20:00:00",
        "type":          "buy",
        "volume":        0.05,
        "entry":         2620.00,
        "sl":            2605.00,
        "tp":            2655.00,
        "profit":        175.00,
        "current_price": 2655.00,
        "magic":         20240102,
        "comment":       "TI V2 GOLD LONG",
        "status":        "closed",
    },
    {
        "ticket":        1040203,
        "symbol":        "USDJPY",
        "open_time":     "2025-01-13 11:00:00",
        "close_time":    "2025-01-13 22:00:00",
        "type":          "sell",
        "volume":        0.10,
        "entry":         158.500,
        "sl":            159.000,
        "tp":            157.500,
        "profit":        95.00,
        "current_price": 157.500,
        "magic":         20240101,
        "comment":       "TI V2 SHORT",
        "status":        "closed",
    },
]


class Command(BaseCommand):
    help = "Seed the database with dummy trade data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing trades before seeding",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            deleted, _ = Trade.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing trade(s)."))

        all_trades = OPEN_TRADES + CLOSED_TRADES
        created = skipped = 0

        for data in all_trades:
            ticket = data["ticket"]
            if Trade.objects.filter(ticket=ticket).exists():
                self.stdout.write(f"  ⟳  Skipping ticket #{ticket} (already exists)")
                skipped += 1
                continue

            Trade.objects.create(
                ticket        = ticket,
                symbol        = data["symbol"],
                open_time     = parse_datetime(data["open_time"] + "+00:00"),
                close_time    = parse_datetime(data.get("close_time", "") + "+00:00") if data.get("close_time") else None,
                type          = data["type"],
                volume        = data["volume"],
                entry         = data["entry"],
                sl            = data["sl"],
                tp            = data["tp"],
                profit        = data["profit"],
                current_price = data["current_price"],
                magic         = data["magic"],
                comment       = data["comment"],
                status        = data["status"],
            )
            self.stdout.write(f"  ✓  Created #{ticket} {data['type'].upper()} {data['symbol']}")
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — {created} trade(s) created, {skipped} skipped."
            )
        )
