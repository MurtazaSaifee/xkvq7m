# syntax=docker/dockerfile:1

# Stage 1: build the React app into static files.
FROM node:22-slim AS frontend
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: the FastAPI app, serving the API and the built frontend.
FROM python:3.12-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    WIND_STATIC_DIR=/app/static
WORKDIR /app

# Dependencies first, so source-only changes reuse this layer.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
RUN uv sync --frozen --no-dev
COPY --from=frontend /frontend/dist ./static

EXPOSE 8000
# Access logging is done by the app's own middleware, so uvicorn's plain-text access log is off.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
