"""App configuration for news."""

from django.apps import AppConfig


class NewsConfig(AppConfig):
    """News articles from several sites, and daily digests of them written by a language model."""

    name = "apps.news"
