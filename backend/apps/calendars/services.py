"""Synchronising and reading calendars."""

import datetime as dt

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.calendars import ical
from apps.calendars.models import Calendar, Event
from apps.calendars.signals import calendar_synced

#: How far back and ahead events are kept. Long, so that a sleep calendar keeps its history.
HISTORY = dt.timedelta(days=365 * 20)
HORIZON = dt.timedelta(days=366)
MAX_TEXT_EVENTS = 100


def sync_calendar(calendar: Calendar) -> bool:
    """Replace the stored events of ``calendar`` with what its address serves now.

    Returns whether that succeeded. On failure the old events are kept and the
    reason is stored on the calendar, without the secret address.
    """
    now = timezone.now()
    try:
        parsed = ical.parse(ical.fetch(calendar.url), now - HISTORY, now + HORIZON)
    except Exception as error:  # noqa: BLE001 - any failure is reported to the user, and the next sync retries
        calendar.sync_error = type(error).__name__
        calendar.save(update_fields=["sync_error"])
        return False

    with transaction.atomic():
        calendar.events.all().delete()
        Event.objects.bulk_create(
            Event(
                calendar=calendar,
                uid=event.uid,
                start=event.start,
                end=event.end,
                all_day=event.all_day,
                title=event.title,
                description=event.description,
                location=event.location,
            )
            for event in parsed
        )
        calendar.synced_at = now
        calendar.sync_error = ""
        calendar.save(update_fields=["synced_at", "sync_error"])
    calendar_synced.send(sender=Calendar, calendar=calendar)
    return True


def events_between(user: User, start: dt.datetime, end: dt.datetime) -> QuerySet[Event]:
    """Return the events of ``user`` that overlap the period, except those of the sleep calendar."""
    return (
        Event.objects.filter(calendar__user=user, calendar__is_sleep=False, start__lt=end, end__gt=start)
        .select_related("calendar")
        .order_by("start", "end")
    )


def events_text(user: User, first: dt.date, last: dt.date) -> str:
    """Return the events of the days from ``first`` to ``last`` as compact text for an AI agent."""
    zone = timezone.get_current_timezone()
    start = dt.datetime.combine(first, dt.time.min, zone)
    end = dt.datetime.combine(last + dt.timedelta(days=1), dt.time.min, zone)
    events = list(events_between(user, start, end)[: MAX_TEXT_EVENTS + 1])
    if not events:
        return f"No events from {first} to {last}."

    lines: list[str] = []
    day: dt.date | None = None
    for event in events[:MAX_TEXT_EVENTS]:
        local_start, local_end = event.start.astimezone(zone), event.end.astimezone(zone)
        if local_start.date() != day:
            day = local_start.date()
            lines.append(f"{day:%a %Y-%m-%d}")
        when = "all day" if event.all_day else f"{local_start:%H:%M}-{local_end:%H:%M}"
        place = f" @ {event.location}" if event.location else ""
        lines.append(f"- {when} {event.title or '(no title)'}{place} [{event.calendar.name}]")
    if len(events) > MAX_TEXT_EVENTS:
        lines.append(f"(more events not shown; ask for a shorter period than {first} to {last})")
    return "\n".join(lines)
