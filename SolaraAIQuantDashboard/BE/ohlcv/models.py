from django.db import models


class OHLCV(models.Model):
    """
    Append-only historical candle store.

    Rules:
      - Insert once, never update, never delete (unless fixing bad data)
      - Only CLOSED candles are stored
      - Primary key is (symbol, timeframe, time) — enforced at DB level
      - All times are UTC
    """

    symbol    = models.CharField(max_length=20)
    timeframe = models.CharField(max_length=5)   # e.g. M1, M5, H1, D1
    time      = models.DateTimeField()            # candle open time, UTC

    open   = models.FloatField()
    high   = models.FloatField()
    low    = models.FloatField()
    close  = models.FloatField()
    volume = models.FloatField()

    class Meta:
        db_table = "ohlcv"
        unique_together = [("symbol", "timeframe", "time")]
        indexes = [
            models.Index(
                fields=["symbol", "timeframe", "-time"],
                name="idx_symbol_tf_time",
            )
        ]
        ordering = ["-time"]

    def __str__(self):
        return f"{self.symbol} {self.timeframe} {self.time} O={self.open} H={self.high} L={self.low} C={self.close}"


class KnownClosure(models.Model):
    """
    Permanently records candle slots that MT5 confirmed have no data.

    Examples: holidays, broker halts, gaps during market suspension.
    Once a slot is here, gap detection skips it forever — never retried.

    Rules:
      - Never delete from this table unless fixing a bug
      - Written automatically by fix_gaps() when MT5 returns no data
    """

    symbol      = models.CharField(max_length=20)
    timeframe   = models.CharField(max_length=5)
    time        = models.DateTimeField()           # candle open time, UTC
    reason      = models.CharField(max_length=50, default="no_data")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ohlcv_known_closure"
        unique_together = [("symbol", "timeframe", "time")]
        ordering = ["symbol", "timeframe", "time"]

    def __str__(self):
        return f"KnownClosure {self.symbol} {self.timeframe} {self.time} ({self.reason})"
