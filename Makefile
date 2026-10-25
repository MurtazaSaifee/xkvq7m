SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help install dev test test-backend test-frontend lint lint-backend lint-frontend gen-types ingest

help: ## List the make targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-16s %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (pnpm) dependencies
	cd backend && uv sync --frozen
	cd frontend && pnpm install --frozen-lockfile

dev: ## Run the API on :8000 (reload) and the Vite dev server on :5173 (proxies /api)
	@trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000 --no-access-log) & \
	(cd frontend && pnpm dev) & \
	wait

test: test-backend test-frontend ## Run all tests

test-backend: ## pytest
	cd backend && uv run pytest

test-frontend: ## vitest
	cd frontend && pnpm test

lint: lint-backend lint-frontend ## Run all linters and type checks

lint-backend: ## ruff check, ruff format --check, pyright
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyright

lint-frontend: ## eslint, tsc
	cd frontend && pnpm lint && pnpm typecheck

ingest: ## Fetch Elexon data for the fixed window and rebuild data/snapshot.duckdb (needs network)
	cd backend && uv run python -m app.ingestion --output ../data/snapshot.duckdb

gen-types: ## Regenerate the OpenAPI document and the frontend API types
	cd backend && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > ../frontend/src/api/openapi.json
	cd frontend && pnpm exec openapi-typescript src/api/openapi.json -o src/api/schema.ts
