"""Tests for the calendars app."""

import datetime as dt
import socket
from pathlib import Path

import httpx
import pytest
import respx
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import AgentToken, User
from apps.calendars import ical, services, tasks
from apps.calendars.models import Calendar, Event
from apps.calendars.signals import calendar_synced
from tests.isolation import assert_hidden_from
from tests.mcp_helpers import call, text, token_for, tool_names

ICS = (Path(__file__).parent / "data" / "calendar.ics").read_bytes()
URL = "https://calendar.example.com/private/basic.ics"
UTC = dt.UTC
WINDOW = (dt.datetime(2026, 11, 1, tzinfo=UTC), dt.datetime(2026, 12, 31, tzinfo=UTC))


def resolves_to(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    monkeypatch.setattr(ical, "resolve_host", lambda hostname, port: [address])


@pytest.fixture(autouse=True)
def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every hostname resolves to a public address, without touching the network."""
    resolves_to(monkeypatch, "93.184.215.14")


@pytest.fixture
def calendar(user: User) -> Calendar:
    return Calendar.objects.create(user=user, name="Work", url=URL)


@pytest.fixture
def synced(calendar: Calendar) -> Calendar:
    """A calendar holding the events of the fixture file."""
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, content=ICS))
        assert services.sync_calendar(calendar)
    return calendar


# Address checks


@pytest.mark.parametrize(
    "url", ["http://calendar.example.com/a.ics", "file:///etc/passwd", "https://", "webcal://x/y"]
)
def test_only_https_addresses_are_accepted(url: str) -> None:
    with pytest.raises(ValidationError, match="https"):
        ical.validate_url(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.20.25", "169.254.169.254", "::1"])
def test_addresses_inside_the_network_are_refused(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    resolves_to(monkeypatch, address)
    with pytest.raises(ValidationError, match="public"):
        ical.validate_url(URL)


def test_unknown_hosts_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise socket.gaierror

    monkeypatch.setattr(ical, "resolve_host", fail)
    with pytest.raises(ValidationError, match="could not be found"):
        ical.validate_url(URL)


def test_hosts_are_resolved_with_the_system_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    assert ical.resolve_host("127.0.0.1", 443) == ["127.0.0.1"]


@respx.mock
def test_fetch_does_not_follow_redirects() -> None:
    respx.get(URL).mock(return_value=httpx.Response(302, headers={"Location": "https://internal.example/"}))
    with pytest.raises(httpx.HTTPStatusError):
        ical.fetch(URL)


@respx.mock
def test_fetch_refuses_huge_calendars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ical, "MAX_BYTES", 10)
    respx.get(URL).mock(return_value=httpx.Response(200, content=ICS))
    with pytest.raises(ValueError, match="too large"):
        ical.fetch(URL)


# Parsing


def test_parse_expands_recurrences_and_converts_times() -> None:
    events = {(event.uid, event.start): event for event in ical.parse(ICS, *WINDOW)}
    assert sorted(events) == [
        ("allday-1", dt.datetime(2026, 11, 18, 22, 0, tzinfo=UTC)),
        ("floating-1", dt.datetime(2026, 11, 18, 10, 0, tzinfo=UTC)),
        ("meeting-1", dt.datetime(2026, 11, 16, 8, 0, tzinfo=UTC)),
        ("weekly-1", dt.datetime(2026, 11, 17, 16, 0, tzinfo=UTC)),
        ("weekly-1", dt.datetime(2026, 12, 1, 16, 0, tzinfo=UTC)),
    ]
    meeting = events["meeting-1", dt.datetime(2026, 11, 16, 8, 0, tzinfo=UTC)]
    assert (meeting.title, meeting.location, meeting.description) == ("Planning meeting", "Room 1", "Agenda")
    assert meeting.end == dt.datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    assert not meeting.all_day

    holiday = events["allday-1", dt.datetime(2026, 11, 18, 22, 0, tzinfo=UTC)]
    assert holiday.all_day
    assert holiday.end == dt.datetime(2026, 11, 19, 22, 0, tzinfo=UTC)

    floating = events["floating-1", dt.datetime(2026, 11, 18, 10, 0, tzinfo=UTC)]
    assert (floating.title, floating.end) == ("", floating.start)


def test_parse_keeps_only_the_window() -> None:
    window = (dt.datetime(2026, 11, 16, tzinfo=UTC), dt.datetime(2026, 11, 17, tzinfo=UTC))
    assert [event.uid for event in ical.parse(ICS, *window)] == ["meeting-1"]


# Synchronisation


def test_sync_replaces_events_and_announces_it(synced: Calendar) -> None:
    received: list[Calendar] = []

    def listener(calendar: Calendar, **kwargs: object) -> None:
        received.append(calendar)

    calendar_synced.connect(listener)
    stale = Event.objects.create(calendar=synced, uid="stale", start=WINDOW[0], end=WINDOW[0])
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, content=ICS))
        assert services.sync_calendar(synced)
    calendar_synced.disconnect(listener)

    assert received == [synced]
    assert synced.events.count() == 5
    assert not Event.objects.filter(pk=stale.pk).exists()
    assert synced.synced_at is not None
    assert synced.sync_error == ""
    assert (str(synced), str(synced.events.get(uid="meeting-1"))) == ("Work", "Planning meeting")


@respx.mock
def test_failed_sync_keeps_events_and_hides_the_address(synced: Calendar) -> None:
    respx.get(URL).mock(return_value=httpx.Response(404))
    assert not services.sync_calendar(synced)
    synced.refresh_from_db()
    assert synced.events.count() == 5
    assert synced.sync_error == "HTTPStatusError"
    assert "example.com" not in synced.sync_error


def test_address_is_encrypted_in_the_database(calendar: Calendar) -> None:
    stored = (
        Calendar.objects.filter(pk=calendar.pk).extra(select={"raw": "url"}).values_list("raw", flat=True)[0]
    )
    assert "example.com" not in stored
    assert Calendar.objects.get(pk=calendar.pk).url == URL


@respx.mock
def test_tasks_sync_one_or_all_calendars(calendar: Calendar) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, content=ICS))
    assert tasks.sync_calendar.apply(args=(calendar.pk,)).get() is True
    assert tasks.sync_calendar.apply(args=(0,)).get() is False
    assert tasks.sync_all_calendars.apply().get() == 1
    assert route.call_count == 2


# REST API


def test_calendar_api_requires_login(api_client: APIClient) -> None:
    assert api_client.get("/api/calendars/calendars/").status_code == 403
    assert api_client.get("/api/calendars/events/").status_code == 403


@respx.mock
def test_calendar_can_be_created_updated_and_synced(user_client: APIClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, content=ICS))
    created = user_client.post("/api/calendars/calendars/", {"name": "Work", "url": URL}, format="json")
    assert created.status_code == 201
    assert "url" not in created.json()
    pk = created.json()["id"]
    assert Event.objects.filter(calendar_id=pk).count() == 5

    renamed = user_client.patch(f"/api/calendars/calendars/{pk}/", {"name": "Job"}, format="json")
    assert (renamed.status_code, renamed.json()["name"]) == (200, "Job")
    assert user_client.post(f"/api/calendars/calendars/{pk}/sync/").status_code == 202
    assert route.call_count == 3
    assert user_client.get("/api/calendars/calendars/").json()[0]["sync_error"] == ""


def test_calendar_api_rejects_bad_input(
    user_client: APIClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    Calendar.objects.create(user=user, name="Sleep", url=URL, is_sleep=True)

    def post(**data: object) -> tuple[int, list[str]]:
        response = user_client.post(
            "/api/calendars/calendars/", {"name": "New", "url": URL, **data}, format="json"
        )
        return response.status_code, list(response.json())

    assert post(name="Sleep") == (400, ["name"])
    assert post(is_sleep=True) == (400, ["is_sleep"])
    assert post(color="blue") == (400, ["color"])
    assert post(url="http://calendar.example.com/") == (400, ["url"])
    resolves_to(monkeypatch, "192.168.20.25")
    assert post() == (400, ["url"])
    assert Calendar.objects.count() == 1


def test_sleep_calendar_can_be_edited_without_clashing_with_itself(
    user_client: APIClient, user: User
) -> None:
    sleep = Calendar.objects.create(user=user, name="Sleep", url=URL, is_sleep=True)
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(500))
        response = user_client.patch(
            f"/api/calendars/calendars/{sleep.pk}/",
            {"name": "Sleep", "is_sleep": True, "sleep_as_android": True},
            format="json",
        )
    assert response.status_code == 200
    assert response.json()["sleep_as_android"] is True


def test_calendars_are_hidden_from_other_users(calendar: Calendar, other_client: APIClient) -> None:
    assert_hidden_from(other_client, "/api/calendars/calendars/", calendar.pk)
    assert other_client.post(f"/api/calendars/calendars/{calendar.pk}/sync/").status_code == 404
    assert Calendar.objects.filter(pk=calendar.pk).exists()


def test_events_api_returns_the_period_for_the_owner_only(
    synced: Calendar,
    user_client: APIClient,
    other_client: APIClient,
) -> None:
    period = {"start": "2026-11-16T00:00:00Z", "end": "2026-11-18T00:00:00Z"}
    events = user_client.get("/api/calendars/events/", period).json()
    assert [(event["title"], event["calendar"]) for event in events] == [
        ("Planning meeting", synced.pk),
        ("Choir", synced.pk),
    ]
    assert other_client.get("/api/calendars/events/", period).json() == []


def test_events_api_needs_a_valid_period(user_client: APIClient) -> None:
    assert user_client.get("/api/calendars/events/").status_code == 400
    backwards = {"start": "2026-11-18T00:00:00Z", "end": "2026-11-16T00:00:00Z"}
    assert user_client.get("/api/calendars/events/", backwards).status_code == 400


def test_sleep_calendar_events_are_not_listed_as_events(synced: Calendar, user: User) -> None:
    Calendar.objects.filter(pk=synced.pk).update(is_sleep=True)
    assert not services.events_between(user, *WINDOW).exists()


# MCP


def test_events_text_groups_events_by_day(synced: Calendar, user: User) -> None:
    noon = dt.datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
    Event.objects.create(
        calendar=synced, uid="lunch", start=noon, end=noon + dt.timedelta(minutes=30), title="Lunch"
    )
    assert services.events_text(user, dt.date(2026, 11, 16), dt.date(2026, 11, 19)) == (
        "Mon 2026-11-16\n"
        "- 10:00-11:00 Planning meeting @ Room 1 [Work]\n"
        "- 12:00-12:30 Lunch [Work]\n"
        "Tue 2026-11-17\n"
        "- 18:00-19:00 Choir [Work]\n"
        "Wed 2026-11-18\n"
        "- 12:00-12:00 (no title) [Work]\n"
        "Thu 2026-11-19\n"
        "- all day Holiday [Work]"
    )


def test_events_text_reports_empty_periods_and_truncation(
    synced: Calendar,
    user: User,
    other_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    day = dt.date(2026, 11, 16)
    assert services.events_text(other_user, day, day) == "No events from 2026-11-16 to 2026-11-16."
    monkeypatch.setattr(services, "MAX_TEXT_EVENTS", 1)
    lines = services.events_text(user, day, dt.date(2026, 11, 19)).splitlines()
    assert len(lines) == 3
    assert lines[-1].startswith("(more events not shown")


@pytest.mark.django_db(transaction=True)
def test_calendar_tool_needs_its_scope_and_checks_dates(server: TestClient, user: User) -> None:
    assert "calendar_events" not in tool_names(server, token_for(user, {"food": "read"}))
    token = AgentToken.objects.create_token(user, "calendar agent", {"calendars": "read"})[1]
    assert "calendar_events" in tool_names(server, token)
    assert text(call(server, token, "calendar_events", {"start": "2026-11-16"})) == (
        "No events from 2026-11-16 to 2026-11-22."
    )
    assert text(call(server, token, "calendar_events")).startswith("No events from ")
    assert (
        text(call(server, token, "calendar_events", {"start": "16.11."})) == "Invalid date. Use YYYY-MM-DD."
    )
    for end in ("2026-11-15", "2027-11-16"):
        result = text(call(server, token, "calendar_events", {"start": "2026-11-16", "end": end}))
        assert result.startswith("The end must be on or after the start")
