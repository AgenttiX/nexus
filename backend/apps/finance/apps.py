"""App configuration for personal finances."""

from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """Bank accounts and their transactions, imported from the exports of online banks."""

    name = "apps.finance"
