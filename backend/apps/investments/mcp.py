"""MCP tools for investments."""

from apps.accounts.models import Feature
from apps.investments import services
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool

MAX_DAYS = 365


@nexus_tool(Feature.INVESTMENTS)
def portfolio() -> str:
    """Show the user's investment holdings with latest prices, values in euros and gains."""
    return services.portfolio_text(current_user())


@nexus_tool(Feature.INVESTMENTS)
def asset_prices(symbol: str, days: int = 30) -> str:
    """Daily closing prices of one asset (by its symbol in the portfolio) for the last days, at most 365."""
    return services.prices_text(symbol, min(max(days, 1), MAX_DAYS))
