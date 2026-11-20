"""Tests for the core app and project plumbing."""

from pathlib import Path

import pytest
from django.http import FileResponse
from django.test import Client
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from nexus import celery_app
from nexus.env import env, env_list


@pytest.mark.django_db
def test_health_is_public(api_client: APIClient) -> None:
    response = api_client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_schema_requires_login(api_client: APIClient) -> None:
    assert api_client.get("/api/schema/").status_code == 403


def test_schema_renders(user_client: APIClient) -> None:
    response = user_client.get("/api/schema/")
    assert response.status_code == 200
    assert "/api/me/" in response.data["paths"]


def test_env_returns_value_or_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_TEST_VALUE", "a, b,,c")
    assert env("NEXUS_TEST_VALUE") == "a, b,,c"
    assert env("NEXUS_TEST_MISSING", "fallback") == "fallback"
    assert env_list("NEXUS_TEST_VALUE") == ["a", "b", "c"]
    assert env_list("NEXUS_TEST_MISSING") == []


def test_env_fails_when_required_value_is_missing() -> None:
    with pytest.raises(RuntimeError, match="NEXUS_TEST_MISSING"):
        env("NEXUS_TEST_MISSING")


def test_celery_uses_django_settings() -> None:
    assert celery_app.main == "nexus"
    assert celery_app.conf.task_always_eager is True


def test_spa_serves_index_for_client_side_routes(client: Client, settings: Settings, tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<title>Nexus</title>")
    settings.FRONTEND_DIR = tmp_path
    response = client.get("/sleep/2026")
    assert response.status_code == 200
    assert isinstance(response, FileResponse)
    assert response.getvalue() == b"<title>Nexus</title>"


def test_spa_is_missing_until_frontend_is_built(client: Client, settings: Settings, tmp_path: Path) -> None:
    settings.FRONTEND_DIR = tmp_path
    assert client.get("/sleep").status_code == 404


def test_unknown_api_paths_are_not_answered_by_the_spa(client: Client) -> None:
    assert client.get("/api/nope/").status_code == 404


def test_spa_rejects_writes(client: Client) -> None:
    assert client.post("/sleep").status_code == 405
