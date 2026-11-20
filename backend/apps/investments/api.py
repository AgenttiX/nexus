"""REST API for investments."""

import datetime as dt

from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.investments import services
from apps.investments.models import Holding
from apps.investments.serializers import HoldingSerializer, PortfolioSerializer

HISTORY_DAYS = 365


def _user(request: Request) -> User:
    user = request.user
    assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
    return user


class HoldingViewSet(viewsets.ModelViewSet[Holding]):
    """The signed-in user's holdings."""

    serializer_class = HoldingSerializer
    queryset = Holding.objects.none()

    def get_queryset(self) -> QuerySet[Holding]:
        """Return only the holdings of the signed-in user."""
        return Holding.objects.for_user(_user(self.request)).select_related("asset")

    def perform_create(self, serializer: BaseSerializer[Holding]) -> None:
        """Create the holding for the signed-in user."""
        serializer.save(user=self.request.user)


class PortfolioView(APIView):
    """The signed-in user's portfolio."""

    @extend_schema(responses=PortfolioSerializer)
    def get(self, request: Request) -> Response:
        """Return the positions at their latest prices, the total, and the value over the last year."""
        user = _user(request)
        result = services.portfolio(user)
        today = timezone.localdate()
        history = services.value_history(user, today - dt.timedelta(days=HISTORY_DAYS), today)
        data = {
            "total_eur": result.total_eur,
            "positions": result.positions,
            "history": [{"date": day, "value_eur": value} for day, value in history],
        }
        return Response(PortfolioSerializer(data).data)
