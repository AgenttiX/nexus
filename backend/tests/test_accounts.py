"""Tests for the accounts app."""

from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import User


def test_me_requires_login(api_client: APIClient) -> None:
    assert api_client.get("/api/me/").status_code == 403


def test_me_returns_current_user(user_client: APIClient, user: User) -> None:
    response = user_client.get("/api/me/")
    assert response.status_code == 200
    assert response.json() == {
        "id": user.pk,
        "username": "alice",
        "first_name": "",
        "last_name": "",
        "email": "alice@example.com",
    }


def test_login_goes_to_authentik_only() -> None:
    assert settings.SOCIALACCOUNT_ONLY is True
    assert settings.LOGIN_URL == "/accounts/oidc/authentik/login/"
