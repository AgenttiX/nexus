"""App configuration for users and authentication."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Users, Authentik login and (later) agent tokens."""

    name = "apps.accounts"
