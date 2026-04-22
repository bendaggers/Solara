from rest_framework import serializers
from .models import Trade


class TradeSerializer(serializers.ModelSerializer):
    # Expose open_time in the same "MM/DD/YYYY HH:MM:SS" format the FE already uses
    time = serializers.DateTimeField(source="open_time", format="%m/%d/%Y %H:%M:%S")
    currentPrice = serializers.DecimalField(
        source="current_price", max_digits=12, decimal_places=5
    )

    class Meta:
        model  = Trade
        fields = [
            "ticket",
            "symbol",
            "time",          # aliased from open_time
            "type",
            "volume",
            "entry",
            "sl",
            "tp",
            "profit",
            "currentPrice",  # aliased from current_price
            "magic",
            "comment",
            "status",
        ]
