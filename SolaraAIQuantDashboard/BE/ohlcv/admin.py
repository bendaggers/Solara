from django.contrib import admin
from .models import OHLCV


@admin.register(OHLCV)
class OHLCVAdmin(admin.ModelAdmin):
    list_display  = ["symbol", "timeframe", "time", "open", "high", "low", "close", "volume"]
    list_filter   = ["symbol", "timeframe"]
    search_fields = ["symbol"]
    ordering      = ["-time"]
    # Candles are append-only — disable add/change/delete in admin
    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
