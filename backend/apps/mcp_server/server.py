"""The MCP server and the decorator with which feature apps add tools to it.

Tool definitions are sent to the model on every request, and the agents that
use this server run on small local models. Keep tool names short, descriptions
to one line, and results compact. Longer guidance belongs in the Agent Skills
under ``skills/``.
"""

from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.server.auth import require_scopes
from fastmcp.server.dependencies import get_access_token

from apps.accounts.models import Access, Feature, scope
from apps.mcp_server.auth import AgentTokenVerifier, current_user
from apps.mcp_server.db import with_fresh_connection

mcp: FastMCP = FastMCP(
    name="Nexus",
    instructions="Personal data of the user: news, finances, time use, sleep and food.",
    auth=AgentTokenVerifier(),
)


def nexus_tool[**P, R](
    feature: Feature, access: Access = Access.READ
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Register a function as an MCP tool of ``feature``.

    The tool is listed for, and callable by, only those agents whose token has
    the given access to the feature. The function's docstring is the tool
    description that the model sees.
    """

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        mcp.tool(
            with_fresh_connection(function),
            tags={feature.value},
            auth=require_scopes(scope(feature, access)),
            output_schema=None,  # results are compact text; a schema would only cost context
            annotations={"readOnlyHint": access is Access.READ},
        )
        return function

    return decorator


@mcp.tool(annotations={"readOnlyHint": True}, output_schema=None)
@with_fresh_connection
def whoami() -> str:
    """Show whose data this connection can access and with which scopes."""
    user = current_user()
    access_token = get_access_token()
    scopes = access_token.scopes if access_token else []
    return f"user: {user.username}\nscopes: {' '.join(scopes) or '(none)'}"
