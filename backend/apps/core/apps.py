"""App configuration for shared building blocks."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Shared building blocks used by every feature app."""

    name = "apps.core"
