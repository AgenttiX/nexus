"""Settings shared by every environment.

Everything deployment-specific comes from environment variables, because this
repository is public and must not contain private configuration.
"""

from pathlib import Path

from django.utils.csp import CSP

from nexus.env import env, env_list

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env("DJANGO_SECRET_KEY")
# Secrets stored in the database, such as calendar addresses, are encrypted with a key derived
# from SECRET_KEY and this salt. Changing either makes them unreadable, unless the old secret
# key is listed in SECRET_KEY_FALLBACKS.
SALT_KEY = env("FIELD_ENCRYPTION_SALT")
SECRET_KEY_FALLBACKS = env_list("DJANGO_SECRET_KEY_FALLBACKS")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "apps.core",
    "apps.accounts",
    "apps.mcp_server",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    # WhiteNoise answers static files itself, so it sits after the middleware whose
    # response headers those files must also carry.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "nexus.urls"
WSGI_APPLICATION = "nexus.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "nexus"),
        "USER": env("POSTGRES_USER", "nexus"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", "redis://redis:6379")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_URL}/1",
    },
}
CELERY_BROKER_URL = f"{REDIS_URL}/0"
# Periodic tasks are declared here in code. django-celery-beat (schedules in the database)
# does not support Django 6.1 yet.
CELERY_BEAT_SCHEDULE: dict[str, dict[str, object]] = {}
CELERY_TASK_ACKS_LATE = True
CELERY_TIMEZONE = env("TIME_ZONE", "UTC")

# Authentication: every browser login goes through Authentik, which enforces the passkey policy.
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
OIDC_PROVIDER_ID = "authentik"
LOGIN_URL = f"/accounts/oidc/{OIDC_PROVIDER_ID}/login/"
LOGIN_REDIRECT_URL = "/"
SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_PROVIDERS = {
    "openid_connect": {
        "APPS": [
            {
                "provider_id": OIDC_PROVIDER_ID,
                "name": "Authentik",
                "client_id": env("OIDC_CLIENT_ID"),
                "secret": env("OIDC_CLIENT_SECRET"),
                "settings": {"server_url": env("OIDC_SERVER_URL")},
            },
        ],
    },
}

# Optional free demo key of CoinGecko, which raises its rate limit.
COINGECKO_API_KEY = env("COINGECKO_API_KEY", "")

# Language models, reached through the OpenAI-compatible API of a LiteLLM proxy.
LITELLM_BASE_URL = env("LITELLM_BASE_URL", "")
LITELLM_API_KEY = env("LITELLM_API_KEY", "")
LLM_DEFAULT_MODEL = env("LLM_DEFAULT_MODEL", "")
# How many articles are summarised at the same time in the parallel digest mode.
NEWS_PARALLEL_SESSIONS = int(env("NEWS_PARALLEL_SESSIONS", "4"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Nexus API",
    "DESCRIPTION": "REST API of Nexus, a personal intranet.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
}

LANGUAGE_CODE = "en"
# The time zone decides what "today" means, for example for menus and sleep statistics.
TIME_ZONE = env("TIME_ZONE", "UTC")
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# The built single-page application. WhiteNoise serves its asset files from the site root,
# and ``apps.core.views.spa`` answers every page route (including ``/``) with ``index.html``.
FRONTEND_DIR = Path(env("FRONTEND_DIR", str(BASE_DIR.parent / "frontend" / "dist")))
WHITENOISE_ROOT = FRONTEND_DIR

# Security. TLS is terminated by the external Nginx, which forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
SECURE_HSTS_SECONDS = 31536000
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
}
