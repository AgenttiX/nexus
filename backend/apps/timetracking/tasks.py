"""Background tasks for time tracking."""

from celery import shared_task

from apps.timetracking import services


@shared_task
def import_activitywatch() -> int:
    """Import new ActivityWatch events of all users. Returns the number of events stored."""
    return services.import_all()
