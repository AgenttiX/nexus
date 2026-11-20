"""Fetching and reading iCalendar data."""

import datetime as dt
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import icalendar
import recurring_ical_events
import x_wr_timezone
from django.core.exceptions import ValidationError
from django.utils import timezone

TIMEOUT_SECONDS = 30
MAX_BYTES = 20 * 1024 * 1024
FIELD_LIMIT = 500


@dataclass(frozen=True)
class ParsedEvent:
    """One occurrence of an event, with times in UTC."""

    uid: str
    start: dt.datetime
    end: dt.datetime
    all_day: bool
    title: str
    description: str
    location: str


def validate_url(url: str) -> None:
    """Allow only addresses that are safe for the server to fetch.

    The address comes from a user and is fetched by the server, so it must not
    be able to reach services inside the server's own network: it has to use
    https and resolve only to public addresses.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        msg = "The address must start with https://."
        raise ValidationError(msg)
    try:
        addresses = resolve_host(parts.hostname, parts.port or 443)
    except OSError as error:
        msg = "The host of the address could not be found."
        raise ValidationError(msg) from error
    if not all(ipaddress.ip_address(address).is_global for address in addresses):
        msg = "The address must point to a public server."
        raise ValidationError(msg)


def resolve_host(hostname: str, port: int) -> list[str]:
    """Return the IP addresses that ``hostname`` resolves to."""
    return [str(sockaddr[0]) for *_, sockaddr in socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)]


def fetch(url: str) -> bytes:
    """Download an iCalendar file. Redirects are not followed, as they would bypass the address check."""
    validate_url(url)
    response = httpx.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=False)
    response.raise_for_status()
    if len(response.content) > MAX_BYTES:
        msg = "The calendar is too large."
        raise ValueError(msg)
    return response.content


def parse(data: bytes, window_start: dt.datetime, window_end: dt.datetime) -> list[ParsedEvent]:
    """Return the occurrences of all events between two moments, with recurrences expanded."""
    calendar = icalendar.Calendar.from_ical(data)
    # Google Calendar gives the time zone in X-WR-TIMEZONE instead of on each event.
    calendar = x_wr_timezone.to_standard(calendar)
    events: list[ParsedEvent] = []
    for component in recurring_ical_events.of(calendar).between(window_start, window_end):
        start = component.decoded("DTSTART")
        end = component.decoded("DTEND", start)
        all_day = not isinstance(start, dt.datetime)
        events.append(
            ParsedEvent(
                uid=str(component.get("UID", ""))[:FIELD_LIMIT],
                start=_to_utc(start),
                end=_to_utc(end),
                all_day=all_day,
                title=str(component.get("SUMMARY", ""))[:FIELD_LIMIT],
                description=str(component.get("DESCRIPTION", "")),
                location=str(component.get("LOCATION", ""))[:FIELD_LIMIT],
            ),
        )
    return events


def _to_utc(value: dt.date | dt.datetime) -> dt.datetime:
    """Return ``value`` as an aware UTC time. Dates and times without a zone are taken as local."""
    if not isinstance(value, dt.datetime):
        value = dt.datetime.combine(value, dt.time.min)
    if value.tzinfo is None:
        value = timezone.make_aware(value)
    return value.astimezone(dt.UTC)
