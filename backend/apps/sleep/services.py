"""Building sleep records from the sleep calendar, and summarising them."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.calendars.models import Calendar
from apps.sleep import sleep_as_android
from apps.sleep.models import SleepRecord, Tag
from apps.sleep.statistics import Stats, circular_mean, clock_difference, summarize, summarize_clock

#: Shorter periods are naps: they are stored, but left out of the statistics of nights.
MIN_NIGHT = dt.timedelta(hours=3)
SATURDAY = 5
MAX_TEXT_NIGHTS = 62


def on_calendar_synced(calendar: Calendar, **kwargs: object) -> None:  # noqa: ARG001 - signal signature
    """Signal receiver: rebuild the owner's sleep records after their calendar changed."""
    rebuild_records(calendar)


@transaction.atomic
def rebuild_records(calendar: Calendar) -> int:
    """Replace the sleep records of the calendar's owner if this is, or was, their sleep calendar.

    Returns the number of records now stored for the user.
    """
    has_other_sleep_calendar = (
        Calendar.objects.for_user(calendar.user).filter(is_sleep=True).exclude(pk=calendar.pk).exists()
    )
    if not calendar.is_sleep and has_other_sleep_calendar:
        return SleepRecord.objects.for_user(calendar.user).count()

    SleepRecord.objects.for_user(calendar.user).delete()
    Tag.objects.for_user(calendar.user).delete()
    if not calendar.is_sleep:
        return 0

    tags: dict[str, Tag] = {}
    count = 0
    for event in calendar.events.filter(all_day=False):
        if event.end <= event.start:
            continue
        details = (
            sleep_as_android.parse(event) if calendar.sleep_as_android else sleep_as_android.SleepDetails()
        )
        record = SleepRecord.objects.create(
            user=calendar.user,
            start=event.start,
            end=event.end,
            duration=details.duration or event.end - event.start,
            rating=details.rating,
            latitude=details.latitude,
            longitude=details.longitude,
            deep_sleep=details.deep_sleep,
            cycles=details.cycles,
            noise=details.noise,
            snoring=details.snoring,
            comment=details.comment,
        )
        for name in sleep_as_android.extract_tags(details.comment):
            if name not in tags:
                tags[name] = Tag.objects.create(user=calendar.user, name=name)
            record.tags.add(tags[name])
        count += 1
    return count


def records_between(user: User, first: dt.date, last: dt.date, tag: str = "") -> QuerySet[SleepRecord]:
    """Return the records of ``user`` that ended (woke up) on the days from ``first`` to ``last``."""
    zone = timezone.get_current_timezone()
    start = dt.datetime.combine(first, dt.time.min, zone)
    end = dt.datetime.combine(last + dt.timedelta(days=1), dt.time.min, zone)
    records = SleepRecord.objects.for_user(user).filter(end__gte=start, end__lt=end)
    if tag:
        records = records.filter(tags__name=tag.lower().removeprefix("#"))
    return records.order_by("start").prefetch_related("tags")


@dataclass(frozen=True)
class Summary:
    """Statistics of the nights in a period. All values are in hours."""

    first: dt.date
    last: dt.date
    nights: int
    bedtime: Stats | None
    wake_time: Stats | None
    duration: Stats | None
    jet_lag: Stats | None


def summary(user: User, first: dt.date, last: dt.date, tag: str = "") -> Summary:
    """Summarise the nights that ended on the days from ``first`` to ``last``.

    Jet lag is computed per calendar week that has nights on both weekdays and
    the weekend: the mean middle of sleep of nights ending on Saturday or
    Sunday, minus that of the other nights. Positive means sleeping later at
    the weekend.
    """
    zone = timezone.get_current_timezone()
    bedtimes: list[float] = []
    wake_times: list[float] = []
    durations: list[float] = []
    middles_by_week: dict[tuple[int, int], dict[bool, list[float]]] = defaultdict(lambda: defaultdict(list))

    for record in records_between(user, first, last, tag):
        if record.duration < MIN_NIGHT:
            continue
        start, end = record.start.astimezone(zone), record.end.astimezone(zone)
        middle = start + (end - start) / 2
        bedtimes.append(_clock_hours(start))
        wake_times.append(_clock_hours(end))
        durations.append(record.duration.total_seconds() / 3600)
        year, week, _ = end.isocalendar()
        middles_by_week[year, week][end.weekday() >= SATURDAY].append(_clock_hours(middle))

    lags = [
        clock_difference(circular_mean(groups[True]), circular_mean(groups[False]))
        for groups in middles_by_week.values()
        if groups[True] and groups[False]
    ]
    return Summary(
        first=first,
        last=last,
        nights=len(durations),
        bedtime=summarize_clock(bedtimes),
        wake_time=summarize_clock(wake_times),
        duration=summarize(durations),
        jet_lag=summarize(lags),
    )


def summary_text(user: User, first: dt.date, last: dt.date, tag: str = "") -> str:
    """Return the summary of a period as compact text for an AI agent."""
    result = summary(user, first, last, tag)
    title = f"Sleep {first}..{last}" + (f" #{tag.lower().removeprefix('#')}" if tag else "")
    if result.duration is None or result.bedtime is None or result.wake_time is None:
        return f"{title}: no nights recorded."
    lines = [
        f"{title}: {result.nights} nights",
        _stats_line("bedtime", result.bedtime, _clock),
        _stats_line("wake-up", result.wake_time, _clock),
        _stats_line("duration", result.duration, _span),
    ]
    if result.jet_lag is None:
        lines.append("weekend jet lag: needs a week with both weekday and weekend nights")
    else:
        lines.append(
            _stats_line(f"weekend jet lag ({result.jet_lag.count} weeks)", result.jet_lag, _signed_span)
        )
    return "\n".join(lines)


def nights_text(user: User, first: dt.date, last: dt.date, tag: str = "") -> str:
    """Return the individual sleep records of a period as compact text for an AI agent."""
    zone = timezone.get_current_timezone()
    records = list(records_between(user, first, last, tag)[: MAX_TEXT_NIGHTS + 1])
    if not records:
        return f"No sleep recorded from {first} to {last}."
    lines = ["wake date, asleep-awake, duration"]
    for record in records[:MAX_TEXT_NIGHTS]:
        start, end = record.start.astimezone(zone), record.end.astimezone(zone)
        extras = [f"rating {record.rating:g}"] if record.rating is not None else []
        extras += [str(tag_) for tag_ in record.tags.all()]
        hours = record.duration.total_seconds() / 3600
        lines.append(" ".join([f"{end:%Y-%m-%d %a} {start:%H:%M}-{end:%H:%M} {_span(hours)}", *extras]))
    if len(records) > MAX_TEXT_NIGHTS:
        lines.append("(more not shown; ask for a shorter period, or use sleep_summary)")
    return "\n".join(lines)


def _clock_hours(moment: dt.datetime) -> float:
    return moment.hour + moment.minute / 60 + moment.second / 3600


def _span(hours: float) -> str:
    minutes = round(abs(hours) * 60)
    return f"{minutes // 60}:{minutes % 60:02d}"


def _signed_span(hours: float) -> str:
    return ("-" if round(hours * 60) < 0 else "+") + _span(hours)


def _clock(hours: float) -> str:
    minutes = round(hours * 60) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _stats_line(label: str, stats: Stats, show: object) -> str:
    assert callable(show)  # noqa: S101 - a formatter from this module
    return (
        f"{label}: mean {show(stats.mean)}, median {show(stats.median)}, "
        f"range {show(stats.minimum)} to {show(stats.maximum)}, sd {_span(stats.std)}"
    )
