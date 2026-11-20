"""Local development settings. Never use these in a deployment."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "insecure-development-key")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
os.environ.setdefault("POSTGRES_PASSWORD", "nexus")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("OIDC_CLIENT_ID", "nexus")
os.environ.setdefault("OIDC_CLIENT_SECRET", "insecure-development-secret")
os.environ.setdefault("OIDC_SERVER_URL", "http://localhost:9000/application/o/nexus/")

from nexus.settings.base import *  # noqa: F403

DEBUG = True
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
