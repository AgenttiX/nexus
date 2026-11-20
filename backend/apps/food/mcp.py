"""MCP tools for restaurant menus."""

import datetime as dt

from django.utils import timezone

from apps.accounts.models import Feature
from apps.food import services
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool


@nexus_tool(Feature.FOOD)
def food_menu(date: str = "", restaurant: str = "") -> str:
    """UniCafe lunch menus for a date (YYYY-MM-DD, default today), for favourites or a named restaurant."""
    try:
        day = dt.date.fromisoformat(date) if date else timezone.localdate()
    except ValueError:
        return f"Invalid date {date!r}. Use YYYY-MM-DD."
    return services.menu_text(current_user(), day, restaurant)
