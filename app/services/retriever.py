"""Ingest and hybrid retrieval against Postgres/pgvector."""

import json
from typing import Any

from langsmith import traceable

from app.core.config import settings
from app.core.db import get_pool, vector_literal
from app.services.chunking import chunk_text
from app.services.llm import embed_query, embed_texts


@traceable(name="ingest_documents", run_type="retriever")
async def ingest_documents(tenant_id: str, documents: list[dict[str, str]]) -> dict[str, int]:
    """Replace chunks for each document id in the tenant, then insert new ones.

    Returns:
        Counts of documents and chunks written.
    """
    prepared: list[dict[str, Any]] = []
    for document in documents:
        chunks = chunk_text(document["id"], document["title"], document["text"])
        for chunk in chunks:
            chunk["visibility"] = document.get("visibility", "all")
            prepared.append(chunk)

    embeddings = await embed_texts([chunk["content"] for chunk in prepared])
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            for document in documents:
                await conn.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE tenant_id = %s AND document_id = %s
                    """,
                    (tenant_id, document["id"]),
                )
            for chunk, embedding in zip(prepared, embeddings, strict=True):
                chunk_metadata = chunk.get("metadata") or {}
                header_path = chunk_metadata.get("header_path")
                await conn.execute(
                    """
                    INSERT INTO document_chunks (
                        chunk_id, tenant_id, document_id, title, content,
                        chunk_index, visibility, metadata, header_path, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::vector)
                    """,
                    (
                        f"{tenant_id}:{chunk['chunk_id']}",
                        tenant_id,
                        chunk["document_id"],
                        chunk["title"],
                        chunk["content"],
                        chunk["chunk_index"],
                        chunk.get("visibility", "all"),
                        json.dumps(chunk_metadata),
                        header_path,
                        vector_literal(embedding),
                    ),
                )
    return {"documents": len(documents), "chunks": len(prepared)}


@traceable(name="hybrid_search", run_type="retriever")
async def hybrid_search(
    tenant_id: str,
    question: str,
    match_count: int | None = None,
    role: str = "ops",
) -> list[dict[str, Any]]:
    """Call the SQL hybrid_search RPC, scoped to tenant_id (and role) in the database."""
    embedding = await embed_query(question)
    k = match_count or settings.RETRIEVE_POOL_K
    pool = get_pool()
    async with pool.connection() as conn:
        rows = await conn.execute(
            """
            SELECT chunk_id, document_id, title, content, metadata, header_path, score, is_primary_hit
            FROM hybrid_search(%s, %s, %s::vector, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                question,
                vector_literal(embedding),
                k,
                settings.HYBRID_LEXICAL_WEIGHT,
                settings.HYBRID_SEMANTIC_WEIGHT,
                role,
                settings.EXPAND_SECTION_SIBLINGS,
                settings.RETRIEVE_MAX_EXPANDED,
            ),
        )
        return list(await rows.fetchall())
