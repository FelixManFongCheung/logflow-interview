"""Pydantic request/response schemas for ingest and query."""

from typing import Literal

from pydantic import BaseModel, Field


class IngestDocument(BaseModel):
    """A single knowledge document to index."""

    id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    text: str = Field(..., min_length=1, max_length=200_000)
    visibility: Literal["ops", "cs", "all"] = "all"


class IngestRequest(BaseModel):
    """POST /documents/ingest body."""

    tenant_id: str = Field(..., min_length=1, max_length=128)
    documents: list[IngestDocument] = Field(..., min_length=1)


class IngestResponse(BaseModel):
    """Ingest result counts."""

    tenant_id: str
    documents: int
    chunks: int


class QueryRequest(BaseModel):
    """POST /query body."""

    tenant_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=3, max_length=2000)
    role: Literal["ops", "cs", "admin"] = "ops"


class Citation(BaseModel):
    """A retrieved chunk used as evidence."""

    document_id: str
    chunk_id: str
    score: float
    title: str | None = None


class QueryResponse(BaseModel):
    """Grounded answer plus retrieval diagnostics."""

    answer: str
    citations: list[Citation]
    confidence: Literal["high", "medium", "low"]
    insufficient_evidence: bool
