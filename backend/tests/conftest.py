"""Shared fixtures."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


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
