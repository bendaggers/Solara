from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OHLCVViewSet

router = DefaultRouter()
router.register(r"ohlcv", OHLCVViewSet, basename="ohlcv")

urlpatterns = [
    path("", include(router.urls)),
]
