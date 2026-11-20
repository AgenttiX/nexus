"""Tests for the Android app's access: bearer tokens from Authentik, the config endpoint and CORS."""

import time
from types import SimpleNamespace

import jwt
import pytest
from allauth.socialaccount.models import SocialAccount
from cryptography.hazmat.primitives.asymmetric import rsa
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts import authentication
from apps.accounts.models import User

ISSUER = "https://auth.test/application/o/nexus-android/"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def signing_keys(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Authentik's published keys are ``KEY``. Returns the JWKS addresses that were asked for."""
    asked: list[str] = []

    def client(url: str) -> SimpleNamespace:
        asked.append(url)
        return SimpleNamespace(get_signing_key_from_jwt=lambda token: KEY.public_key())

    monkeypatch.setattr(authentication, "jwks_client", client)
    return asked


def token(key: rsa.RSAPrivateKey = KEY, **claims: object) -> str:
    payload = {
        "iss": ISSUER,
        "aud": "nexus-android",
        "sub": "subject-1",
        "exp": int(time.time()) + 300,
        "preferred_username": "alice",
        "email": "alice@example.com",
        **claims,
    }
    return jwt.encode(
        {name: value for name, value in payload.items() if value is not None}, key, algorithm="RS256"
    )


def me(api_client: APIClient, bearer: str) -> tuple[int, dict[str, object]]:
    response = api_client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {bearer}")
    return response.status_code, response.json()


def test_valid_token_signs_in_and_creates_the_user_once(
    db: None, api_client: APIClient, signing_keys: list[str]
) -> None:
    status, body = me(api_client, token())
    assert (status, body["username"], body["email"]) == (200, "alice", "alice@example.com")
    assert me(api_client, token())[1]["id"] == body["id"]
    assert User.objects.count() == 1
    assert SocialAccount.objects.get().uid == "subject-1"
    assert signing_keys[0] == ISSUER + "jwks/"


def test_token_maps_to_the_user_of_the_browser_login(user: User, api_client: APIClient) -> None:
    SocialAccount.objects.create(user=user, provider="authentik", uid="subject-1")
    assert me(api_client, token(preferred_username="someone-else"))[1]["id"] == user.pk
    assert User.objects.count() == 1


def test_new_user_gets_a_free_username(user: User, api_client: APIClient) -> None:
    User.objects.create_user("alice-2")
    assert me(api_client, token())[1]["username"] == "alice-3"
    assert (
        me(api_client, token(sub="subject-2", preferred_username=None, email=None))[1]["username"]
        == "subject-2"
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"aud": "another-app"},
        {"iss": "https://evil.example/"},
        {"exp": int(time.time()) - 3600},
        {"sub": None},
        {"key": OTHER_KEY},
    ],
)
def test_tokens_for_others_or_tampered_tokens_are_refused(
    db: None, api_client: APIClient, bad: dict[str, object]
) -> None:
    key = bad.pop("key", KEY)
    assert isinstance(key, rsa.RSAPrivateKey)
    response = api_client.get("/api/me/", HTTP_AUTHORIZATION=f"Bearer {token(key, **bad)}")
    assert response.status_code == 403
    assert not User.objects.exists()


def test_garbage_and_other_schemes_are_refused(
    db: None, api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def client(url: str) -> SimpleNamespace:
        def fail(value: str) -> None:
            raise jwt.DecodeError

        return SimpleNamespace(get_signing_key_from_jwt=fail)

    monkeypatch.setattr(authentication, "jwks_client", client)
    assert me(api_client, "not-a-token")[0] == 403
    assert api_client.get("/api/me/", HTTP_AUTHORIZATION="Basic abc").status_code == 403
    assert api_client.get("/api/me/", HTTP_AUTHORIZATION="Bearer").status_code == 403
    assert api_client.get("/api/me/").status_code == 403


def test_inactive_users_are_refused(user: User, api_client: APIClient) -> None:
    SocialAccount.objects.create(user=user, provider="authentik", uid="subject-1")
    user.is_active = False
    user.save()
    assert me(api_client, token())[0] == 403


def test_bearer_login_is_off_without_a_mobile_client(
    db: None, api_client: APIClient, settings: Settings
) -> None:
    settings.OIDC_MOBILE_CLIENT_ID = ""
    assert me(api_client, token())[0] == 403
    assert api_client.get("/api/config/").json() == {"oidc_issuer": "", "oidc_client_id": ""}


def test_bearer_requests_can_change_data_without_csrf(db: None) -> None:
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        "/api/finance/categories/",
        {"name": "Food"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token()}",
    )
    assert response.status_code == 201


def test_config_is_public(api_client: APIClient) -> None:
    assert api_client.get("/api/config/").json() == {"oidc_issuer": ISSUER, "oidc_client_id": "nexus-android"}


def test_signing_keys_are_fetched_from_one_cached_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    first = authentication.jwks_client(ISSUER + "jwks/")
    assert first is authentication.jwks_client(ISSUER + "jwks/")
    assert first.uri == ISSUER + "jwks/"


def test_only_the_api_is_open_to_the_app_origin(api_client: APIClient) -> None:
    def allowed(path: str, origin: str) -> str | None:
        response = api_client.get(path, HTTP_ORIGIN=origin)
        response.close()  # the page of the web interface is served as an open file
        return response.headers.get("Access-Control-Allow-Origin")

    assert allowed("/api/config/", "https://localhost") == "https://localhost"
    assert allowed("/api/config/", "https://evil.example") is None
    assert allowed("/sleep", "https://localhost") is None

    preflight = api_client.options(
        "/api/me/",
        HTTP_ORIGIN="https://localhost",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
    )
    assert preflight.status_code == 200
    assert "authorization" in preflight["Access-Control-Allow-Headers"]
    assert "Access-Control-Allow-Credentials" not in preflight
