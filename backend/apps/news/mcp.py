"""MCP tools for news."""

import datetime as dt

from apps.accounts.models import Feature
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool
from apps.news import services


@nexus_tool(Feature.NEWS)
def news_digest(date: str = "", articles: bool = False) -> str:  # noqa: FBT001, FBT002 - a tool argument
    """Show the news digest for a date (YYYY-MM-DD, default the newest), optionally with article links."""
    try:
        day = dt.date.fromisoformat(date) if date else None
    except ValueError:
        return f"Invalid date {date!r}. Use YYYY-MM-DD."
    return services.digest_text(current_user(), day, with_articles=articles)
