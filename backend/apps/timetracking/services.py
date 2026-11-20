"""Importing ActivityWatch data and summarising time use."""

import datetime as dt
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.timetracking import activitywatch
from apps.timetracking.models import Bucket, Event

BATCH_SIZE = 2000
WINDOW_TYPE = "currentwindow"
AFK_TYPE = "afkstatus"
NOT_AFK = "not-afk"
MAX_TEXT_APPS = 15
UNKNOWN = "(unknown)"

Interval = tuple[dt.datetime, dt.datetime]


def import_all() -> int:
    """Import new events for every user who has a directory of ActivityWatch data.

    The data of a user is expected in ``<AW_SYNC_DIR>/<username>/``. Returns
    the number of events stored.
    """
    root = Path(settings.AW_SYNC_DIR)
    return sum(import_user(user, root / user.username) for user in User.objects.filter(is_active=True))


def import_user(user: User, directory: Path) -> int:
    """Import new events from every database below ``directory`` for ``user``."""
    stored = 0
    for path in activitywatch.find_databases(directory):
        try:
            with closing(activitywatch.connect(path)) as connection:
                stored += _import_database(user, connection)
        except sqlite3.Error:
            # Being written, half-synchronised or not an ActivityWatch database: try again next time.
            continue
    return stored


def _import_database(user: User, connection: sqlite3.Connection) -> int:
    stored = 0
    for source in activitywatch.read_buckets(connection):
        bucket, _ = Bucket.objects.update_or_create(
            user=user,
            name=source.name[:300],
            defaults={
                "type": source.type[:100],
                "client": source.client[:100],
                "hostname": source.hostname[:200],
            },
        )
        batch: list[Event] = []
        for event in activitywatch.read_events(connection, source, bucket.imported_until):
            batch.append(
                Event(bucket=bucket, source_id=event.id, start=event.start, end=event.end, data=event.data)
            )
            if len(batch) >= BATCH_SIZE:
                stored += _store(batch)
                batch = []
        stored += _store(batch)
        bucket.imported_until = bucket.events.aggregate(latest=Max("end"))["latest"]
        bucket.save(update_fields=["imported_until"])
    return stored


def _store(events: list[Event]) -> int:
    Event.objects.bulk_create(
        events,
        update_conflicts=True,
        unique_fields=["bucket", "source_id"],
        update_fields=["start", "end", "data"],
    )
    return len(events)


@dataclass
class Summary:
    """Active time in a period, in hours. Active means a window had the focus while the user was not away."""

    first: dt.date
    last: dt.date
    by_day: dict[dt.date, float] = field(default_factory=dict)
    by_app: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    by_device: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    @property
    def total(self) -> float:
        """Active hours in the whole period."""
        return sum(self.by_day.values())


def summary(user: User, first: dt.date, last: dt.date) -> Summary:
    """Summarise the active time of ``user`` on the days from ``first`` to ``last``, by day, app and device.

    On each device the window events are cut to the periods when the user was
    at the device, according to its away-from-keyboard watcher. A device
    without such a watcher (a phone) counts in full.
    """
    zone = timezone.get_current_timezone()
    start = dt.datetime.combine(first, dt.time.min, zone)
    end = dt.datetime.combine(last + dt.timedelta(days=1), dt.time.min, zone)
    result = Summary(first, last)
    result.by_day = {first + dt.timedelta(days=offset): 0.0 for offset in range((last - first).days + 1)}

    buckets = list(Bucket.objects.for_user(user).filter(type__in=[WINDOW_TYPE, AFK_TYPE]))
    for hostname in sorted({bucket.hostname for bucket in buckets}):
        afk_buckets = [
            bucket for bucket in buckets if bucket.hostname == hostname and bucket.type == AFK_TYPE
        ]
        present = _merge(
            (max(event.start, start), min(event.end, end))
            for event in Event.objects.filter(
                bucket__in=afk_buckets, start__lt=end, end__gt=start, data__status=NOT_AFK
            )
        )
        window_buckets = [
            bucket for bucket in buckets if bucket.hostname == hostname and bucket.type == WINDOW_TYPE
        ]
        for event in Event.objects.filter(bucket__in=window_buckets, start__lt=end, end__gt=start).order_by(
            "start"
        ):
            span = (max(event.start, start), min(event.end, end))
            pieces = _intersect(span, present) if afk_buckets else [span]
            app = str(event.data.get("app") or UNKNOWN)
            for piece_start, piece_end in pieces:
                for day, hours in _split_by_day(piece_start.astimezone(zone), piece_end.astimezone(zone)):
                    result.by_day[day] += hours
                    result.by_app[app] += hours
                    result.by_device[hostname or UNKNOWN] += hours
    return result


def _merge(intervals: Iterable[Interval]) -> list[Interval]:
    """Return sorted, non-overlapping intervals covering the same time as ``intervals``."""
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _intersect(span: Interval, intervals: list[Interval]) -> list[Interval]:
    """Return the parts of ``span`` that lie within the sorted ``intervals``."""
    return [
        (max(span[0], start), min(span[1], end))
        for start, end in intervals
        if start < span[1] and end > span[0]
    ]


def _split_by_day(start: dt.datetime, end: dt.datetime) -> list[tuple[dt.date, float]]:
    """Split a period of local time at midnights, giving the hours that fall on each day."""
    parts: list[tuple[dt.date, float]] = []
    while start < end:
        midnight = dt.datetime.combine(start.date() + dt.timedelta(days=1), dt.time.min, start.tzinfo)
        piece_end = min(end, midnight)
        parts.append((start.date(), (piece_end - start).total_seconds() / 3600))
        start = piece_end
    return parts


def _hours(value: float) -> str:
    minutes = round(value * 60)
    return f"{minutes // 60}:{minutes % 60:02d}"


def summary_text(user: User, first: dt.date, last: dt.date) -> str:
    """Return the summary of a period as compact text for an AI agent."""
    result = summary(user, first, last)
    if result.total == 0:
        return f"No activity recorded from {first} to {last}."
    days = len(result.by_day)
    lines = [
        f"Active time {first}..{last}: {_hours(result.total)} total, {_hours(result.total / days)} per day"
    ]
    if len(result.by_device) > 1:
        lines.append(
            "devices: " + ", ".join(f"{name} {_hours(hours)}" for name, hours in ranked(result.by_device))
        )
    apps = ranked(result.by_app)
    lines.append("apps: " + ", ".join(f"{name} {_hours(hours)}" for name, hours in apps[:MAX_TEXT_APPS]))
    if len(apps) > MAX_TEXT_APPS:
        lines.append(f"({len(apps) - MAX_TEXT_APPS} more apps not shown)")
    lines.append(
        "days: " + ", ".join(f"{day:%a %m-%d} {_hours(hours)}" for day, hours in result.by_day.items())
    )
    return "\n".join(lines)


def ranked(hours_by_name: dict[str, float]) -> list[tuple[str, float]]:
    """Return names with their hours, most hours first."""
    return sorted(hours_by_name.items(), key=lambda item: (-item[1], item[0]))
