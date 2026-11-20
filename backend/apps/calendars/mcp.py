"""MCP tools for calendars."""

import datetime as dt

from django.utils import timezone

from apps.accounts.models import Feature
from apps.calendars import services
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool

DEFAULT_DAYS = 7
MAX_DAYS = 62


@nexus_tool(Feature.CALENDARS)
def calendar_events(start: str = "", end: str = "") -> str:
    """Calendar events between two dates (YYYY-MM-DD, default today and the six days after it)."""
    try:
        first = dt.date.fromisoformat(start) if start else timezone.localdate()
        last = dt.date.fromisoformat(end) if end else first + dt.timedelta(days=DEFAULT_DAYS - 1)
    except ValueError:
        return "Invalid date. Use YYYY-MM-DD."
    if not first <= last <= first + dt.timedelta(days=MAX_DAYS):
        return f"The end must be on or after the start, and at most {MAX_DAYS} days later."
    return services.events_text(current_user(), first, last)
