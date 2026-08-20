"""Pydantic request/response schemas for ingest and query."""

from typing import Literal

from pydantic import BaseModel, Field


class IngestDocument(BaseModel):
    id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    text: str = Field(..., min_length=1, max_length=200_000)
    visibility: Literal["ops", "cs", "all"] = "all"


class IngestRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    documents: list[IngestDocument] = Field(..., min_length=1)


class IngestResponse(BaseModel):
    tenant_id: str
    documents: int
    chunks: int


class QueryRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=3, max_length=2000)
    role: Literal["ops", "cs", "admin"] = "ops"


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    score: float
    title: str | None = None
    header_path: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: Literal["high", "medium", "low"]
    insufficient_evidence: bool
