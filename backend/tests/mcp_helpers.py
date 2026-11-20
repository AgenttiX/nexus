"""Helpers for talking to the MCP server in tests, over its real HTTP interface."""

from typing import Any

from starlette.testclient import TestClient

from apps.accounts.models import AgentToken, User


def rpc(server: TestClient, token: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = server.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def tool_names(server: TestClient, token: str) -> set[str]:
    return {tool["name"] for tool in rpc(server, token, "tools/list")["result"]["tools"]}


def call(
    server: TestClient, token: str, name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    return rpc(server, token, "tools/call", {"name": name, "arguments": arguments or {}})


def text(result: dict[str, Any]) -> str:
    return result["result"]["content"][0]["text"]


def token_for(user: User, scopes: dict[str, str]) -> str:
    return AgentToken.objects.create_token(user, "assistant", scopes)[1]
