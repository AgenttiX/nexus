"""MCP tools for time tracking."""

import datetime as dt

from django.utils import timezone

from apps.accounts.models import Feature
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool
from apps.timetracking import services

DEFAULT_DAYS = 7
MAX_DAYS = 92


@nexus_tool(Feature.TIMETRACKING)
def time_summary(start: str = "", end: str = "") -> str:
    """Active device time by app, device and day between two dates (YYYY-MM-DD), default the last 7 days."""
    try:
        last = dt.date.fromisoformat(end) if end else timezone.localdate()
        first = dt.date.fromisoformat(start) if start else last - dt.timedelta(days=DEFAULT_DAYS - 1)
    except ValueError:
        return "Invalid date. Use YYYY-MM-DD."
    if not first <= last < first + dt.timedelta(days=MAX_DAYS):
        return f"The start must not be after the end, and the period at most {MAX_DAYS} days."
    return services.summary_text(current_user(), first, last)
