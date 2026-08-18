.DEFAULT_GOAL := help

help:
	@echo "make db          - start Postgres + pgvector"
	@echo "make install     - uv sync"
	@echo "make dev         - run API on :8000"
	@echo "make seed        - ingest sample logistics documents"
	@echo "make test        - unit tests (no live LLM)"

install:
	uv sync

db:
	docker compose up -d db

dev:
	uv run uvicorn app.main:app --reload --port 8000

seed:
	uv run python scripts/seed.py --tenant-id logflows-demo

test:
	uv run pytest -q
