"""REST API for calendars."""

from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.accounts.models import User
from apps.calendars import services, tasks
from apps.calendars.models import Calendar, Event
from apps.calendars.serializers import CalendarSerializer, EventSerializer


class CalendarViewSet(viewsets.ModelViewSet[Calendar]):
    """The signed-in user's calendars."""

    serializer_class = CalendarSerializer
    queryset = Calendar.objects.none()

    def get_queryset(self) -> QuerySet[Calendar]:
        """Return only the calendars of the signed-in user."""
        user = self.request.user
        assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
        return Calendar.objects.for_user(user)

    def perform_create(self, serializer: BaseSerializer[Calendar]) -> None:
        """Create the calendar for the signed-in user and fetch its events in the background."""
        calendar = serializer.save(user=self.request.user)
        tasks.sync_calendar.delay(calendar.pk)

    def perform_update(self, serializer: BaseSerializer[Calendar]) -> None:
        """Save the calendar and fetch its events again, as the address or its meaning may have changed."""
        calendar = serializer.save()
        tasks.sync_calendar.delay(calendar.pk)

    @extend_schema(request=None, responses={202: None})
    @action(detail=True, methods=["post"])
    def sync(self, request: Request, pk: str | None = None) -> Response:
        """Fetch the calendar's events again in the background."""
        tasks.sync_calendar.delay(self.get_object().pk)
        return Response(status=status.HTTP_202_ACCEPTED)


class PeriodSerializer(serializers.Serializer[dict[str, object]]):
    """The period whose events are wanted."""

    start = serializers.DateTimeField()
    end = serializers.DateTimeField()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Require the end to be after the start."""
        if attrs["end"] <= attrs["start"]:  # type: ignore[operator]
            msg = "The end must be after the start."
            raise serializers.ValidationError(msg)
        return attrs


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("start", OpenApiTypes.DATETIME, required=True),
            OpenApiParameter("end", OpenApiTypes.DATETIME, required=True),
        ],
    ),
)
class EventViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[Event]):
    """Events of the signed-in user's calendars that overlap a period, except those of the sleep calendar."""

    serializer_class = EventSerializer
    queryset = Event.objects.none()

    def get_queryset(self) -> QuerySet[Event]:
        """Return the user's events in the requested period."""
        user = self.request.user
        assert isinstance(user, User)  # noqa: S101 - guaranteed by IsAuthenticated
        period = PeriodSerializer(data=self.request.query_params)
        period.is_valid(raise_exception=True)
        return services.events_between(user, period.validated_data["start"], period.validated_data["end"])
