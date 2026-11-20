"""REST API for sleep."""

from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.sleep import services
from apps.sleep.models import SleepRecord
from apps.sleep.serializers import PeriodSerializer, SleepRecordSerializer, SleepSummarySerializer

PERIOD_PARAMETERS = [
    OpenApiParameter("start", OpenApiTypes.DATE, required=True, description="First wake-up date."),
    OpenApiParameter("end", OpenApiTypes.DATE, required=True, description="Last wake-up date."),
    OpenApiParameter("tag", OpenApiTypes.STR, description="Only records with this tag."),
]


def _period(request: Request) -> tuple[User, dict[str, object]]:
    user = request.user
    assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
    period = PeriodSerializer(data=request.query_params)
    period.is_valid(raise_exception=True)
    return user, period.validated_data


@extend_schema_view(list=extend_schema(parameters=PERIOD_PARAMETERS))
class SleepRecordViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[SleepRecord]):
    """The signed-in user's sleep records whose wake-up date is in a period."""

    serializer_class = SleepRecordSerializer
    queryset = SleepRecord.objects.none()

    def get_queryset(self) -> QuerySet[SleepRecord]:
        """Return the user's records in the requested period."""
        user, period = _period(self.request)
        return services.records_between(user, period["start"], period["end"], period["tag"])  # type: ignore[arg-type]


class SleepSummaryView(APIView):
    """Statistics of the signed-in user's nights in a period."""

    @extend_schema(parameters=PERIOD_PARAMETERS, responses=SleepSummarySerializer)
    def get(self, request: Request) -> Response:
        """Return bedtime, wake-up time, duration and weekend jet lag statistics."""
        user, period = _period(request)
        result = services.summary(user, period["start"], period["end"], period["tag"])  # type: ignore[arg-type]
        return Response(SleepSummarySerializer(result).data)
