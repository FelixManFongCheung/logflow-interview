"""Barebones FastAPI RAG service: ingest + query."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import close_db, init_db
from app.schema.schemas import Citation, IngestRequest, IngestResponse, QueryRequest, QueryResponse
from app.services.evidence import confidence_label, is_insufficient
from app.services.llm import generate_answer
from app.services.retriever import hybrid_search, ingest_documents


def _normalize_chunk_metadata(raw: object) -> dict[str, str]:
    """Coerce JSONB metadata from Postgres into citation-safe string values."""
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Open Postgres and apply schema on startup."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Classic RAG over logistics knowledge documents with tenant-scoped hybrid search.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe for local Docker and frontend checks."""
    return {"status": "ok"}


@app.post("/documents/ingest", response_model=IngestResponse)
async def ingest(body: IngestRequest) -> IngestResponse:
    """Chunk, embed, and upsert documents for a tenant."""
    try:
        result = await ingest_documents(
            body.tenant_id,
            [document.model_dump() for document in body.documents],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ingest_failed: {exc}") from exc
    return IngestResponse(tenant_id=body.tenant_id, **result)


@app.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest) -> QueryResponse:
    """Retrieve tenant-scoped chunks and answer only when evidence is strong enough."""
    try:
        hits = await hybrid_search(body.tenant_id, body.question, role=body.role)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"retrieval_failed: {exc}") from exc

    scores = [float(hit["score"]) for hit in hits]
    citations = [
        Citation(
            document_id=hit["document_id"],
            chunk_id=hit["chunk_id"],
            score=round(float(hit["score"]), 4),
            title=hit.get("title"),
            header_path=hit.get("header_path"),
            metadata=_normalize_chunk_metadata(hit.get("metadata")),
        )
        for hit in hits
    ]
    confidence = confidence_label(scores)

    if is_insufficient(scores):
        return QueryResponse(
            answer=(
                "I do not have enough evidence in the indexed knowledge base for this tenant to answer that question."
            ),
            citations=[],
            confidence="low",
            insufficient_evidence=True,
        )

    context_blocks = [f"[{hit['document_id']} / {hit['chunk_id']}]\n{hit['content']}" for hit in hits]
    try:
        answer = await generate_answer(body.question, context_blocks)
    except Exception as extra:
        raise HTTPException(status_code=502, detail=f"generation_failed: {extra}") from extra

    if answer.strip().upper().startswith("INSUFFICIENT_EVIDENCE"):
        return QueryResponse(
            answer=(
                "The retrieved documents are related but do not contain a complete answer. "
                "I will not guess missing operational details."
            ),
            citations=[],
            confidence="low",
            insufficient_evidence=True,
        )

    return QueryResponse(
        answer=answer,
        citations=citations,
        confidence=confidence,
        insufficient_evidence=False,
    )
