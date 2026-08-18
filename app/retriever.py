"""Ingest and hybrid retrieval against Postgres/pgvector."""

from typing import Any

from app.chunking import chunk_text
from app.core.config import settings
from app.db import get_pool, vector_literal
from app.llm import embed_query, embed_texts


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
                await conn.execute(
                    """
                    INSERT INTO document_chunks (
                        chunk_id, tenant_id, document_id, title, content, chunk_index, visibility, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    (
                        f"{tenant_id}:{chunk['chunk_id']}",
                        tenant_id,
                        chunk["document_id"],
                        chunk["title"],
                        chunk["content"],
                        chunk["chunk_index"],
                        chunk.get("visibility", "all"),
                        vector_literal(embedding),
                    ),
                )
    return {"documents": len(documents), "chunks": len(prepared)}


async def hybrid_search(
    tenant_id: str,
    question: str,
    match_count: int | None = None,
    role: str = "ops",
) -> list[dict[str, Any]]:
    """Call the SQL hybrid_search RPC, scoped to tenant_id (and role) in the database."""
    embedding = await embed_query(question)
    k = match_count or settings.RETRIEVE_K
    pool = get_pool()
    async with pool.connection() as conn:
        rows = await conn.execute(
            """
            SELECT chunk_id, document_id, title, content, score
            FROM hybrid_search(%s, %s, %s::vector, %s, 0.3, 0.7, %s)
            """,
            (tenant_id, question, vector_literal(embedding), k, role),
        )
        return list(await rows.fetchall())
