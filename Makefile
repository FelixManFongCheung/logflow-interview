.DEFAULT_GOAL := help

# Docker Desktop on macOS installs credential helpers outside default PATH.
DOCKER_APP_BIN := /Applications/Docker.app/Contents/Resources/bin
ifneq (,$(wildcard $(DOCKER_APP_BIN)/docker-credential-desktop))
export PATH := $(DOCKER_APP_BIN):$(PATH)
endif

help:
	@echo "make start       - Docker Compose: Postgres + FastAPI (http://localhost:8000/docs)"
	@echo "make db          - start Postgres + pgvector only"
	@echo "make stop        - stop Compose stack and delete the postgres-data volume"
	@echo "make install     - uv sync"
	@echo "make dev         - run API on the host against localhost:5432"
	@echo "make seed        - ingest sample docs (host Python → localhost:5432)"
	@echo "make seed-docker - ingest sample docs from the API container → db"
	@echo "make test        - unit tests (no live LLM)"

install:
	uv sync

start:
	docker compose up --build -d
	@echo "API: http://localhost:8000/docs  (seed with: make seed-docker)"

db:
	docker compose up -d db

stop:
	docker compose down -v
dev:
	uv run uvicorn app.main:app --reload --port 8000

seed:
	uv run python scripts/seed.py --tenant-id logflows-demo

seed-docker:
	docker compose run --rm -e PYTHONPATH=/app api uv run python scripts/seed.py --tenant-id logflows-demo

test:
	uv run pytest -q
