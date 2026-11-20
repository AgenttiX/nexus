"""App configuration for time tracking."""

from django.apps import AppConfig


class TimetrackingConfig(AppConfig):
    """Computer and phone use, read from the data that ActivityWatch records on the user's devices."""

    name = "apps.timetracking"
