# LOGFLOWS Knowledge RAG

Classic RAG backend for logistics **knowledge documents** (SOPs, policies, incidents). Not a chatbot, not LangGraph: two JSON endpoints any frontend can call.

## Why Postgres + pgvector (not a separate vector DB)

| Option | Hybrid search | Tenant filter | Take-home fit |
|--------|---------------|---------------|----------------|
| **Postgres + pgvector** | `tsvector` + cosine in one SQL function | `WHERE tenant_id = $1` in the same query | Best default |
| Supabase | Same Postgres function, exposed as `rpc('hybrid_search', …)` | Same | Hosted version of this schema |
| Chroma / FAISS | Vector only unless you add a second index | Easy to forget in app code | Weaker for SOP **ids** (`SOP-001`) |
| Azure AI Search | Strong hybrid | Native filters | Production mapping, extra account |

This repo defaults to **local Docker Postgres**. The function in `sql/schema.sql` is written so you can paste it into Supabase SQL editor and call:

```js
supabase.rpc('hybrid_search', {
  p_tenant_id: 'logflows-demo',
  p_query_text: question,
  p_query_embedding: embedding,
  p_match_count: 6,
  p_role: 'ops',
})
```

## Architecture

```text
POST /documents/ingest
  → validate → hierarchical markdown chunk → embed → DELETE+INSERT chunks (per tenant + document_id)

POST /query
  → embed question → hybrid_search(tenant_id, role)   ← isolation in SQL
  → if max(score) < threshold: refuse (no LLM guess)
  → else LLM with chunks only + citations
```

Live TMS/LMS shipment rows are **out of scope**. This service answers from indexed documents. Operational truth would be a later API-tool layer.

## Setup

Typical reviewer flow: clone locally, create env from template, add **your own** secrets, then run Compose.

```bash
git clone <your-repo-url>
cd logflows-interview
cp .env.example .env.development
# REQUIRED: set your own OPENROUTER_API_KEY — https://openrouter.ai/keys
# Never commit .env.development
```

### One-command Docker (API + Postgres)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) running, then:

```bash
make start        # builds the API image, starts db + api
make seed-docker  # ingest sample docs from inside the API container
```

- API: http://localhost:8000/docs
- Postgres: `localhost:5432` (also reachable as hostname `db` from the API container)

Compose services share a **bridge network**. FastAPI talks to Postgres over TCP (`POSTGRES_HOST=db`). Chunks and embeddings live in the named volume `postgres-data` (owned by Postgres).

- The database container mounts `sql/schema.sql` on first boot (`/docker-entrypoint-initdb.d/001-schema.sql`).
- The API container does **not** mount Postgres data files.
- `make seed-docker` runs `scripts/seed.py` in a one-off API container and sets `PYTHONPATH=/app` so `app.*` imports resolve correctly.

Stop containers without deleting data: `make stop`. Wipe the volume only if you intend to: `docker compose down -v`.

### Host API + Docker Postgres

```bash
make db          # Postgres + pgvector only
make install
make seed        # 6 sample logistics docs → tenant logflows-demo
make dev         # http://localhost:8000/docs
make test
```

`POSTGRES_HOST=localhost` when the API runs on the host. Compose sets `POSTGRES_HOST=db` when the API runs in Docker.

Supabase is optional: same schema, swap host/user/ssl in `.env.development`. Reviewers do not need a cloud project.

## API

### Ingest

```bash
curl -s localhost:8000/documents/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "logflows-demo",
    "documents": [
      {"id": "sop-001", "title": "Cold Chain SOP", "text": "If delayed more than 30 minutes, notify QC..."}
    ]
  }'
```

### Query

```bash
curl -s localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "logflows-demo",
    "user_id": "ops-user-01",
    "question": "What should we do if a cold-chain delivery is delayed?"
  }'
```

Expected shape:

```json
{
  "success": true,
  "message": "query_answered",
  "data": {
    "answer": "...notify QC within 10 minutes...",
    "citations": [
      {
        "document_id": "sop-001",
        "chunk_id": "logflows-demo:sop-001:0",
        "score": 0.82,
        "title": "Cold Chain SOP",
        "header_path": "Cold Chain SOP (SOP-001) > Delay procedure",
        "metadata": {}
      }
    ],
    "confidence": "medium",
    "insufficient_evidence": false
  }
}
```

Errors use HTTP 502 with `{ "success": false, "error_code": "...", "detail": "...", "message": "..." }`.
Ingest success returns HTTP 201; query and health return HTTP 200.

CORS defaults to `*` so a TMS web app or mobile client can call these two routes.

## Sample data and expected behaviour

| Question | Expected |
|----------|----------|
| What should we do if a cold-chain delivery is delayed? | **Answerable** from `sop-001` (30 min, QC, temperature band) |
| What should we do after a reefer logger gap on yogurt to Berlin? | **Partial** — `inc-2026-014` describes one incident; it does not replace SOP-001 |
| What is ACME’s contracted freight rate to Hamburg? | **Unanswerable** — `insufficient_evidence: true`, no invented rates |
| How do we handle a broken inbound seal? | **Answerable** from `sop-006` (long SOP; stored as multiple `sop-006:N` chunks) |

Documents live in `data/samples/`. Visibility: warehouse escalation and the incident are `ops`-only; `role=cs` should not retrieve them.

## Chunking strategy

Implemented in `app/services/chunking.py` — LangChain hierarchical split, not fixed-size paragraph windows.

### Pipeline

```text
Markdown body
  → Layer 1: MarkdownHeaderTextSplitter (# / ## / ###)
  → Layer 2: TokenTextSplitter only when a section exceeds the token ceiling
  → Layer 3: inherit h1/h2/h3 + header_path into metadata and embedded content
```

| Layer | Splitter | Overlap? |
|-------|----------|----------|
| **1 — Structure** | Split on `#`, `##`, `###` | No — each heading block is a separate unit |
| **2 — Size cap** | Sub-split blocks over `CHUNK_SIZE_TOKENS` | Yes — `CHUNK_OVERLAP_TOKENS` sliding window **within** that section only |
| **3 — Context** | Prefix title + header breadcrumbs into `content` | N/A — repeated header lines on sub-chunks for retrieval, not token overlap |

Short sections (e.g. a temperature table under one `##`) stay **one chunk**. Long SOPs (e.g. `sop-006`) produce multiple sub-chunks under the same `header_path`.

### Stored fields

Each chunk row gets:

- **`content`** — `{title}\n\n{## headers}\n\n{body}` (what gets embedded)
- **`metadata`** (JSONB) — `h1`, `h2`, `h3`, `document_id`, `document_title`, `header_path`
- **`header_path`** (column) — breadcrumb such as `Cold Chain SOP (SOP-001) > Delay procedure`, used by `hybrid_search` for **section expansion** at query time (sibling chunks under the same heading)

### Defaults (`app/core/config.py`)

| Setting | Default | Notes |
|---------|---------|-------|
| `CHUNK_SIZE_TOKENS` | 256 | Max tokens per section body before sub-split |
| `CHUNK_OVERLAP_TOKENS` | 32 | Overlap when layer 2 runs; most sample docs never hit this |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 900 / 120 | Legacy char fallbacks if passed explicitly to `chunk_text()` |

Tune via env vars; re-ingest after changes.

### Query-time section expansion

Top-k hybrid hits with the same `(document_id, header_path)` can pull in sibling chunks from that section (`EXPAND_SECTION_SIBLINGS=true`, cap `RETRIEVE_MAX_EXPANDED=24`). This compensates when a procedure spans several sub-chunks but one paragraph matched the question.

## Key decisions

| Choice | Value | Why |
|--------|--------|-----|
| Chunking | Hierarchical `#`/`##`/`###`, 256 tokens, 32-token overlap on long sections only | Keeps tables and steps intact; `header_path` enables sibling expansion at query time |
| Embeddings | OpenRouter `qwen/qwen3-embedding-4b` (1024-d via `dimensions`) | OpenAI-compatible `/embeddings`; works from Hong Kong |
| Vector store | pgvector HNSW + GIN on `tsvector` | Hybrid: semantic + keyword (`SOP-001`) |
| Hybrid weights | 0.7 cosine, 0.3 full-text | Keywords help ids; semantics help paraphrases |
| Evidence gate | refuse if top hybrid score `< 0.22` | Stops “helpful” hallucination |
| Access control | `tenant_id` **and** `visibility`/`role` in SQL | Prompt-only isolation is not isolation |
| LLM | OpenRouter `google/gemma-4-26b-a4b-it:free`, temperature 0, “ONLY from chunks” | Separate chat client; free route (Qwen chat needs credits) |

Changing embedding model dimensions requires changing `vector(1024)` in `sql/schema.sql` and re-ingesting.

## Production notes (not built)

These are intentional boundaries and follow-ups for a LOGFLOWS-style deployment — the take-home implements the core RAG path only.

### Auth and access control

- **Identity:** API gateway validates JWT (or mTLS); map claims → `user_id`, `tenant_id`, `role`. Do not trust those fields from the request body in production.
- **Tenant membership:** maintain a user→tenant registry; reject queries where the caller is not a member of the requested tenant.
- **Ingest authorization:** restrict document indexing to `ops` / `admin` roles; CS and read-only roles query only.
- **Document visibility:** keep filtering in SQL (`visibility` + `role`) — not in the LLM prompt. `user_id` is for audit, not chunk-level ACL in v1.

### Document lifecycle

- **Upsert:** ingest already replaces all chunks for `(tenant_id, document_id)` on re-ingest.
- **Delete:** add `DELETE /documents/{id}` with the same role gate as ingest; cascade chunk rows and optionally tombstone in an audit log.
- **Versioning:** store `ingested_at`, `ingested_by`, and source hash per document for rollback and compliance.

### Scale (1M docs × 100 tenants)

- Partition `document_chunks` by `tenant_id` (or schema-per-tenant for largest customers).
- Rebuild HNSW / GIN indexes per partition; tune `lists` / `m` as row counts grow.
- Async ingest workers for embedding (queue + batch API calls); API returns 202 + job id for large uploads.
- Read replicas for hybrid search; writer primary for ingest only.

### Observability

- Structured logs (structlog): `tenant_id`, `user_id`, `question_hash`, `chunk_ids`, top scores, latency ms, token usage — **never** full SOP body text.
- Metrics: ingest throughput, query p95, refusal rate, embed/LLM error rate, cache hit rate.
- Tracing: span per request — embed → `hybrid_search` → evidence gate → LLM (when called).

### Privacy and compliance

- Keep Postgres indexes in-region with the tenant contract (EU data stays in EU).
- SOPs may name customers and sites; redact or tokenize before sending context to third-party LLMs if DPA requires it.
- Pseudonymise `user_id` in analytics; retain raw ids only in security audit logs with retention policy.

### Cost and latency

- **Embed once at ingest** — query path pays one embed + one RPC + (optionally) one LLM call.
- **`RETRIEVE_K=6`** with section expansion capped by `RETRIEVE_MAX_EXPANDED`.
- **Skip LLM when `max(score) < EVIDENCE_THRESHOLD`** (retrieval gate). Borderline “related but not answerable” questions may still invoke the LLM today — raising the threshold or adding a reranker are tunable trade-offs.
- **Query embedding cache** (Redis, keyed by normalised question + tenant): skip DB vector search on near-duplicate questions; invalidate on document re-ingest for that tenant.
- **Answer cache** (optional, short TTL): cache `(tenant, question_hash) → response` for repeated ops desk queries — only when citations unchanged.

### Quality, eval, and human-in-the-loop

- **Offline eval:** fixed question set with expected `document_id`s, hit@k, refusal accuracy, and LLM faithfulness checks before each release.
- **Online monitoring:** sample production queries for manual review; track citation click-through in the TMS UI.
- **Human-in-the-loop:** ops can flag wrong answers → feeds chunking/threshold/prompt updates (not automatic fine-tuning in v1).
- **Remaining hallucination risk:** LLM can misread a correct chunk; citations + `header_path` let users verify. Per-chunk score floors and reranking reduce but do not eliminate this.

## Project layout

```text
app/
  main.py                 # FastAPI app, CORS, lifespan, router mount
  api/
    api.py                # GET /health; mounts ingest + query routers
    ingest.py             # POST /documents/ingest
    query.py              # POST /query
  core/
    config.py             # env settings (OpenRouter, Postgres, retrieval tuning)
    db.py                 # connection pool + schema bootstrap
  schema/
    schemas.py            # IngestRequest, QueryRequest, Citation, payloads
    responses.py          # BaseResponse, CorrectResponse, ErrorResponse
  services/
    chunking.py           # LangChain hierarchical chunking + metadata
    retriever.py          # ingest_documents + hybrid_search RPC
    llm.py                # OpenRouter embeddings + grounded chat
    evidence.py           # score threshold + confidence labels

sql/schema.sql            # document_chunks table + hybrid_search() RPC

data/samples/             # six logistics markdown docs (SOPs, policies, incident)

scripts/
  seed.py                 # ingest sample docs into a tenant

tests/                    # validation, chunking, evidence, response envelopes

docker-compose.yml        # db (Postgres) + api (FastAPI) + postgres-data volume
Dockerfile                # API image
Makefile                  # start | db | stop | install | dev | seed | seed-docker | test
```

**Routes:** `GET /health` · `POST /documents/ingest` · `POST /query`

No LangGraph — linear retrieve-then-generate pipeline.
