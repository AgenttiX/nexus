"""Settings for the test suite: no Redis, no network, fast hashing."""

from nexus.settings.dev import *  # noqa: F403

DEBUG = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Fixed, so that tests of local times do not depend on the environment.
TIME_ZONE = "Europe/Helsinki"

LITELLM_BASE_URL = "http://litellm.test/v1"
LLM_DEFAULT_MODEL = "test-model"

OIDC_MOBILE_CLIENT_ID = "nexus-android"
OIDC_MOBILE_ISSUER = "https://auth.test/application/o/nexus-android/"
CORS_ALLOWED_ORIGINS = ["https://localhost"]
