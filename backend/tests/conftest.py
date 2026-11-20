"""Shared fixtures."""

from collections.abc import Iterator

import pytest
from django.utils.module_loading import autodiscover_modules
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import User
from apps.mcp_server.server import mcp

# Register the MCP tools of every app, as the MCP server's entry point does.
autodiscover_modules("mcp")


@pytest.fixture
def user(db: None) -> User:
    """A regular user."""
    return User.objects.create_user(username="alice", email="alice@example.com")


@pytest.fixture
def api_client() -> APIClient:
    """An anonymous API client."""
    return APIClient()


@pytest.fixture
def user_client(user: User) -> APIClient:
    """An API client signed in as ``user``."""
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def other_user(db: None) -> User:
    """A second user, who must never see the data of ``user``."""
    return User.objects.create_user(username="bob")


@pytest.fixture
def other_client(other_user: User) -> APIClient:
    """An API client signed in as ``other_user``."""
    client = APIClient()
    client.force_authenticate(other_user)
    return client


@pytest.fixture
def server() -> Iterator[TestClient]:
    """The MCP server. Tests using it need ``django_db(transaction=True)``."""
    app = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)
    with TestClient(app) as client:
        yield client
