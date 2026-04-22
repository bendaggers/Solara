from rest_framework import serializers
from .models import OHLCV


class OHLCVSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OHLCV
        fields = ["symbol", "timeframe", "time", "open", "high", "low", "close", "volume"]
