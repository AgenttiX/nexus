"""App configuration for the MCP server."""

from django.apps import AppConfig


class McpServerConfig(AppConfig):
    """The MCP server through which AI agents read a user's data."""

    name = "apps.mcp_server"
