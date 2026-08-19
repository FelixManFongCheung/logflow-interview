# LOGFLOWS Knowledge RAG

Classic RAG backend for logistics knowledge documents (SOPs, policies, incidents).

## What It Is

- FastAPI service with three endpoints: `GET /health`, `POST /documents/ingest`, `POST /query`
- Retrieval stack: PostgreSQL + pgvector hybrid search (semantic + keyword)
- Local-first review path: Docker Compose runs API and DB containers

## Quickstart

```bash
git clone <your-repo-url>
cd logflows-interview
cp .env.example .env.development
# REQUIRED: set your own OPENROUTER_API_KEY in .env.development
make start
make seed-docker
```

Open: [http://localhost:8000/docs](http://localhost:8000/docs)

## Required Env Vars

Only one secret is required for end-to-end ingest/query:

- `OPENROUTER_API_KEY`

Everything else in `.env.example` can stay as-is for local Docker defaults.

## Routes

- `GET /health` — liveness
- `POST /documents/ingest` — chunk/embed/upsert tenant documents
- `POST /query` — tenant-scoped retrieval and grounded answer with citations

## How To Verify

1) Seed sample docs:

```bash
make seed-docker
```

2) Run one query:

```bash
curl -sS -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "logflows-demo",
    "user_id": "ops-user-01",
    "role": "ops",
    "question": "What should we do if a cold-chain delivery is delayed?"
  }'
```

Expected result: `success=true` with an answer and citations.

## Stop / Reset

- Stop and remove containers plus the DB volume:

```bash
make stop
```

- Equivalent explicit reset:

```bash
docker compose down -v
```

## Notes

- Compose API container uses `POSTGRES_HOST=db`.
- Host-mode `make dev` uses `POSTGRES_HOST=localhost`.
- `make seed-docker` runs a one-off API container with `PYTHONPATH=/app` so `app.*` imports resolve.
- Supabase remains optional by swapping Postgres env values in `.env.development`.
