# LOGFLOWS Knowledge RAG

RAG backend for logistics documents (SOPs, policies, incidents, customer notes).

## What It Is

- **FastAPI** service with three routes: `GET /health`, `POST /documents/ingest`, `POST /query`
- **Retrieval:** PostgreSQL 16 + pgvector hybrid search (50% cosine similarity + 50% Postgres full-text rank)
- **Models:** Qwen embeddings + DeepSeek R1 reasoning chat model, both via OpenRouter
- **Local review path:** Docker Compose runs the API and Postgres containers (`make start`)

Indexed documents only — live TMS/LMS rows are out of scope.

## Architecture

![LOGFLOWS Knowledge RAG — 3-layer architecture](docs/architecture.png)

**Flow:** ingest/query → hybrid retrieve → evidence gate → LLM or refusal → answer + citations.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (Compose v2)
- [uv](https://docs.astral.sh/uv/) (Python 3.13+)
- [OpenRouter API key](https://openrouter.ai/keys) for embeddings and answer generation

## Quickstart (Docker — recommended for reviewers)

```bash
git clone https://github.com/FelixManFongCheung/logflow-interview.git
cd logflows-interview
cp .env.example .env.development
# REQUIRED: set OPENROUTER_API_KEY in .env.development
make start      # builds and starts api + db
make seed-docker  # ingests 6 sample docs into tenant logflows-demo
```

Open Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

On first boot, Postgres loads `sql/schema.sql` from the init volume mount. The API also re-applies the same schema on startup via `init_db()` (idempotent).

## Host development (optional)

Run Postgres in Docker, API on the host with hot reload:

```bash
cp .env.example .env.development
# set OPENROUTER_API_KEY; keep POSTGRES_HOST=localhost
make install
make db         # Postgres only on :5432
make dev        # uvicorn with --reload
make seed       # ingest samples via host Python → localhost:5432
```

## Required env vars

Settings load from the first file found: `.env.development` → `.env` → `.env.example`.

| Variable | Required | Default / notes |
|----------|----------|-----------------|
| `OPENROUTER_API_KEY` | **Yes** | Reviewer must supply their own key |
| `EMBEDDING_MODEL` | No | `qwen/qwen3-embedding-4b` |
| `EMBEDDING_DIMENSIONS` | No | `1024` (must match `vector(1024)` in schema) |
| `LLM_MODEL` | No | `google/gemma-4-26b-a4b-it:free` |
| `CHUNK_SIZE_TOKENS` | No | `256` |
| `CHUNK_OVERLAP_TOKENS` | No | `32` |
| `RETRIEVE_K` | No | `6` |
| `HYBRID_SEMANTIC_WEIGHT` | No | `0.5` |
| `HYBRID_LEXICAL_WEIGHT` | No | `0.5` |
| `EVIDENCE_THRESHOLD` | No | `0.22` (hybrid score, not raw cosine) |
| `HIGH_CONFIDENCE_THRESHOLD` | No | `0.45` |
| `POSTGRES_*` | No | Local defaults in `.env.example`; Compose overrides `POSTGRES_HOST=db` for the API container |

## Routes

All successful responses use a wrapper envelope:

```json
{ "success": true, "message": "...", "data": { ... } }
```

Errors return `{ "success": false, "error_code": "...", "detail": "...", "message": "..." }` with 4xx/5xx status.

### `GET /health`

Liveness probe. Returns `data.status = "ok"`.

### `POST /documents/ingest`

Chunk, embed, and upsert documents for a tenant. Re-ingesting the same `document_id` replaces that document's chunks.

```json
{
  "tenant_id": "logflows-demo",
  "documents": [
    {
      "id": "sop-001",
      "title": "Cold Chain SOP",
      "text": "# Cold Chain SOP\n\n...",
      "visibility": "all"
    }
  ]
}
```

- `visibility`: `"ops"` | `"cs"` | `"all"` — enforced at retrieval time by user `role`
- **201** on success: `data.documents`, `data.chunks` counts

### `POST /query`

Retrieve tenant-scoped chunks, apply evidence gating, generate an answer.

```json
{
  "tenant_id": "logflows-demo",
  "user_id": "ops-user-01",
  "role": "ops",
  "question": "What should we do if a cold-chain delivery is delayed?"
}
```

- `role`: `"ops"` | `"cs"` | `"admin"` — `"admin"` sees all visibility levels
- `user_id` is validated and reserved for future audit logging (not used in retrieval today)

**200** response `data` fields:

| Field | Description |
|-------|-------------|
| `answer` | Grounded answer or controlled refusal text |
| `citations` | Retrieved chunks with `document_id`, `chunk_id`, `score`, `title`, `header_path` |
| `confidence` | `"high"` \| `"medium"` \| `"low"` from hybrid scores |
| `insufficient_evidence` | `true` when pre- or post-LLM refusal triggers |

## Sample data

`make seed` / `make seed-docker` loads six markdown files from `data/samples/` into tenant `logflows-demo`:

| Document ID | Title | Visibility |
|-------------|-------|------------|
| `sop-001` | Cold Chain SOP | `all` |
| `wh-esc-002` | Warehouse Escalation Procedure | `ops` |
| `cust-acme-003` | Customer Handling Notes — ACME Retail | `all` |
| `inc-2026-014` | Incident Report INC-2026-014 — Reefer logger gap | `ops` |
| `pol-haz-005` | Shipment Policy — Hazardous goods labeling | `all` |
| `sop-006` | Inbound Receiving SOP | `all` |

After seeding, expect roughly **47 chunks** (hierarchical markdown split).

### Expected query behaviour

| Question | Expected behaviour | Why |
|----------|-------------------|-----|
| What should we do if a cold-chain delivery is delayed? | **Answerable** — cites `sop-001`, step-by-step delay procedure | Explicit SOP section on delay handling |
| What happened on shipment SH-8891 to Berlin? | **Partially answerable** — cites `inc-2026-014` with timeline gaps noted or refusal if evidence incomplete | Incident report covers the event but not every operational detail |
| What is ACME's contracted freight rate to Hamburg? | **Not answerable** — `insufficient_evidence=true` | `cust-acme-003` explicitly excludes pricing and rates |

## How to verify

1. Seed:

```bash
make seed-docker
```

2. Query:

```bash
curl -sS -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "logflows-demo",
    "user_id": "ops-user-01",
    "role": "ops",
    "question": "What should we do if a cold-chain delivery is delayed?"
  }' | jq .
```

Expected: `"success": true`, `"message": "query_answered"`, non-empty `data.answer`, `data.citations` referencing `sop-001`, `"insufficient_evidence": false`.

3. Run tests (mocked retrieval/LLM — no live API calls):

```bash
make test
```

## Key decisions

### Chunk size (`CHUNK_SIZE_TOKENS=256`, overlap `32`)

Markdown SOPs split on `#` / `##` / `###` first; sections over 256 tokens get a second token split (32 overlap). Chunks carry `header_path` for section expansion at query time.

### Embedding model (`qwen/qwen3-embedding-4b`, 1024 dims)

- OpenRouter `/embeddings`, same client as chat; one API key
- 1024 dims match `vector(1024)` in schema — no migration
- 4B over 0.6B: better on ops jargon (`HLD-QC-*`, POD, temperature bands) for ~50 chunks
- Alternatives considered: OpenAI/Cohere embeds (second billing/integration), local sentence-transformers (ops overhead)
- Re-ingest required if embed model changes

### Chat model (`deepseek/deepseek-r1-0528`)

Embeddings find semantically close text but miss nuance — cross-doc overrides, partial coverage, “out of scope” boundaries. Hybrid search + section context helps retrieval; the LLM still has to read what the blocks mean together.

Reasoning models (o-series, R1, QwQ, etc.) are used here to interpret retrieved text, not to replace search. R1 on OpenRouter: stable slug, OpenAI-compatible API, strong instruction following with `temperature=0`, lower cost than closed frontier models.

Alternatives via `LLM_MODEL`: `openai/o3-mini`, `qwen/qwq-32b-preview`, `deepseek/deepseek-r1-distill-qwen-32b`, or a free instruct route for smoke tests.

### Vector store (PostgreSQL 16 + pgvector)

Chose pgvector over a dedicated vector DB (Pinecone, Weaviate, Qdrant) so chunks, metadata, full-text indexes, and embeddings live in one ACID store. Tenant/role filters, hybrid fusion, and section expansion are a single SQL function — no dual-write or sync between Postgres and a second service.

Local Compose and hosted Postgres (Supabase, RDS) share the same schema; backup, SSL, and monitoring are the usual Postgres toolchain. FastAPI talks to it with async `psycopg` (`app/core/db.py`). LangChain is used only for markdown/token splitters, not as the retrieval layer.

This corpus is small (~6 docs / ~47 chunks, 1024-dim vectors). HNSW is enough; a specialised ANN cluster would add ops cost without a retrieval win at this scale.

- HNSW + `hybrid_search()` SQL: 0.5 cosine + 0.5 `ts_rank_cd` (procedural SOPs, not conversational docs)
- Section expansion by `header_path`; `is_primary_hit` splits API citations vs LLM-only siblings
- `tenant_id` + `visibility`/`role` filtered in SQL

### Reranking

Not implemented. Hybrid fusion + section expansion is enough at ~50 chunks.

### Prompt strategy

- Pre-LLM: refuse if `max(primary score) < 0.22` (primary hits only)
- LLM: sources formatted with title, headers, metadata; `PRIMARY SOURCE` vs `SECTION CONTEXT`
- Post-LLM: clear citations if model returns `INSUFFICIENT_EVIDENCE`

### Evidence threshold (`0.22` / `0.45`)

Fused hybrid score: `0.5 × cosine + 0.5 × ts_rank_cd` — not raw cosine. Threshold `< 0.22` skips LLM; `≥ 0.45` with 2+ primary hits → high confidence. Tune via `HYBRID_*_WEIGHT`, `EVIDENCE_THRESHOLD`, / `HIGH_CONFIDENCE_THRESHOLD`.

## Production considerations

What this service does today vs what would change before a product integration.

### Tenant isolation

`hybrid_search()` and ingest filter on `tenant_id` in SQL; `visibility` vs caller `role` drops ops-only chunks from CS queries. That is data-plane isolation, not auth. Production needs JWT (or gateway identity) that **sets** `tenant_id` / `role` — never trust those fields from the JSON body. Row-level security (`SET LOCAL app.tenant_id`) is the next Postgres step if the API and DB share a connection pool across tenants.

### Document updates and deletes

Re-ingest of the same `document_id` deletes that tenant’s chunks and inserts the new set (transactional). There is no `DELETE /documents/{id}` and no tenant wipe API — ops would run SQL. Production should add delete + audit (`user_id` is already on `/query` for that). Embedding-model changes still require a full re-ingest.

### Observability

Today: `GET /health` plus FastAPI 4xx/5xx on ingest/query failures. No request IDs, no Langfuse traces, no metrics.

Production plan:

- Request ID middleware; structured logs with `tenant_id`, `user_id`, latency, hit counts, `insufficient_evidence`
- Trace embed + retrieve + generate separately (Langfuse or OpenTelemetry) so cost and p95 split by stage
- Metrics: query QPS, refusal rate, OpenRouter errors, Postgres pool wait
- Sample query logs (question + citation ids, not full SOP body) for retrieval eval

### Cost control

Billable path is OpenRouter: Qwen embeddings on **ingest** (once per chunk) and DeepSeek R1 on **every answered query**. The evidence gate skips the chat call when `max(primary score) < 0.22`, which is the main cost brake. Keep `RETRIEVE_K` and section expansion bounded (`RETRIEVE_MAX_EXPANDED=24`) so prompt tokens stay small. Cache embeddings by content hash if the same SOP is re-uploaded unchanged. Prefer a cheaper instruct model for high-QPS CS chat; keep R1 for ops questions that need cross-doc reasoning.

### Latency targets

| Stage | Expected (this corpus) | Notes |
|--------|-------------------------|--------|
| Hybrid retrieve | tens of ms | Local pgvector; grows with corpus, not with prompt size |
| Embed query | 100–400 ms | OpenRouter round trip |
| Chat completion | 2–15 s | R1 reasoning; no streaming — user waits for the full answer |
| End-to-end (answered) | ~3–20 s | Dominated by the LLM |
| End-to-end (refusal) | ~0.2–1 s | Embed + retrieve only |

Product targets: **p95 refusal under 1.5 s**, **p95 answer under 8 s** if you switch off reasoning or stream tokens. This take-home does not stream.

### Privacy and security

Indexed text and the user question are sent to OpenRouter (embeddings + chat). Do not put secrets, rates, or PII in sample SOPs without a DPA and a region-pinned provider. `.env` holds the API key — never commit it. CORS defaults to `*`; lock `ALLOWED_ORIGINS` in production. Postgres password in Compose is a local default; hosted DBs should use `POSTGRES_SSLMODE=require`. No rate limiting on `/query` yet — add it at the gateway so one tenant cannot burn the LLM budget.

### Scaling

~47 chunks is not an ANN problem. At ~1M chunks / 100 tenants: keep one Postgres with `tenant_id` in every index and RLS; partition or shard by tenant if a few customers dominate; raise HNSW `ef_search` only after measuring recall. Still retrieve a candidate pool in SQL, then rerank if quality drops. Do not put embeddings in a second database unless Postgres CPU or storage becomes the bottleneck.

## Known limitations

### Security & tenancy
- No JWT auth — `tenant_id`, `role`, and `user_id` are trusted from the request body
- Tenant isolation is enforced in SQL retrieval, not caller identity — anyone who can reach the API can query any tenant id they guess

### Document ingest & format
- **Markdown-first input** — ingest expects plain `text` that is already markdown. There is no PDF/DOCX/HTML parser, OCR, or table extractor in this service; those formats must be preprocessed upstream.
- **Structure-sensitive chunking** — quality depends on `#` / `##` / `###` headings to preserve SOP sections, tables, and escalation steps. Flat walls of text, inconsistent heading levels, or docs exported without headings chunk poorly and lose `header_path` metadata used for section expansion.
- No document delete endpoint — re-ingest replaces chunks per `document_id`; full tenant wipe is manual SQL
- Changing the embedding model requires a full re-ingest (vectors are not portable across models)

### Retrieval & query understanding
- **No query rewriting** — the user question is embedded and searched as-is. There is no HyDE, synonym expansion, acronym normalisation (e.g. “POD” → “proof of delivery”), or LLM rephrase step before retrieval. Opaque, vague, or mismatched terminology often yields weak hits → controlled refusal with no second attempt.
- **Evidence threshold is not self-tuning** — `EVIDENCE_THRESHOLD`, `HIGH_CONFIDENCE_THRESHOLD`, hybrid weights (`HYBRID_SEMANTIC_WEIGHT` / `HYBRID_LEXICAL_WEIGHT`, default 0.5/0.5), and chunk token limits are fixed env values. Changing any of them shifts the refuse/answer boundary and requires re-testing on a labeled query set (answerable / partial / unanswerable); there is no online calibration from live traffic.
- No reranking after hybrid search — top-k order is fused score only
- Full-text leg uses Postgres `english` config — non-English or heavy jargon/code matching is imperfect without custom dictionaries
- Citations return chunk pointers (`chunk_id`, `header_path`, score) but not chunk body text in the API response

### Tuning, loops & human review
- **No eval / feedback loop** — no automated pipeline to log queries, score retrieval quality, compare prompt variants, or promote config changes. Tuning chunk size, fusion weights, or thresholds is manual: change env → re-seed → re-run eval queries.
- **No human-in-the-loop (HITL)** — no UI or workflow for ops staff to mark answers wrong, fix chunk boundaries, or approve documents before indexing. Index choice (HNSW vs IVFFlat), section expansion, and ingest structure are engineer decisions, not reviewer-driven.

### Generation & product scope
- No streaming responses — answers return only after full LLM completion
- Live TMS/LMS operational data (shipment status, rates, contracts) is intentionally out of scope
- Reasoning chat model adds latency and OpenRouter cost per query

### Operations
- No request tracing or eval dashboard wired up
- Hosted Postgres (e.g. Supabase) works by swapping `POSTGRES_*` env vars and setting `POSTGRES_SSLMODE=require`

## Troubleshooting Docker

**`docker-credential-desktop: executable file not found in $PATH`**

Docker Desktop’s credential helper lives outside default PATH on macOS. The Makefile prepends `/Applications/Docker.app/Contents/Resources/bin` automatically. If you run `docker compose` directly, either:

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

or symlink once:

```bash
sudo ln -sf /Applications/Docker.app/Contents/Resources/bin/docker-credential-desktop /usr/local/bin/docker-credential-desktop
```

Also ensure **Docker Desktop is running** before `make start`.

## Stop / reset

`make stop` runs `docker compose down -v`, which **removes containers and the `postgres-data` volume** (full DB reset):

```bash
make stop
# equivalent:
docker compose down -v
```

To stop without wiping data, run `docker compose down` (no `-v`).

## Makefile reference

| Target | Action |
|--------|--------|
| `make start` | Build and start API + Postgres in Docker |
| `make db` | Start Postgres only |
| `make dev` | Run API on host against `localhost:5432` |
| `make seed` | Ingest samples from host Python |
| `make seed-docker` | Ingest samples from API container (`PYTHONPATH=/app`) |
| `make test` | `pytest` — unit/route tests, no live LLM |
| `make stop` | Tear down Compose stack and delete DB volume |
