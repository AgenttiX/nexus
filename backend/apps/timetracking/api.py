"""REST API for time tracking."""

from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.timetracking import services
from apps.timetracking.models import Bucket
from apps.timetracking.serializers import BucketSerializer, TimePeriodSerializer, TimeSummarySerializer


def _user(request: Request) -> User:
    user = request.user
    assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
    return user


class BucketViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[Bucket]):
    """The signed-in user's ActivityWatch buckets, which shows what has been imported and until when."""

    serializer_class = BucketSerializer
    queryset = Bucket.objects.none()

    def get_queryset(self) -> QuerySet[Bucket]:
        """Return only the buckets of the signed-in user."""
        return Bucket.objects.for_user(_user(self.request))


class TimeSummaryView(APIView):
    """Active time of the signed-in user in a period."""

    @extend_schema(
        parameters=[
            OpenApiParameter("start", OpenApiTypes.DATE, required=True),
            OpenApiParameter("end", OpenApiTypes.DATE, required=True),
        ],
        responses=TimeSummarySerializer,
    )
    def get(self, request: Request) -> Response:
        """Return active hours by day, app and device."""
        period = TimePeriodSerializer(data=request.query_params)
        period.is_valid(raise_exception=True)
        result = services.summary(
            _user(request), period.validated_data["start"], period.validated_data["end"]
        )

        def named(hours_by_name: dict[str, float]) -> list[dict[str, object]]:
            return [{"name": name, "hours": hours} for name, hours in services.ranked(hours_by_name)]

        data = {
            "first": result.first,
            "last": result.last,
            "total": result.total,
            "by_day": [{"date": day, "hours": hours} for day, hours in result.by_day.items()],
            "by_app": named(result.by_app),
            "by_device": named(result.by_device),
        }
        return Response(TimeSummarySerializer(data).data)
