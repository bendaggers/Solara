from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from .models import Trade
from .serializers import TradeSerializer


class TradeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/trades/          — list all trades (paginated, 100/page)
    GET /api/trades/?status=open    — filter by status
    GET /api/trades/?status=closed  — filter by status
    GET /api/trades/?symbol=EURUSD  — filter by symbol
    GET /api/trades/{ticket}/       — retrieve single trade
    GET /api/trades/summary/        — aggregated stats for StatCards
    """

    serializer_class = TradeSerializer
    filter_backends  = [filters.OrderingFilter]
    ordering_fields  = ["open_time", "profit", "symbol", "volume"]
    ordering         = ["-open_time"]

    def get_queryset(self):
        qs     = Trade.objects.all()
        status = self.request.query_params.get("status")
        symbol = self.request.query_params.get("symbol")
        if status:
            qs = qs.filter(status=status)
        if symbol:
            qs = qs.filter(symbol__iexact=symbol)
        return qs

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Returns aggregate data consumed by the StatCards."""
        open_qs   = Trade.objects.filter(status="open")
        closed_qs = Trade.objects.filter(status="closed")

        total_open    = open_qs.count()
        floating_pnl  = open_qs.aggregate(total=Sum("profit"))["total"] or 0
        total_volume  = open_qs.aggregate(total=Sum("volume"))["total"] or 0

        total_closed  = closed_qs.count()
        winning       = closed_qs.filter(profit__gt=0).count()
        win_rate      = round((winning / total_closed * 100), 1) if total_closed else 0

        return Response(
            {
                "open_trades":   total_open,
                "floating_pnl":  float(floating_pnl),
                "win_rate":      win_rate,
                "total_volume":  float(total_volume),
                "total_closed":  total_closed,
            }
        )
