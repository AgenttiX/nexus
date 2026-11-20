"""Tests for the sleep app."""

import datetime as dt
import math
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import AgentToken, User
from apps.calendars import ical
from apps.calendars import services as calendar_services
from apps.calendars.models import Calendar, Event
from apps.sleep import services, sleep_as_android
from apps.sleep.models import SleepRecord, Tag
from apps.sleep.statistics import circular_mean, clock_difference, summarize, summarize_clock
from tests.mcp_helpers import call, text, tool_names

HELSINKI = ZoneInfo("Europe/Helsinki")
URL = "https://calendar.example.com/sleep.ics"
FIRST, LAST = dt.date(2026, 11, 9), dt.date(2026, 11, 15)


def local(day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 11, day, hour, minute, tzinfo=HELSINKI)


def record(user: User, start: dt.datetime, end: dt.datetime, **fields: object) -> SleepRecord:
    return SleepRecord.objects.create(user=user, start=start, end=end, duration=end - start, **fields)


@pytest.fixture
def week(user: User) -> list[SleepRecord]:
    """Four nights and a nap in one week: two nights ending on weekdays, two at the weekend."""
    return [
        record(user, local(9, 23), local(10, 7)),
        record(user, local(10, 23, 30), local(11, 7, 30)),
        record(user, local(11, 14), local(11, 14, 30)),
        record(user, local(14, 1), local(14, 10)),
        record(user, local(15, 0, 30), local(15, 9, 30)),
    ]


# Statistics


def test_ordinary_statistics() -> None:
    stats = summarize([6, 8])
    assert stats is not None
    assert (stats.count, stats.minimum, stats.maximum, stats.mean, stats.median) == (2, 6, 8, 7, 7)
    assert stats.std == pytest.approx(math.sqrt(2))
    assert summarize([]) is None
    single = summarize([7.5])
    assert single is not None
    assert single.std == 0


def test_clock_times_are_averaged_around_midnight() -> None:
    assert circular_mean([23, 1]) == pytest.approx(0, abs=1e-9)
    assert clock_difference(1, 23) == 2
    assert clock_difference(23, 1) == -2
    stats = summarize_clock([23, 1, 0])
    assert stats is not None
    assert stats.mean % 24 == pytest.approx(0, abs=1e-9)
    assert (stats.minimum, stats.maximum) == (pytest.approx(23), pytest.approx(1))
    assert stats.median % 24 == pytest.approx(0, abs=1e-9)
    assert stats.std == pytest.approx(1)
    assert summarize_clock([]) is None


# Summary


def test_summary_of_a_week(user: User, week: list[SleepRecord]) -> None:
    result = services.summary(user, FIRST, LAST)
    assert result.nights == 4
    assert result.bedtime is not None
    assert result.wake_time is not None
    assert result.duration is not None
    assert result.jet_lag is not None
    assert result.bedtime.mean % 24 == pytest.approx(0, abs=1e-9)
    assert (result.bedtime.minimum, result.bedtime.maximum) == (pytest.approx(23), pytest.approx(1))
    assert result.wake_time.mean == pytest.approx(8.5)
    assert (result.duration.mean, result.duration.minimum, result.duration.maximum) == (8.5, 8, 9)
    assert (result.jet_lag.count, result.jet_lag.mean) == (1, pytest.approx(2))


def test_summary_text_of_a_week(user: User, week: list[SleepRecord]) -> None:
    assert services.summary_text(user, FIRST, LAST) == (
        "Sleep 2026-11-09..2026-11-15: 4 nights\n"
        "bedtime: mean 00:00, median 00:00, range 23:00 to 01:00, sd 0:55\n"
        "wake-up: mean 08:30, median 08:30, range 07:00 to 10:00, sd 1:28\n"
        "duration: mean 8:30, median 8:30, range 8:00 to 9:00, sd 0:35\n"
        "weekend jet lag (1 weeks): mean +2:00, median +2:00, range +2:00 to +2:00, sd 0:00"
    )


def test_summary_without_weekend_or_without_nights(user: User, week: list[SleepRecord]) -> None:
    weekdays = services.summary_text(user, FIRST, dt.date(2026, 11, 13))
    assert weekdays.startswith("Sleep 2026-11-09..2026-11-13: 2 nights\n")
    assert weekdays.endswith("weekend jet lag: needs a week with both weekday and weekend nights")
    assert services.summary_text(user, dt.date(2026, 1, 1), dt.date(2026, 1, 2)) == (
        "Sleep 2026-01-01..2026-01-02: no nights recorded."
    )


def test_negative_jet_lag_is_shown_with_its_sign(user: User) -> None:
    record(user, local(10, 1), local(10, 9))
    record(user, local(13, 22), local(14, 6))
    assert "mean -3:00" in services.summary_text(user, FIRST, LAST).splitlines()[-1]


def test_summary_is_per_user(other_user: User, week: list[SleepRecord]) -> None:
    assert services.summary(other_user, FIRST, LAST).nights == 0


def test_records_can_be_filtered_by_tag(user: User, week: list[SleepRecord]) -> None:
    week[0].tags.add(Tag.objects.create(user=user, name="travel"))
    assert list(services.records_between(user, FIRST, LAST, "#Travel")) == [week[0]]
    assert services.summary_text(user, FIRST, LAST, "travel").startswith(
        "Sleep 2026-11-09..2026-11-15 #travel: 1 nights"
    )
    assert str(week[0].tags.get()) == "#travel"
    assert str(week[0]) == "2026-11-09 23:00 - 07:00"


def test_nights_text_lists_records_with_extras(user: User, week: list[SleepRecord]) -> None:
    SleepRecord.objects.filter(pk=week[0].pk).update(rating=4.5)
    week[0].tags.add(Tag.objects.create(user=user, name="travel"))
    assert services.nights_text(user, FIRST, LAST).splitlines()[:4] == [
        "wake date, asleep-awake, duration",
        "2026-11-10 Tue 23:00-07:00 8:00 rating 4.5 #travel",
        "2026-11-11 Wed 23:30-07:30 8:00",
        "2026-11-11 Wed 14:00-14:30 0:30",
    ]


def test_nights_text_reports_empty_periods_and_truncation(
    user: User,
    week: list[SleepRecord],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert services.nights_text(user, dt.date(2026, 1, 1), dt.date(2026, 1, 2)) == (
        "No sleep recorded from 2026-01-01 to 2026-01-02."
    )
    monkeypatch.setattr(services, "MAX_TEXT_NIGHTS", 2)
    lines = services.nights_text(user, FIRST, LAST).splitlines()
    assert len(lines) == 4
    assert lines[-1].startswith("(more not shown")


# Building records from the sleep calendar


def sleep_calendar(user: User, **fields: object) -> Calendar:
    calendar = Calendar.objects.create(user=user, name="Sleep", url=URL, is_sleep=True, **fields)
    Event.objects.create(calendar=calendar, uid="night", start=local(9, 23), end=local(10, 7))
    Event.objects.create(calendar=calendar, uid="empty", start=local(11, 23), end=local(11, 23))
    Event.objects.create(calendar=calendar, uid="day", start=local(12, 0), end=local(13, 0), all_day=True)
    return calendar


def test_records_are_built_from_timed_events_of_the_sleep_calendar(user: User) -> None:
    assert services.rebuild_records(sleep_calendar(user)) == 1
    built = SleepRecord.objects.get()
    assert (built.user, built.start, built.end) == (user, local(9, 23), local(10, 7))
    assert built.duration == dt.timedelta(hours=8)
    assert built.rating is None


def test_sleep_as_android_details_and_tags_are_stored(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    details = sleep_as_android.SleepDetails(
        duration=dt.timedelta(hours=7),
        rating=4.0,
        deep_sleep=0.4,
        cycles=5,
        comment="Slept well #Travel #hotel #travel",
    )
    monkeypatch.setattr(sleep_as_android, "parse", lambda event: details)
    services.rebuild_records(sleep_calendar(user, sleep_as_android=True))
    built = SleepRecord.objects.get()
    assert (built.duration, built.rating, built.deep_sleep, built.cycles) == (
        dt.timedelta(hours=7),
        4.0,
        0.4,
        5,
    )
    assert [tag.name for tag in built.tags.all()] == ["hotel", "travel"]
    assert Tag.objects.for_user(user).count() == 2


def test_sleep_as_android_parser_is_a_placeholder(user: User) -> None:
    calendar = sleep_calendar(user)
    assert sleep_as_android.parse(calendar.events.first()) == sleep_as_android.SleepDetails()  # type: ignore[arg-type]
    assert sleep_as_android.extract_tags("no tags here") == []


def test_tags_are_shared_between_records(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sleep_as_android, "parse", lambda event: sleep_as_android.SleepDetails(comment="#hotel")
    )
    calendar = sleep_calendar(user, sleep_as_android=True)
    Event.objects.create(calendar=calendar, uid="second", start=local(13, 23), end=local(14, 7))
    assert services.rebuild_records(calendar) == 2
    assert Tag.objects.for_user(user).count() == 1
    assert Tag.objects.get().records.count() == 2


def test_records_disappear_when_the_calendar_is_no_longer_for_sleep(user: User) -> None:
    calendar = sleep_calendar(user)
    services.rebuild_records(calendar)
    calendar.is_sleep = False
    calendar.save()
    assert services.rebuild_records(calendar) == 0
    assert not SleepRecord.objects.exists()


def test_other_calendars_do_not_touch_sleep_records(user: User) -> None:
    services.rebuild_records(sleep_calendar(user))
    work = Calendar.objects.create(user=user, name="Work", url=URL)
    assert services.rebuild_records(work) == 1
    assert SleepRecord.objects.count() == 1


@respx.mock
def test_syncing_the_sleep_calendar_rebuilds_records(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ical, "resolve_host", lambda hostname, port: ["93.184.215.14"])
    ics = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//EN\r\nBEGIN:VEVENT\r\nUID:n1\r\n"
        b"DTSTART:20261109T210000Z\r\nDTEND:20261110T050000Z\r\nSUMMARY:Sleep\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    respx.get(URL).mock(return_value=httpx.Response(200, content=ics))
    calendar = Calendar.objects.create(user=user, name="Sleep", url=URL, is_sleep=True)
    assert calendar_services.sync_calendar(calendar)
    assert SleepRecord.objects.for_user(user).get().duration == dt.timedelta(hours=8)


# REST API


def test_sleep_api_requires_login(api_client: APIClient) -> None:
    assert api_client.get("/api/sleep/summary/").status_code == 403
    assert api_client.get("/api/sleep/records/").status_code == 403


def test_sleep_api_needs_a_valid_period(user_client: APIClient) -> None:
    assert user_client.get("/api/sleep/summary/").status_code == 400
    backwards = {"start": "2026-11-15", "end": "2026-11-09"}
    assert user_client.get("/api/sleep/records/", backwards).status_code == 400


def test_summary_api(user_client: APIClient, other_client: APIClient, week: list[SleepRecord]) -> None:
    period = {"start": "2026-11-09", "end": "2026-11-15"}
    summary = user_client.get("/api/sleep/summary/", period).json()
    assert (summary["first"], summary["last"], summary["nights"]) == ("2026-11-09", "2026-11-15", 4)
    assert summary["duration"] == {
        "count": 4,
        "minimum": 8.0,
        "maximum": 9.0,
        "mean": 8.5,
        "median": 8.5,
        "std": pytest.approx(0.5774, abs=1e-4),
    }
    assert summary["jet_lag"]["mean"] == pytest.approx(2)
    empty = other_client.get("/api/sleep/summary/", period).json()
    assert (empty["nights"], empty["bedtime"], empty["jet_lag"]) == (0, None, None)


def test_records_api(
    user: User, user_client: APIClient, other_client: APIClient, week: list[SleepRecord]
) -> None:
    week[0].tags.add(Tag.objects.create(user=user, name="travel"))
    period = {"start": "2026-11-09", "end": "2026-11-15"}
    records = user_client.get("/api/sleep/records/", period).json()
    assert len(records) == 5
    assert (records[0]["duration_hours"], records[0]["tags"], records[0]["rating"]) == (8.0, ["travel"], None)
    assert len(user_client.get("/api/sleep/records/", {**period, "tag": "travel"}).json()) == 1
    assert other_client.get("/api/sleep/records/", period).json() == []


# MCP


@pytest.mark.django_db(transaction=True)
def test_sleep_tools(server: TestClient, user: User) -> None:
    record(user, local(9, 23), local(10, 7))
    token = AgentToken.objects.create_token(user, "sleep agent", {"sleep": "read"})[1]
    assert {"sleep_summary", "sleep_nights"} <= tool_names(server, token)
    period = {"start": "2026-11-09", "end": "2026-11-15"}
    assert text(call(server, token, "sleep_summary", period)).startswith(
        "Sleep 2026-11-09..2026-11-15: 1 nights"
    )
    assert "2026-11-10 Tue 23:00-07:00 8:00" in text(call(server, token, "sleep_nights", period))
    assert text(call(server, token, "sleep_summary")).startswith("Sleep ")
    assert text(call(server, token, "sleep_nights", {"end": "2026-11-10"})).startswith("wake date")
    assert (
        text(call(server, token, "sleep_summary", {"start": "yesterday"})) == "Invalid date. Use YYYY-MM-DD."
    )
    backwards = {"start": "2026-11-15", "end": "2026-11-09"}
    assert text(call(server, token, "sleep_nights", backwards)) == "The start must not be after the end."

    other = User.objects.create_user("carol")
    other_token = AgentToken.objects.create_token(other, "sleep agent", {"sleep": "read"})[1]
    assert text(call(server, other_token, "sleep_summary", period)).endswith("no nights recorded.")
