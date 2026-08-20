# LOGFLOWS Knowledge RAG

Classic RAG backend for logistics knowledge documents (SOPs, policies, customer handling notes, incident reports).

## What It Is

- **FastAPI** service with three routes: `GET /health`, `POST /documents/ingest`, `POST /query`
- **Retrieval:** PostgreSQL 16 + pgvector hybrid search (70% cosine similarity + 30% Postgres full-text rank)
- **Models:** Qwen embeddings + DeepSeek R1 reasoning chat model, both via OpenRouter
- **Local review path:** Docker Compose runs the API and Postgres containers (`make start`)

Indexed operational documents only — live TMS/LMS shipment rows are out of scope for this take-home.

## Architecture

![LOGFLOWS Knowledge RAG — 3-layer architecture](docs/architecture.png)

**Flow:** client → FastAPI routes → chunk/embed or hybrid retrieve → evidence gate → LLM (or controlled refusal) → grounded answer with citations.

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

Retrieve tenant-scoped chunks, apply evidence gating, then generate a grounded answer.

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

These match `app/services/chunking.py`, `sql/schema.sql`, and `app/services/llm.py`.

### Chunk size (`CHUNK_SIZE_TOKENS=256`, overlap `32`)

Sample docs are markdown SOPs with `##` / `###` sections and short tables. Flat character splitting would break tables and numbered escalation steps.

**Strategy — two-layer hierarchical chunking:**

1. **`MarkdownHeaderTextSplitter`** on `#` / `##` / `###` — keeps sections like “Delay handling”, “Temperature bands”, and “Escalation matrix” intact when they fit under the token cap.
2. **`TokenTextSplitter`** only when a section exceeds **256 tokens**. Overlap **32 tokens** applies only to those oversized splits, not between sibling sections.

Each chunk includes document title plus inherited header breadcrumbs (`header_path`) in both content and metadata. Token counting uses `cl100k_base` (same family as LangChain's `TokenTextSplitter`).

Legacy `CHUNK_SIZE` / `CHUNK_OVERLAP` char settings remain in config for backward compatibility; ingest uses the token settings above.

### Embedding model (`qwen/qwen3-embedding-4b`, 1024 dims via OpenRouter)

**Why an embedding model at all (vs “just use a big LLM”)?**  
Retrieval has to run on every query against ~50–50k+ chunks. Embedding + pgvector is orders of magnitude cheaper and faster than asking a frontier model to read the whole corpus each time. The embedder’s job is narrow: map text into a vector space where similar *meaning* is nearby. It is not asked to reason, cite, or refuse — that stays with the chat model.

**Why Qwen specifically (and not OpenAI `text-embedding-3-*`, Cohere, BGE, E5, etc.)?**

| Factor | Why Qwen3 Embedding 4B |
|--------|------------------------|
| **OpenRouter + OpenAI-compatible API** | Same `/embeddings` client as chat — no second SDK or auth path |
| **1024-dim output** | Matches `vector(1024)` in `document_chunks` / HNSW index without schema migration |
| **Strong on technical / ops text** | Logistics SOPs mix codes (`HLD-QC-*`), temperatures, and procedural language — Qwen3 embed family scores well on MTEB-style semantic tasks vs smaller general embedders |
| **4B over 0.6B** | Marginal quality gain on jargon and cross-lingual tokens at negligible ingest cost for ~50 chunks; 0.6B is fine for demos, 4B is the quality default |
| **Open weights / vendor continuity** | Same model family as other Qwen routes on OpenRouter if we swap chat models later |

**What we did not pick:** OpenAI embeddings (excellent but ties ingest to a second provider pricing table), Cohere (great rerank/embed but another integration), open local models via sentence-transformers (adds GPU/ops burden for a take-home). Qwen on OpenRouter keeps **one API key, one bill, one HTTP shape**.

**Swap note:** changing embed model requires re-ingest (vectors are not compatible across models). Chat model changes do not.

### Chat model (`deepseek/deepseek-r1-0528` via OpenRouter)

**A reasoning model, deliberately.** Retrieval still finds the evidence; the LLM’s job is to read nuanced operational text and decide what is actually supported.

The main limitation of RAG is that embedding search catches *semantically close* passages but can miss subtle nuance — cross-references between SOP sections, when a customer sheet overrides a network default, or when a doc says “out of scope” for part of the question. Hybrid search + section context helps, but the generator still has to interpret what the retrieved blocks mean together.

That is why many teams reach for large reasoning models (e.g. GPT-4.5-preview): not as a cheap vector search replacement, but as a heavy, parameter-rich reader that can weigh conflicting instructions, follow multi-step procedures, and refuse when evidence is incomplete.

**Why DeepSeek R1 specifically (when many reasoning models exist)?**

Reasoning-capable options today include OpenAI o-series, Claude “extended thinking”, Gemini thinking, Qwen QwQ, Llama reasoning fine-tunes, NVIDIA Nemotron, distilled R1 variants, etc. **`deepseek/deepseek-r1-0528` was chosen as a practical default on OpenRouter because:**

| Factor | Why DeepSeek R1 0528 |
|--------|----------------------|
| **Reasoning-native** | Trained for chain-of-thought — better at reconciling multiple SOP blocks, overrides, and “out of scope” boundaries than a plain instruction model |
| **OpenRouter availability** | Stable model slug, multiple providers, OpenAI-compatible `/chat/completions` — no custom “thinking tokens” API in this codebase yet |
| **Open-weight lineage** | Same R1 family widely benchmarked against o1-class models; easy to cite and reproduce in interviews |
| **Grounded-use fit** | With `temperature=0` and strict prompts, R1 follows “answer only from sources / emit `INSUFFICIENT_EVIDENCE`” reliably |
| **Cost vs frontier closed models** | Cheaper than GPT-4.5/o3-class closed APIs for a take-home, while still meaningfully stronger than free 8B instruct models on nuance |

**Reasonable alternatives (not used here, same swap via `LLM_MODEL`):**

- **`openai/o3-mini` / `openai/o4-mini`** — strong closed reasoning; higher cost, same OpenRouter path
- **`qwen/qwq-32b-preview`** — Qwen reasoning line; good if staying in Qwen ecosystem end-to-end
- **`deepseek/deepseek-r1-distill-qwen-32b`** — faster/cheaper distill; less depth on messy multi-doc synthesis
- **Free `:free` routers** — fine for smoke tests; unstable availability and weaker nuance handling for partial/refusal cases

We did **not** pick a reasoning model to replace retrieval — only to **interpret** what hybrid search returns.

**Tradeoffs accepted for this take-home:**

- **Cost & latency** — reasoning models are slower and billed per token (unlike a free instruct route). Reviewers need a funded OpenRouter key.
- **Still grounded** — prompts and evidence gates unchanged; R1 must answer only from retrieved sources or return `INSUFFICIENT_EVIDENCE`.
- **Swappable** — `LLM_MODEL` is env-driven; embeddings stay on Qwen so chat model experiments do not require re-indexing.

**On the future:** capabilities and pricing move quickly — o-series, R1 variants, QwQ, and Gemini thinking will keep shifting. This stack decouples **retrieval** (Postgres hybrid search + Qwen vectors) from **generation** (OpenRouter model id) so either side can be upgraded independently.

### Vector store (PostgreSQL 16 + pgvector, hybrid SQL function)

One database for vectors, full-text search, tenant isolation, and role-based visibility — no separate vector DB for this scope.

- **Vector index:** HNSW on `embedding` with `vector_cosine_ops`
- **Lexical leg:** generated `tsvector` column + GIN index; `ts_rank_cd` scores keyword matches (policy ids like `SOP-001`, ticket prefixes like `HLD-QC-*`, customer codes)
- **Retrieval RPC:** `hybrid_search(...)` in `sql/schema.sql` runs semantic and lexical searches in parallel, full-outer-joins on `chunk_id`, ranks by weighted score
- **Section expansion:** when a hit lands in a markdown section, sibling chunks under the same `header_path` are included (up to `RETRIEVE_MAX_EXPANDED=24`) so “delay handling” returns the full procedure block, not one sentence
- **Citations vs LLM context:** `hybrid_search` returns `is_primary_hit` — only direct top-k hits appear in API `citations`; section siblings are labeled `SECTION CONTEXT` in the LLM prompt only

`tenant_id` and `visibility`/`role` filters are enforced inside the SQL function.

### Reranking — not used

No cross-encoder or LLM reranker after retrieval. For ~50 chunks and `RETRIEVE_K=6`, hybrid fusion plus section expansion was sufficient without a second model pass.

At 100k+ chunks, add a reranker on the top ~20 hybrid hits before LLM context assembly.

### Prompt strategy

**Pre-LLM gate** (`app/services/evidence.py`): if `max(primary_hybrid_score) < EVIDENCE_THRESHOLD` (`0.22`), return a fixed refusal without calling the LLM. Scoring uses **primary hits only**, not section-expanded siblings.

**LLM path** (`app/services/prompts.py` + `app/services/context.py` + `app/services/llm.py`):

- Domain-specific system prompt for LOGFLOWS SOPs, customer sheets, incidents, and policies
- Each retrieved row is formatted with: `PRIMARY SOURCE` vs `SECTION CONTEXT`, `document_id`, `chunk_id`, `title`, `header_path`, `h1`/`h2`/`h3` metadata, `retrieval_score`, and body text
- **Primary sources** = direct hybrid-search hits (also returned as API citations)
- **Section context** = sibling chunks from the same markdown section (LLM context only — not listed as citations)
- Answer only from provided sources; honor “out of scope” sections; reply exactly `INSUFFICIENT_EVIDENCE` when incomplete
- Inline citations like `[sop-001]`; `LLM_TEMPERATURE=0`

**Post-LLM gate:** if the model returns `INSUFFICIENT_EVIDENCE`, citations are cleared and a controlled refusal is returned (handles partially answerable questions the score gate passed).

### Evidence threshold (`0.22` / high `0.45`)

The threshold applies to the **fused hybrid score**, not raw embedding cosine similarity:

```sql
score = sem_score * 0.7 + lex_score * 0.3
```

- `sem_score = 1 - cosine_distance` (roughly 0–1)
- `lex_score = ts_rank_cd(...)` (Postgres full-text rank — different scale, often small)

A cosine-style cutoff of `0.8` would reject most valid hits because semantic-only matches are scaled to `~0.7 × sem_score` before keyword contribution.

| Score | Behaviour |
|-------|-----------|
| `< 0.22` | Pre-LLM refusal (`insufficient_evidence=true`, LLM skipped) |
| `≥ 0.22` | LLM called; confidence `"medium"` unless higher bar met |
| `≥ 0.45` with ≥2 hits | confidence `"high"` |

Tune via `EVIDENCE_THRESHOLD` / `HIGH_CONFIDENCE_THRESHOLD` in `.env.development`.

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
- No reranking after hybrid search — top-k order is fused score only
- Full-text leg uses Postgres `english` config — non-English or heavy jargon/code matching is imperfect without custom dictionaries
- Citations return chunk pointers (`chunk_id`, `header_path`, score) but not chunk body text in the API response

### Generation & product scope
- No streaming responses — answers return only after full LLM completion
- Live TMS/LMS operational data (shipment status, rates, contracts) is intentionally out of scope
- Reasoning chat model adds latency and OpenRouter cost per query

### Operations
- No request tracing / eval dashboard (Langfuse, Prometheus hooks not wired in this take-home)
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
