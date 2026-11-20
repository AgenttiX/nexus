"""Tests for the MCP server: authentication, scopes and tool visibility."""

import pytest
from asgiref.sync import async_to_sync
from fastmcp.exceptions import AuthorizationError
from starlette.testclient import TestClient

from apps.accounts.models import Access, Feature, User
from apps.mcp_server.auth import AgentTokenVerifier, current_user
from apps.mcp_server.server import mcp, nexus_tool
from tests.mcp_helpers import call, rpc, text, token_for, tool_names

# The server runs tools and token checks in worker threads with their own
# database connections, so these tests need real commits.
pytestmark = pytest.mark.django_db(transaction=True)


@nexus_tool(Feature.SLEEP)
def demo_sleep_read() -> str:
    """Return whose sleep data would be read."""
    return f"sleep of {current_user().username}"


@nexus_tool(Feature.SLEEP, Access.WRITE)
def demo_sleep_write(note: str) -> str:
    """Pretend to write a sleep note."""
    return f"saved {note}"


@nexus_tool(Feature.FINANCE)
def demo_finance_read() -> str:
    """Return whose finance data would be read."""
    return f"finances of {current_user().username}"


def demo_tools(server: TestClient, token: str) -> set[str]:
    """The demo tools and ``whoami`` that a token can see, ignoring the tools of real features."""
    return {name for name in tool_names(server, token) if name.startswith("demo_") or name == "whoami"}


def test_requests_without_a_valid_token_are_refused(server: TestClient, user: User) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert server.post("/mcp", json=body).status_code == 401
    assert server.post("/mcp", json=body, headers={"Authorization": "Bearer nxs_wrong"}).status_code == 401


def test_token_without_scopes_sees_only_whoami(server: TestClient, user: User) -> None:
    token = token_for(user, {})
    assert tool_names(server, token) == {"whoami"}
    assert text(call(server, token, "whoami")) == "user: alice\nscopes: (none)"


def test_read_token_sees_only_read_tools_of_its_feature(server: TestClient, user: User) -> None:
    token = token_for(user, {"sleep": "read"})
    assert demo_tools(server, token) == {"whoami", "demo_sleep_read"}
    assert text(call(server, token, "demo_sleep_read")) == "sleep of alice"
    assert text(call(server, token, "whoami")) == "user: alice\nscopes: sleep:read"


def test_write_token_sees_read_and_write_tools(server: TestClient, user: User) -> None:
    token = token_for(user, {"sleep": "write"})
    assert demo_tools(server, token) == {"whoami", "demo_sleep_read", "demo_sleep_write"}
    assert text(call(server, token, "demo_sleep_write", {"note": "x"})) == "saved x"


@pytest.mark.parametrize("tool", ["demo_sleep_write", "demo_finance_read"])
def test_tools_outside_the_scopes_cannot_be_called(server: TestClient, user: User, tool: str) -> None:
    token = token_for(user, {"sleep": "read"})
    result = call(server, token, tool, {"note": "x"} if tool == "demo_sleep_write" else {})
    assert "error" in result or result["result"]["isError"] is True
    assert "saved" not in str(result)
    assert "finances of" not in str(result)


def test_each_token_reads_its_own_users_data(server: TestClient, user: User, other_user: User) -> None:
    alice = token_for(user, {"sleep": "read"})
    bob = token_for(other_user, {"sleep": "read"})
    assert text(call(server, alice, "demo_sleep_read")) == "sleep of alice"
    assert text(call(server, bob, "demo_sleep_read")) == "sleep of bob"


def test_tool_definitions_stay_small(server: TestClient, user: User) -> None:
    token = token_for(user, {"sleep": "read"})
    for tool in rpc(server, token, "tools/list")["result"]["tools"]:
        assert "outputSchema" not in tool
        assert "\n" not in tool["description"]
        assert len(tool["description"]) <= 100


def test_verifier_reports_user_scopes_and_expiry(user: User) -> None:
    verify = async_to_sync(AgentTokenVerifier().verify_token)
    access = verify(token_for(user, {"finance": "write"}))
    assert access is not None
    assert access.subject == str(user.pk)
    assert access.scopes == ["finance:read", "finance:write"]
    assert access.expires_at is None
    assert verify("nxs_wrong") is None


def test_current_user_needs_an_authenticated_request() -> None:
    with pytest.raises(AuthorizationError):
        current_user()


def test_asgi_entry_point_serves_the_same_server() -> None:
    from nexus import mcp_asgi  # noqa: PLC0415 - importing it configures Django and builds the app

    assert mcp_asgi.application.state.fastmcp_server is mcp
