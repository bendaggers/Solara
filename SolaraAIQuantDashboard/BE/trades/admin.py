from django.contrib import admin
from .models import Trade


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display  = ["ticket", "symbol", "type", "volume", "entry", "profit", "status", "open_time"]
    list_filter   = ["status", "type", "symbol"]
    search_fields = ["ticket", "symbol", "comment"]
    ordering      = ["-open_time"]
    readonly_fields = ["created_at", "updated_at"]
