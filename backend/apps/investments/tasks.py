"""Background tasks for investments."""

from celery import shared_task

from apps.investments import services


@shared_task
def update_prices() -> int:
    """Fetch new prices and exchange rates. Returns the number of assets updated."""
    return services.update_prices()
