"""Background tasks for restaurant menus."""

from celery import shared_task

from apps.food.services import import_feed
from apps.food.unicafe import fetch_feed


@shared_task
def fetch_menus() -> int:
    """Download the current UniCafe menus and store them. Returns the number of dishes stored."""
    return import_feed(fetch_feed())
