# syntax=docker/dockerfile:1
# Build from the repository root:
#   docker build --file backend/Dockerfile --tag nexus .

FROM node:26-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-alpine AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev

FROM python:3.14-alpine
RUN addgroup -S -g 10001 nexus && adduser -S -u 10001 -G nexus nexus
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=nexus.settings.prod \
    FRONTEND_DIR=/app/frontend
COPY --from=build /app/.venv /app/.venv
COPY backend/apps ./apps
COPY backend/nexus ./nexus
COPY backend/manage.py ./
COPY --from=frontend /frontend/dist ./frontend
# collectstatic needs importable settings; these placeholder values are not kept in the image.
RUN DJANGO_SECRET_KEY=build FIELD_ENCRYPTION_SALT=build DJANGO_ALLOWED_HOSTS=build POSTGRES_PASSWORD=build \
    OIDC_CLIENT_ID=build OIDC_CLIENT_SECRET=build OIDC_SERVER_URL=https://build.invalid/ \
    python manage.py collectstatic --noinput
USER nexus
EXPOSE 8000
CMD ["gunicorn", "nexus.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "--access-logfile", "-"]
