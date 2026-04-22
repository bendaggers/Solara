from django.db import models


class Trade(models.Model):
    """
    Represents a single forex position from MetaTrader 5.
    Field names match the shape used by the React frontend (trades.js).
    """

    TRADE_TYPE_CHOICES = [("buy", "Buy"), ("sell", "Sell")]
    STATUS_CHOICES = [("open", "Open"), ("closed", "Closed")]

    # ── Identity ──────────────────────────────────────────────────────────────
    ticket = models.BigIntegerField(unique=True, help_text="MT5 order/position ticket")
    symbol = models.CharField(max_length=20, help_text="e.g. EURUSD, XAUUSD")
    type   = models.CharField(max_length=4, choices=TRADE_TYPE_CHOICES)
    status = models.CharField(max_length=6, choices=STATUS_CHOICES, default="open", db_index=True)

    # ── Timing ────────────────────────────────────────────────────────────────
    open_time  = models.DateTimeField(help_text="When the position was opened")
    close_time = models.DateTimeField(null=True, blank=True, help_text="Set when closed")

    # ── Prices ────────────────────────────────────────────────────────────────
    entry         = models.DecimalField(max_digits=12, decimal_places=5, help_text="Entry price")
    current_price = models.DecimalField(max_digits=12, decimal_places=5, help_text="Last known market price")
    sl            = models.DecimalField(max_digits=12, decimal_places=5, default=0, help_text="Stop Loss price")
    tp            = models.DecimalField(max_digits=12, decimal_places=5, default=0, help_text="Take Profit price")

    # ── Size & P&L ────────────────────────────────────────────────────────────
    volume = models.DecimalField(max_digits=8, decimal_places=2, help_text="Lot size, e.g. 0.10")
    profit = models.DecimalField(max_digits=12, decimal_places=2, help_text="Floating or closed P&L in USD")

    # ── Metadata ──────────────────────────────────────────────────────────────
    magic   = models.BigIntegerField(default=0, help_text="EA magic number")
    comment = models.CharField(max_length=255, blank=True, default="")

    # ── Housekeeping ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-open_time"]
        indexes  = [
            models.Index(fields=["symbol"]),
            models.Index(fields=["status", "-open_time"]),
        ]

    def __str__(self):
        return f"#{self.ticket} {self.type.upper()} {self.symbol} ({self.status})"
