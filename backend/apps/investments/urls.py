"""URLs of the investments app."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.investments.api import HoldingViewSet, PortfolioView

router = SimpleRouter()
router.register("investments/holdings", HoldingViewSet, basename="holding")

urlpatterns = [
    path("investments/portfolio/", PortfolioView.as_view(), name="portfolio"),
    *router.urls,
]
