# LOGFLOWS Knowledge RAG

Classic RAG backend for logistics **knowledge documents** (SOPs, policies, incidents). Not a chatbot, not LangGraph: two JSON endpoints any frontend can call.

## Why Postgres + pgvector (not a separate vector DB)

| Option | Hybrid search | Tenant filter | Take-home fit |
|--------|---------------|---------------|----------------|
| **Postgres + pgvector** | `tsvector` + cosine in one SQL function | `WHERE tenant_id = $1` in the same query | Best default |
| Supabase | Same Postgres function, exposed as `rpc('hybrid_search', …)` | Same | Hosted version of this schema |
| Chroma / FAISS | Vector only unless you add a second index | Easy to forget in app code | Weaker for SOP **ids** (`SOP-001`) |
| Azure AI Search | Strong hybrid | Native filters | Production mapping, extra account |

This repo uses **local Docker Postgres**. The function in `sql/schema.sql` is written so you can paste it into Supabase SQL editor and call:

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
  → validate → section-aware chunk → embed → DELETE+INSERT chunks (per tenant + document_id)

POST /query
  → embed question → hybrid_search(tenant_id, role)   ← isolation in SQL
  → if max(score) < threshold: refuse (no LLM guess)
  → else LLM with chunks only + citations
```

Live TMS/LMS shipment rows are **out of scope**. This service answers from indexed documents. Operational truth would be a later API-tool layer.

## Setup

```bash
cp .env.example .env.development
# set OPENAI_API_KEY (or OPENAI_BASE_URL for a compatible provider)

make db          # Postgres + pgvector
make install
make dev         # http://localhost:8000/docs
make seed        # 5 sample logistics docs → tenant logflows-demo
make test
```

`POSTGRES_HOST=localhost` when the API runs on the host. Use `db` only if the API also runs in Compose.

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
  "answer": "...notify QC within 10 minutes...",
  "citations": [
    {"document_id": "sop-001", "chunk_id": "logflows-demo:sop-001:0", "score": 0.82, "title": "Cold Chain SOP"}
  ],
  "confidence": "medium",
  "insufficient_evidence": false
}
```

CORS defaults to `*` so a TMS web app or mobile client can call these two routes.

## Sample data and expected behaviour

| Question | Expected |
|----------|----------|
| What should we do if a cold-chain delivery is delayed? | **Answerable** from `sop-001` (30 min, QC, temperature band) |
| What should we do after a reefer logger gap on yogurt to Berlin? | **Partial** — `inc-2026-014` describes one incident; it does not replace SOP-001 |
| What is ACME’s contracted freight rate to Hamburg? | **Unanswerable** — `insufficient_evidence: true`, no invented rates |

Documents live in `data/samples/`. Visibility: warehouse escalation and the incident are `ops`-only; `role=cs` should not retrieve them.

## Key decisions

| Choice | Value | Why |
|--------|--------|-----|
| Chunking | ~900 chars, heading/paragraph split, 120 overlap | Avoid cutting SOP steps in half |
| Embeddings | `text-embedding-3-small` (1536-d) | Cheap, good enough for 5–10k chunks |
| Vector store | pgvector HNSW + GIN on `tsvector` | Hybrid: semantic + keyword (`SOP-001`) |
| Hybrid weights | 0.7 cosine, 0.3 full-text | Keywords help ids; semantics help paraphrases |
| Evidence gate | refuse if top hybrid score `< 0.22` | Stops “helpful” hallucination |
| Access control | `tenant_id` **and** `visibility`/`role` in SQL | Prompt-only isolation is not isolation |
| LLM | temperature 0, “ONLY from chunks” | Grounding |

Changing embedding model dimensions requires changing `vector(1536)` in `sql/schema.sql`.

## Production notes (not built)

- **Auth:** gateway JWT; map to `tenant_id` / `role`. Do not trust tenant in the body in production.
- **Updates/deletes:** ingest already replaces chunks for `(tenant_id, document_id)`. Add `DELETE /documents/{id}`.
- **Scale (1M docs, 100 tenants):** partition or schema-per-tenant; HNSW per partition; async embed workers; cache query embeddings.
- **Observability:** log tenant, user, chunk ids, scores, latency, token usage — not full SOP text.
- **Privacy:** SOPs may include customer names; keep indexes in-region; redact before third-party LLMs if required.
- **Cost:** embed once at ingest; retrieve_k=6; skip LLM on refusal.
- **Hallucination remaining:** LLM can still misread a retrieved chunk; citations let ops verify. Add an eval set (hit@k, faithfulness) before production.

## Project layout

```text
app/main.py          FastAPI: /documents/ingest, /query, /health
app/retriever.py     ingest + hybrid_search RPC call
app/chunking.py      section-aware windows
app/llm.py           embeddings + grounded chat
app/evidence.py      score → refuse / confidence
sql/schema.sql       table + hybrid_search()  (Supabase RPC)
data/samples/        five logistics documents
```

No LangGraph: this is a linear retrieve-then-generate pipeline.
