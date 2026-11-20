"""MCP tools for sleep."""

import datetime as dt
from collections.abc import Callable

from django.utils import timezone

from apps.accounts.models import Feature, User
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool
from apps.sleep import services

DEFAULT_DAYS = 30


def _for_period(render: Callable[[User, dt.date, dt.date, str], str], start: str, end: str, tag: str) -> str:
    try:
        last = dt.date.fromisoformat(end) if end else timezone.localdate()
        first = dt.date.fromisoformat(start) if start else last - dt.timedelta(days=DEFAULT_DAYS - 1)
    except ValueError:
        return "Invalid date. Use YYYY-MM-DD."
    if first > last:
        return "The start must not be after the end."
    return render(current_user(), first, last, tag)


@nexus_tool(Feature.SLEEP)
def sleep_summary(start: str = "", end: str = "", tag: str = "") -> str:
    """Sleep statistics for wake dates start..end (YYYY-MM-DD), default the last 30 days."""
    return _for_period(services.summary_text, start, end, tag)


@nexus_tool(Feature.SLEEP)
def sleep_nights(start: str = "", end: str = "", tag: str = "") -> str:
    """Individual sleep records for wake dates start..end (YYYY-MM-DD), default the last 30 days."""
    return _for_period(services.nights_text, start, end, tag)
