# Development

## Setup

```bash
docker compose -f compose.dev.yaml up -d   # PostgreSQL and Redis
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server proxies `/api`, `/accounts` and `/admin` to Django.

Install the Git hooks once with `prek install`.

## Checks

| Check | Command (in `backend/`) |
|---|---|
| Lint and format | `uv run ruff check .` and `uv run ruff format .` |
| Types | `uv run pyrefly check` |
| Tests, with 100 % coverage required | `uv run pytest` |
| API schema | `uv run python manage.py spectacular --validate --fail-on-warn` |
| Documentation | `uv run sphinx-build -W ../docs ../docs/_build` |

| Check | Command (in `frontend/`) |
|---|---|
| Lint | `npm run lint` |
| Tests, with 100 % coverage required | `npm test` |
| Types and build | `npm run build` |

## Rules

- Type annotations and tests are required for all code. Exclusions are listed
  in `backend/pyproject.toml`.
- Before writing new functionality, look for a maintained library with a
  licence compatible with MIT.
- The repository is public. Keep hostnames, secrets and personal data in
  `.env`, never in committed files.

## Android

```bash
cd frontend
npm run android:sync
cd android
./gradlew assembleDebug
```
