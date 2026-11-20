"""Serializers for calendars."""

from django.core.exceptions import ValidationError
from rest_framework import serializers

from apps.calendars import ical
from apps.calendars.models import Calendar, Event


class CalendarSerializer(serializers.ModelSerializer[Calendar]):
    """A calendar. Its secret address can be written but is never returned."""

    url = serializers.CharField(write_only=True, max_length=2000)

    class Meta:
        model = Calendar
        fields = ("id", "name", "url", "color", "is_sleep", "sleep_as_android", "synced_at", "sync_error")
        read_only_fields = ("id", "synced_at", "sync_error")

    def validate_url(self, value: str) -> str:
        """Check that the server may fetch the address."""
        try:
            ical.validate_url(value)
        except ValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Report clashes with the user's other calendars as field errors rather than database errors."""
        user = self.context["request"].user
        others = Calendar.objects.for_user(user)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        if "name" in attrs and others.filter(name=attrs["name"]).exists():
            raise serializers.ValidationError({"name": "You already have a calendar with this name."})
        if attrs.get("is_sleep") and others.filter(is_sleep=True).exists():
            raise serializers.ValidationError({"is_sleep": "You already have a sleep calendar."})
        return attrs


class EventSerializer(serializers.ModelSerializer[Event]):
    """One occurrence of a calendar event."""

    class Meta:
        model = Event
        fields = ("id", "calendar", "start", "end", "all_day", "title", "description", "location")
