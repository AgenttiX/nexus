"""Background tasks for calendars."""

from celery import shared_task

from apps.calendars import services
from apps.calendars.models import Calendar


@shared_task
def sync_calendar(calendar_id: int) -> bool:
    """Synchronise one calendar. Returns whether it succeeded; a deleted calendar counts as failed."""
    calendar = Calendar.objects.filter(pk=calendar_id).first()
    return calendar is not None and services.sync_calendar(calendar)


@shared_task
def sync_all_calendars() -> int:
    """Queue the synchronisation of every calendar. Returns how many were queued."""
    ids = list(Calendar.objects.values_list("pk", flat=True))
    for calendar_id in ids:
        sync_calendar.delay(calendar_id)
    return len(ids)
