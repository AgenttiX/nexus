"""MCP tools for personal finances."""

import datetime as dt
from collections.abc import Callable

from django.utils import timezone

from apps.accounts.models import Feature, User
from apps.finance import services
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool

DEFAULT_DAYS = 30


def period(start: str, end: str, render: Callable[[User, dt.date, dt.date], str]) -> str:
    """Call ``render`` for the period that a tool was asked for, or explain what is wrong with it."""
    try:
        last = dt.date.fromisoformat(end) if end else timezone.localdate()
        first = dt.date.fromisoformat(start) if start else last - dt.timedelta(days=DEFAULT_DAYS - 1)
    except ValueError:
        return "Invalid date. Use YYYY-MM-DD."
    if first > last:
        return "The start must not be after the end."
    return render(current_user(), first, last)


@nexus_tool(Feature.FINANCE)
def finance_summary(start: str = "", end: str = "") -> str:
    """Income and expenses by category and month between two dates (YYYY-MM-DD), default the last 30 days."""
    return period(start, end, services.summary_text)


@nexus_tool(Feature.FINANCE)
def transactions(start: str = "", end: str = "", search: str = "") -> str:
    """Bank transactions between two dates (default the last 30 days), optionally matching a search text."""
    return period(start, end, lambda user, first, last: services.transactions_text(user, first, last, search))
