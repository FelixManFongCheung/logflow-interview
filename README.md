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

## Key Decisions

These choices match what is implemented in `app/services/chunking.py`, `sql/schema.sql`, and `app/services/llm.py` — not generic RAG defaults.

### Chunk size (`CHUNK_SIZE_TOKENS=256`, overlap `32`)

Sample SOPs/policies are markdown with `##` / `###` sections and short tables. A flat character split would cut tables and escalation steps in half.

**Strategy:** two-layer hierarchical chunking:

1. **`MarkdownHeaderTextSplitter`** on `#` / `##` / `###` — keeps “Delay handling”, “Temperature bands”, and “Escalation matrix” as intact units when they fit.
2. **`TokenTextSplitter`** only when a section exceeds **256 tokens** (~1 SOP subsection). Overlap **32 tokens** applies only to those oversized splits, not between sibling sections.

Each chunk is prefixed with document title + inherited header breadcrumbs (`header_path`) so retrieval still knows which SOP section it came from. On the seeded corpus (6 docs), this yields ~47 chunks — small enough for local pgvector, large enough to cover cross-referenced ops content.

### Embedding model (`qwen/qwen3-embedding-4b`, 1024 dims via OpenRouter)

- **Why Qwen embeddings:** OpenRouter exposes them with the same OpenAI-compatible `/embeddings` API this repo already uses; `EMBEDDING_DIMENSIONS=1024` matches the `vector(1024)` column in `document_chunks`.
- **Why 4B not 0.6B:** slightly better semantic match on logistics jargon (“reefer”, “quarantine load”, “POD”, “ACME-NIGHT-*”) at acceptable ingest cost for ~50 chunks.
- **Separate from chat model:** embeddings use `qwen/qwen3-embedding-4b`; answers use `google/gemma-4-26b-a4b-it:free` so ingest/query embedding stays stable even if the free chat route changes.

### Vector store (PostgreSQL 16 + pgvector, hybrid SQL function)

Single database for vectors, full-text, tenant isolation, and access control — no separate Pinecone/Weaviate layer for this take-home.

- **Index:** HNSW on `embedding` with `vector_cosine_ops`.
- **Lexical leg:** `tsvector` + GIN on chunk content; `ts_rank_cd` for keyword scoring (exact policy ids like `SOP-001`, `HLD-QC-*`, customer codes).
- **Retrieval RPC:** `hybrid_search(...)` in `sql/schema.sql` runs semantic + lexical in parallel, full-outer-joins by `chunk_id`, and ranks by weighted score.
- **Section expansion:** when a hit lands in a markdown section, sibling chunks under the same `header_path` are pulled in (up to `RETRIEVE_MAX_EXPANDED=24`) so a question about “delay handling” gets the full procedure block, not one sentence.

`tenant_id` and `visibility`/`role` filters are enforced inside the SQL function, not only in Python.

### Reranking — not used

No cross-encoder or LLM reranker after retrieval. For ~50 chunks and `RETRIEVE_K=6`, the cost/latency of a second model pass did not justify the gain over:

- weighted hybrid fusion (`0.7 × cosine similarity + 0.3 × ts_rank_cd`), and
- section sibling expansion for context completeness.

If the corpus grew to 100k+ chunks, the first add would be a reranker on the top ~20 hybrid hits before LLM context assembly.

### Prompt strategy

**Pre-LLM gate:** if `max(hybrid_score) < EVIDENCE_THRESHOLD` (`0.22`), return a fixed refusal — LLM is not called (avoids hallucinating on garbage retrieval).

**LLM path** (`app/services/llm.py`, `temperature=0`):

- System role scoped to LOGFLOWS logistics ops.
- Hard constraint: answer **only** from provided source chunks.
- Explicit sentinel: reply exactly `INSUFFICIENT_EVIDENCE` when chunks are related but incomplete.
- Ban invented SOP ids, phone numbers, temperatures, SLAs.
- Inline citations like `[sop-001]` requested in the answer text.

**Post-LLM gate:** if the model returns `INSUFFICIENT_EVIDENCE`, citations are cleared and a controlled refusal message is returned (catches “partially answerable” cases the score gate let through).

### Evidence threshold (`0.22` / high `0.45`)

The threshold applies to the **fused hybrid score**, not raw embedding cosine similarity.

```sql
score = sem_score * 0.7 + lex_score * 0.3
```

where `sem_score = 1 - cosine_distance` (~0–1) and `lex_score = ts_rank_cd(...)` (unbounded, often small). A cosine-style cutoff of `0.8` would reject most valid hits because semantic-only matches are scaled to `~0.7 × sem_score` before keyword contribution.

| Score | Meaning in this service |
|-------|-------------------------|
| `< 0.22` | Pre-LLM refusal (`insufficient_evidence=true`) |
| `≥ 0.22` | LLM called; confidence `"medium"` |
| `≥ 0.45` + ≥2 hits | confidence `"high"` |

Tune via `EVIDENCE_THRESHOLD` / `HIGH_CONFIDENCE_THRESHOLD` in `.env.development` after running eval queries against answerable vs unanswerable sample questions.

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
