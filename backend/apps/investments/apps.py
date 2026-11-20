"""App configuration for investments."""

from django.apps import AppConfig


class InvestmentsConfig(AppConfig):
    """Holdings of stocks, funds and cryptocurrencies, valued with fetched prices."""

    name = "apps.investments"
