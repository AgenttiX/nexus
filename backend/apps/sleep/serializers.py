"""Serializers for sleep."""

from rest_framework import serializers

from apps.sleep.models import SleepRecord


class SleepRecordSerializer(serializers.ModelSerializer[SleepRecord]):
    """One period of sleep."""

    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = SleepRecord
        fields = (
            "id",
            "start",
            "end",
            "duration_hours",
            "rating",
            "latitude",
            "longitude",
            "deep_sleep",
            "cycles",
            "noise",
            "snoring",
            "comment",
            "tags",
        )

    def get_duration_hours(self, obj: SleepRecord) -> float:
        """Return the time asleep in hours."""
        return obj.duration.total_seconds() / 3600


class PeriodSerializer(serializers.Serializer[dict[str, object]]):
    """The wake-up dates to include, and optionally a tag to filter by."""

    start = serializers.DateField()
    end = serializers.DateField()
    tag = serializers.CharField(required=False, default="")

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Require the start not to be after the end."""
        if attrs["start"] > attrs["end"]:  # type: ignore[operator]
            msg = "The start must not be after the end."
            raise serializers.ValidationError(msg)
        return attrs


class StatsSerializer(serializers.Serializer[object]):
    """Summary of a series of values in hours. Clock times are hours after midnight."""

    count = serializers.IntegerField()
    minimum = serializers.FloatField()
    maximum = serializers.FloatField()
    mean = serializers.FloatField()
    median = serializers.FloatField()
    std = serializers.FloatField()


class SleepSummarySerializer(serializers.Serializer[object]):
    """Statistics of the nights in a period. A statistic is null when there is no data for it."""

    first = serializers.DateField()
    last = serializers.DateField()
    nights = serializers.IntegerField()
    bedtime = StatsSerializer(allow_null=True)
    wake_time = StatsSerializer(allow_null=True)
    duration = StatsSerializer(allow_null=True)
    jet_lag = StatsSerializer(allow_null=True)
