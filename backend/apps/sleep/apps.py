"""App configuration for sleep monitoring."""

from django.apps import AppConfig


class SleepConfig(AppConfig):
    """Sleep statistics from the user's sleep calendar."""

    name = "apps.sleep"

    def ready(self) -> None:
        """Rebuild sleep records whenever a calendar has been synchronised."""
        from apps.calendars.signals import calendar_synced  # noqa: PLC0415 - apps are not loaded before ready()
        from apps.sleep.services import on_calendar_synced  # noqa: PLC0415

        calendar_synced.connect(on_calendar_synced)
