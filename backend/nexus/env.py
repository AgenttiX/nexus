"""Helpers for reading configuration from environment variables."""

import os


def env(name: str, default: str | None = None) -> str:
    """Return an environment variable, or fail loudly when it is required and missing."""
    value = os.environ.get(name, default)
    if value is None:
        msg = f"Environment variable {name} is required."
        raise RuntimeError(msg)
    return value


def env_list(name: str, default: str = "") -> list[str]:
    """Return a comma-separated environment variable as a list of non-empty items."""
    return [item.strip() for item in env(name, default).split(",") if item.strip()]
