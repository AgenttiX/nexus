"""App configuration for calendars."""

from django.apps import AppConfig


class CalendarsConfig(AppConfig):
    """Calendars read from iCalendar addresses, such as those of Google Calendar."""

    name = "apps.calendars"
