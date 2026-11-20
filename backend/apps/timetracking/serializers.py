"""Serializers for time tracking."""

import datetime as dt

from rest_framework import serializers

from apps.timetracking.models import Bucket

MAX_DAYS = 92


class BucketSerializer(serializers.ModelSerializer[Bucket]):
    """A stream of events from one watcher on one device."""

    class Meta:
        model = Bucket
        fields = ("id", "name", "type", "client", "hostname", "imported_until")


class TimePeriodSerializer(serializers.Serializer[dict[str, object]]):
    """The days to include."""

    start = serializers.DateField()
    end = serializers.DateField()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Require the start not to be after the end, and a period short enough to compute quickly."""
        start, end = attrs["start"], attrs["end"]
        assert isinstance(start, dt.date)  # noqa: S101 - parsed by the date fields
        assert isinstance(end, dt.date)  # noqa: S101
        if not start <= end < start + dt.timedelta(days=MAX_DAYS):
            msg = f"The start must not be after the end, and the period at most {MAX_DAYS} days."
            raise serializers.ValidationError(msg)
        return attrs


class DayHoursSerializer(serializers.Serializer[object]):
    """Active hours of one day."""

    date = serializers.DateField()
    hours = serializers.FloatField()


class NamedHoursSerializer(serializers.Serializer[object]):
    """Active hours of one app or device."""

    name = serializers.CharField()
    hours = serializers.FloatField()


class TimeSummarySerializer(serializers.Serializer[object]):
    """Active time in a period, in hours, by day, app and device. Apps and devices are sorted by time."""

    first = serializers.DateField()
    last = serializers.DateField()
    total = serializers.FloatField()
    by_day = DayHoursSerializer(many=True)
    by_app = NamedHoursSerializer(many=True)
    by_device = NamedHoursSerializer(many=True)
