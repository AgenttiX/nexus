"""Authentication of agents by their bearer tokens."""

from asgiref.sync import sync_to_async
from fastmcp.exceptions import AuthorizationError
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.dependencies import get_access_token

from apps.accounts.models import AgentToken, User
from apps.mcp_server.db import with_fresh_connection


class AgentTokenVerifier(TokenVerifier):
    """Accept the bearer tokens that users create for their agents."""

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return the access that ``token`` grants, or ``None`` when it is not valid."""
        agent_token = await sync_to_async(with_fresh_connection(AgentToken.objects.authenticate))(token)
        if agent_token is None:
            return None
        return AccessToken(
            token=token,
            client_id=f"agent-token-{agent_token.pk}",
            scopes=agent_token.scope_strings,
            expires_at=int(agent_token.expires_at.timestamp()) if agent_token.expires_at else None,
            subject=str(agent_token.user.pk),
            claims={"agent": agent_token.name},
        )


def current_user() -> User:
    """Return the user whose data the calling agent may access.

    Every tool gets its user from here and passes it to a service function,
    so an agent can never name the user it wants to read.
    """
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        msg = "Not authenticated."
        raise AuthorizationError(msg)
    return User.objects.get(pk=int(access_token.subject), is_active=True)
