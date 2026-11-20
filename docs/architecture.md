# Architecture

## Stack

| Area | Choice |
|---|---|
| Backend | Python 3.14, Django 6.1, PostgreSQL, psycopg 3 |
| API | Django REST Framework, django-filter, drf-spectacular (REST only) |
| Web server | Gunicorn; WhiteNoise serves static files and the built web interface |
| Background tasks | Celery with Redis as broker and cache |
| MCP server | FastMCP over Streamable HTTP, in its own container |
| Authentication | Authentik (OIDC) with a passkey-only login flow |
| LLM access | `openai` SDK against a LiteLLM proxy |
| Web interface | React, Vite, TypeScript, TanStack Query, Tailwind CSS, plotly.js |
| Android app | The web interface wrapped with Capacitor (minimum API 35, target API 37) |
| Tooling | uv, ruff, pyrefly, pytest, prek, Sphinx |
| Deployment | Docker Compose behind an external Nginx; images built by GitHub Actions |

## Repository layout

```text
backend/               Django project
  nexus/               settings, URLs, WSGI and Celery entry points
  apps/core/           building blocks shared by all features
  apps/accounts/       users, Authentik login, agent tokens
  apps/<feature>/      one app per feature
  tests/
frontend/              React web interface
  android/             Capacitor Android project
authentik/blueprints/  passkey policy and OIDC provider as Authentik blueprints
nginx/                 configuration for the external Nginx
skills/                Agent Skills that use the MCP server
docs/                  this documentation
```

## Feature apps

Every feature is a Django app with the same parts:

`models.py`
: Data. Models that belong to a user inherit a common base with a `user`
  foreign key.

`services.py`
: Queries and statistics. Every function takes the user whose data it reads,
  so that the REST API and the MCP server share one implementation and one
  place where access is decided.

`api.py`
: REST endpoints for the web interface and the Android app.

`tasks.py`
: Celery tasks for fetching and importing.

`mcp.py`
: MCP tools, which call the same services.

## Containers

| Service | Purpose | Published port |
|---|---|---|
| `web` | Gunicorn: API (also for the Android app), admin, login, web interface | `WEB_PORT` (8000) |
| `mcp` | MCP server for agents | `MCP_PORT` (8001) |
| `worker`, `beat` | Celery worker and scheduler | |
| `migrate` | Applies database migrations, then exits | |
| `db`, `redis` | PostgreSQL and Redis, on an internal network only | |
| `authentik-server`, `authentik-worker`, `authentik-db` | Authentik and its own database | `AUTHENTIK_PORT` (9000) |
| `wud` | What's Up Docker, optional (`--profile wud`) | 3080 |

The backend containers run as an unprivileged user with a read-only root file
system and no Linux capabilities. Databases and Redis are attached only to
networks without a route to the outside.

## Decisions worth knowing

- **Periodic tasks are declared in code** (`CELERY_BEAT_SCHEDULE`).
  django-celery-beat does not support Django 6.1 yet.
- **Sleep statistics use numpy directly**; pandas is present only because
  `yfinance` returns its data in it.
- **Money is stored as decimals with a currency code**, not with django-money,
  whose py-moneyed dependency has not been released since 2022.
- **rest-pandas is not used**: it has had no release since 2019.
- **django-rest-framework-mcp is not used**: it is an alpha that does not
  support current Django. FastMCP is used instead.
- **Yle's public API is not used**: it no longer offers articles. Yle news
  comes from its RSS feed and article pages.
- **The Guardian's API is not used** either: its RSS feed and article pages
  give the same content without an API key.
- **Parallel article summaries run as concurrent requests inside one task**,
  not as separate Celery tasks, which would need a result backend.
- **HS, Aamulehti and Kauppalehti** contribute titles and leads only, as their
  articles are for subscribers.
