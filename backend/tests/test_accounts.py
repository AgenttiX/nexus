"""Tests for the accounts app."""

from datetime import timedelta
from io import StringIO

import pytest
from django.conf import settings
from django.contrib.admin.sites import site
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpRequest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import TOKEN_PREFIX, AgentToken, User, validate_scopes
from tests.isolation import assert_hidden_from


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
    assert "csrftoken" in response.cookies


def test_login_goes_to_authentik_only() -> None:
    assert settings.SOCIALACCOUNT_ONLY is True
    assert settings.LOGIN_URL == "/accounts/oidc/authentik/login/"


def test_token_plaintext_is_not_stored(user: User) -> None:
    token, plaintext = AgentToken.objects.create_token(user, "assistant", {"sleep": "read"})
    assert plaintext.startswith(TOKEN_PREFIX)
    assert plaintext not in {token.token_hash, token.hint}
    assert token.hint == plaintext[-4:]
    assert str(token) == "assistant"


def test_authenticate_accepts_only_the_exact_token(user: User) -> None:
    token, plaintext = AgentToken.objects.create_token(user, "assistant", {})
    assert AgentToken.objects.authenticate(plaintext) == token
    assert AgentToken.objects.authenticate(plaintext + "x") is None
    assert AgentToken.objects.authenticate("") is None


def test_authenticate_rejects_expired_tokens(user: User) -> None:
    past = timezone.now() - timedelta(seconds=1)
    _, plaintext = AgentToken.objects.create_token(user, "assistant", {}, expires_at=past)
    assert AgentToken.objects.authenticate(plaintext) is None


def test_authenticate_accepts_tokens_that_expire_later(user: User) -> None:
    future = timezone.now() + timedelta(days=1)
    token, plaintext = AgentToken.objects.create_token(user, "assistant", {}, expires_at=future)
    assert AgentToken.objects.authenticate(plaintext) == token


def test_authenticate_rejects_tokens_of_inactive_users(user: User) -> None:
    _, plaintext = AgentToken.objects.create_token(user, "assistant", {})
    user.is_active = False
    user.save()
    assert AgentToken.objects.authenticate(plaintext) is None


def test_authenticate_records_use_at_most_once_a_minute(user: User) -> None:
    token, plaintext = AgentToken.objects.create_token(user, "assistant", {})
    assert token.last_used_at is None
    first = AgentToken.objects.authenticate(plaintext)
    assert first is not None
    assert first.last_used_at is not None
    second = AgentToken.objects.authenticate(plaintext)
    assert second is not None
    assert second.last_used_at == first.last_used_at
    AgentToken.objects.update(last_used_at=timezone.now() - timedelta(minutes=5))
    third = AgentToken.objects.authenticate(plaintext)
    assert third is not None
    assert third.last_used_at is not None
    assert third.last_used_at > first.last_used_at


def test_write_scope_includes_read(user: User) -> None:
    token, _ = AgentToken.objects.create_token(user, "assistant", {"sleep": "read", "finance": "write"})
    assert token.scope_strings == ["finance:read", "finance:write", "sleep:read"]


@pytest.mark.parametrize("scopes", [["sleep"], {"gardening": "read"}, {"sleep": "admin"}])
def test_invalid_scopes_are_rejected(scopes: object) -> None:
    with pytest.raises(ValidationError):
        validate_scopes(scopes)


def test_create_token_validates_scopes(user: User) -> None:
    with pytest.raises(ValidationError):
        AgentToken.objects.create_token(user, "assistant", {"sleep": "admin"})
    assert not AgentToken.objects.exists()


def test_agent_tokens_require_login(api_client: APIClient) -> None:
    assert api_client.get("/api/agent-tokens/").status_code == 403


def test_token_api_shows_the_secret_only_on_creation(user_client: APIClient) -> None:
    created = user_client.post(
        "/api/agent-tokens/", {"name": "assistant", "scopes": {"sleep": "read"}}, format="json"
    )
    assert created.status_code == 201
    plaintext = created.json()["token"]
    assert AgentToken.objects.authenticate(plaintext) is not None

    listing = user_client.get("/api/agent-tokens/").json()
    assert [(item["name"], item["scopes"], item["hint"]) for item in listing] == [
        ("assistant", {"sleep": "read"}, plaintext[-4:]),
    ]
    assert "token" not in listing[0]

    assert user_client.delete(f"/api/agent-tokens/{created.json()['id']}/").status_code == 204
    assert AgentToken.objects.authenticate(plaintext) is None


def test_token_api_rejects_bad_input(user_client: APIClient, user: User) -> None:
    AgentToken.objects.create_token(user, "assistant", {})
    duplicate = user_client.post("/api/agent-tokens/", {"name": "assistant", "scopes": {}}, format="json")
    assert duplicate.status_code == 400
    bad_scope = user_client.post(
        "/api/agent-tokens/", {"name": "other", "scopes": {"sleep": "admin"}}, format="json"
    )
    assert bad_scope.status_code == 400
    assert AgentToken.objects.count() == 1


def test_tokens_cannot_be_edited(user_client: APIClient, user: User) -> None:
    token, _ = AgentToken.objects.create_token(user, "assistant", {})
    response = user_client.patch(
        f"/api/agent-tokens/{token.pk}/", {"scopes": {"sleep": "write"}}, format="json"
    )
    assert response.status_code == 405


def test_tokens_are_hidden_from_other_users(user: User, other_client: APIClient) -> None:
    token, _ = AgentToken.objects.create_token(user, "assistant", {"sleep": "read"})
    assert_hidden_from(other_client, "/api/agent-tokens/", token.pk)
    assert AgentToken.objects.filter(pk=token.pk).exists()


def test_same_token_name_is_allowed_for_different_users(user: User, other_client: APIClient) -> None:
    AgentToken.objects.create_token(user, "assistant", {})
    response = other_client.post("/api/agent-tokens/", {"name": "assistant", "scopes": {}}, format="json")
    assert response.status_code == 201


def test_tokens_cannot_be_added_in_the_admin() -> None:
    assert site.get_model_admin(AgentToken).has_add_permission(HttpRequest()) is False


def test_command_creates_a_usable_token(user: User) -> None:
    output = StringIO()
    call_command("create_agent_token", "alice", "assistant", "sleep=read", "finance=write", stdout=output)
    token = AgentToken.objects.authenticate(output.getvalue().strip())
    assert token is not None
    assert token.scopes == {"sleep": "read", "finance": "write"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["nobody", "assistant"], "No user named"),
        (["alice", "assistant", "sleep=admin"], "Unknown access level"),
        (["alice", "assistant", "sleep"], "Unknown access level"),
    ],
)
def test_command_reports_bad_input(user: User, arguments: list[str], message: str) -> None:
    with pytest.raises(CommandError, match=message):
        call_command("create_agent_token", *arguments)
    assert not AgentToken.objects.exists()
