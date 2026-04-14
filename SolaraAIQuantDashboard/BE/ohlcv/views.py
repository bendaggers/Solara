from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Max

from .models import OHLCV
from .serializers import OHLCVSerializer


class OHLCVViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/ohlcv/?symbol=EURUSD&timeframe=H1          — latest 500 candles
    GET /api/ohlcv/?symbol=EURUSD&timeframe=H1&limit=100
    GET /api/ohlcv/latest/  — most recent candle per symbol/timeframe (for monitoring)
    """

    serializer_class = OHLCVSerializer
    filter_backends  = [filters.OrderingFilter]
    ordering         = ["-time"]

    def get_queryset(self):
        symbol    = self.request.query_params.get("symbol")
        timeframe = self.request.query_params.get("timeframe")
        limit     = int(self.request.query_params.get("limit", 500))

        qs = OHLCV.objects.all()
        if symbol:
            qs = qs.filter(symbol__iexact=symbol)
        if timeframe:
            qs = qs.filter(timeframe__iexact=timeframe)
        return qs[:limit]

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """Returns the most recent candle stored per symbol/timeframe combo."""
        rows = (
            OHLCV.objects
            .values("symbol", "timeframe")
            .annotate(last_time=Max("time"))
            .order_by("symbol", "timeframe")
        )
        return Response(list(rows))
