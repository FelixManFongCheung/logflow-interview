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
| `RETRIEVE_K` | No | `6` — max primary hits after elbow filter |
| `RETRIEVE_POOL_K` | No | `20` — wide hybrid pool for per-query elbow |
| `HYBRID_SEMANTIC_WEIGHT` | No | `0.5` |
| `HYBRID_LEXICAL_WEIGHT` | No | `0.5` |
| `EVIDENCE_THRESHOLD` | No | `0.22` absolute floor (hybrid score, not raw cosine) |
| `HIGH_CONFIDENCE_THRESHOLD` | No | `0.45` |
| `USE_ELBOW_GATE` | No | `true` — dynamic cliff cutoff on primary scores |
| `ELBOW_MIN_GAP` | No | `0.08` — minimum absolute score drop to trust a cliff |
| `ELBOW_MIN_RELATIVE_GAP` | No | `0.15` — cliff must be ≥15% of top score |
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
| `confidence` | `"high"` \| `"medium"` \| `"low"` — retrieval strength from primary-hit hybrid scores (see Key decisions) |
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

Not implemented. Elbow gating on a wide retrieve pool (`RETRIEVE_POOL_K=20`) drops weak hybrid tail before the LLM where the cliff checks pass. See **Production retrieval model (RRF + rerank)** below for the scale-out design.

### Prompt strategy

Pre-LLM: refuse when no primary hits or `max(primary score) < 0.22`; otherwise apply elbow cutoff on the pool and drop primaries below the cliff. LLM context is limited to kept primaries plus their section siblings. Post-LLM: clear citations if the model returns `INSUFFICIENT_EVIDENCE`.

### Evidence threshold and confidence (`0.22` / `0.45` + elbow)

Retrieval returns a fused hybrid score per chunk: `0.5 × cosine + 0.5 × ts_rank_cd`. That number is **not** raw embedding similarity — the lexical leg uses Postgres `ts_rank_cd`, which sits on a different scale than cosine. `hybrid_search()` ranks up to **20** primary candidates (`RETRIEVE_POOL_K`); only **primary hits** (`is_primary_hit=true`) feed gating and confidence. Section siblings expanded by `header_path` are included in LLM context only when their primary survived the gate.

Gating is two-stage. First, an **absolute floor**: if there are no primary hits, or `max(score) < EVIDENCE_THRESHOLD` (default **0.22**), the query stops with `insufficient_evidence=true`, empty citations, and no LLM call. This catches unanswerable questions (e.g. freight rates not in the corpus) even when weak keyword noise exists.

Second, an **elbow cutoff** on whatever primary scores came back from the pool (`USE_ELBOW_GATE=true`). The pool asks for up to 20 hits but often returns fewer on a small corpus — elbow runs on the scores that exist, not on a fixed count. Scores are sorted descending and the service finds the **single largest** consecutive drop anywhere in the list (not the first drop from rank #1). That gap must pass **both** checks: absolute size (`ELBOW_MIN_GAP`, default **0.08**) and relative size (`ELBOW_MIN_RELATIVE_GAP`, default **15%** of the top score). If either check fails, elbow does not activate and gating falls back to the **0.22 floor only** — which can look like “elbow kept everything” when it actually never fired.

When both checks pass, the cutoff is the score at the cliff edge (the lowest score in the upper cluster) and the effective threshold is `max(0.22, elbow_cutoff)`. Primaries below it are dropped before citations and LLM context. Example with a clear cliff: 0.88 / 0.85 / 0.81 / 0.45 — largest gap 0.36, cutoff 0.81, top three kept. Example where elbow **does not** activate: on the cold-chain delay query, top scores were 0.5633 → 0.4832 (gap **0.0801**, barely above 0.08) but 0.0801 / 0.5633 ≈ **14.2%**, below the 15% relative rule — so all six primaries above 0.22 were kept up to `RETRIEVE_K=6`, including Escalation and incident chunks that a stricter first-cliff policy might have dropped. Kept primaries are always capped at `RETRIEVE_K=6`.

When an answer is returned, `confidence` is a **retrieval signal for the UI**, not LLM correctness, computed from **kept** primary scores after the elbow:

**`low`** — Pre- or post-LLM refusal, or scores below the floor.

**`medium`** — At least one kept primary has `max(score) ≥ 0.22` but not enough for high (often a single strong hit).

**`high`** — `max(score) ≥ 0.45` on kept primaries **and** at least **two** kept hits — multiple chunks agreed after the cliff filter.

Citation `score` fields reflect kept primaries only. Tune `EVIDENCE_THRESHOLD`, `ELBOW_MIN_GAP`, `ELBOW_MIN_RELATIVE_GAP`, and `HYBRID_*_WEIGHT` together on the three sample query types.

### Production retrieval model (RRF + rerank)

This take-home fuses **unnormalized** cosine and `ts_rank_cd` with fixed 0.5/0.5 weights, then applies elbow on that custom scale — which is why thresholds like 0.22 are not portable to other fusion schemes. The intended production path replaces linear fusion with **Reciprocal Rank Fusion (RRF)** in SQL: merge semantic and keyword ranked lists by rank position (`score += weight / (k + rank)`, typically `k=60`) so no hand-tuned 0.5/0.5 blend and no mixed raw-score scales. RRF scores sit in a much lower numeric range (~0.01–0.02 for strong hits), so **`EVIDENCE_THRESHOLD` and elbow settings would be re-calibrated or replaced** — likely gating on a cross-encoder **reranker** (BGE-Reranker, Cohere Rerank) after retrieving top 25–50 RRF candidates. Elbow on the reranker score distribution, plus an absolute rerank floor, is a more stable production gate than elbow on today's fused hybrid numbers.

## Production considerations

The sections below describe what the service does today and what would change before wiring it into a LOGFLOWS product.

### Tenant isolation

Ingest and `hybrid_search()` filter on `tenant_id` in SQL, and `visibility` against the caller’s `role` keeps ops-only chunks out of CS queries. That is data-plane isolation, not authentication. In production, JWT or gateway identity should set `tenant_id` and `role` on the server — those fields must not be trusted from the request body. If the API shares a Postgres pool across tenants, row-level security with `SET LOCAL app.tenant_id` is the natural next step.

### Document updates and deletes

Re-ingesting the same `document_id` deletes that tenant’s existing chunks and inserts the new set inside one transaction. There is no delete endpoint and no tenant wipe API; operations would run SQL today. Production should add explicit delete plus audit logging — `user_id` is already on `/query` for that hook. Changing the embedding model still requires a full re-ingest because vectors are not portable across models.

### Observability

Today the service exposes `GET /health` and returns FastAPI 4xx/5xx on ingest or query failures. There are no request IDs, Langfuse traces, or Prometheus metrics. Before production, add request-ID middleware and structured logs with `tenant_id`, `user_id`, latency, hit counts, and whether the answer was refused for insufficient evidence. Trace embed, retrieve, and generate as separate spans so cost and p95 latency split by stage. Export query QPS, refusal rate, OpenRouter errors, and Postgres pool wait. Sample query logs with the question and citation ids — not full SOP bodies — so retrieval quality can be evaluated offline.

### Cost control

The billable path runs through OpenRouter: Qwen embeddings on ingest, once per chunk, and DeepSeek R1 on every query that passes the evidence gate. The main cost brake is refusing before the LLM when `max(primary score) < 0.22`, and dropping weak tail primaries via elbow so fewer tokens reach R1. Keep `RETRIEVE_K` and section expansion bounded (`RETRIEVE_MAX_EXPANDED=24`) so prompt tokens stay small. Cache embeddings by content hash when the same SOP is re-uploaded unchanged. A cheaper instruct model may be enough for high-volume CS chat; keep R1 for ops questions that need cross-document reasoning.

### Latency targets

Hybrid retrieve on this corpus is tens of milliseconds locally; it grows with corpus size, not prompt size. Query embedding via OpenRouter typically adds 100–400 ms. Chat completion with R1 reasoning runs 2–15 s with no streaming, so the user waits for the full answer. End-to-end, an answered query is roughly 3–20 s and dominated by the LLM; a refusal is roughly 0.2–1 s because it stops after embed and retrieve. Reasonable product targets are p95 refusal under 1.5 s and p95 answer under 8 s if you drop reasoning or stream tokens — neither is implemented in this take-home.

### Privacy and security

Indexed document text and the user question are sent to OpenRouter for embeddings and chat. Do not index secrets, contract rates, or PII without a DPA and a region-pinned provider. The OpenRouter key lives in `.env` and must not be committed. CORS defaults to `*`; lock `ALLOWED_ORIGINS` in production. The Compose Postgres password is a local default; hosted databases should use `POSTGRES_SSLMODE=require`. There is no rate limiting on `/query` yet — add it at the gateway so one tenant cannot exhaust the LLM budget.

### Scaling

Forty-seven chunks is not an approximate-nearest-neighbour problem. At roughly one million chunks across a hundred tenants, keep one Postgres with `tenant_id` on every index and enforce RLS. Partition or shard by tenant if a few customers dominate storage or QPS. Raise HNSW `ef_search` only after measuring recall on a labeled set. Replace linear 0.5/0.5 fusion with RRF in `hybrid_search()`, retrieve 25–50 candidates, rerank, then apply elbow or a rerank-score floor before the LLM — the same two-stage refuse logic, on scores meant for ranking rather than today's cosine+BM25 blend. A second vector database is justified only when Postgres CPU or storage becomes the bottleneck, not at demo size.

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
- **Evidence threshold is not self-tuning** — `EVIDENCE_THRESHOLD`, elbow settings, `HIGH_CONFIDENCE_THRESHOLD`, hybrid weights, and chunk token limits are fixed env values. Elbow adapts per query but still needs calibration on a labeled set; there is no online calibration from live traffic.
- No reranking after hybrid search — elbow + fused score only; production path is RRF + cross-encoder rerank
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
