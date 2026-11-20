"""ASGI entry point of the MCP server, served by Uvicorn in the ``mcp`` container."""

import os

import django
from django.utils.module_loading import autodiscover_modules

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus.settings.prod")
django.setup()

from apps.mcp_server.server import mcp  # noqa: E402

# Each feature app registers its tools in its ``mcp`` module.
autodiscover_modules("mcp")

# Stateless, with plain JSON responses: every request stands alone, which suits a
# server whose tools only read and return data.
application = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)
