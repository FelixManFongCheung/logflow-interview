-- Classic RAG store: tenant-scoped chunks + hybrid search RPC.
-- Same function signature works locally and as a Supabase RPC:
--   supabase.rpc('hybrid_search', {
--     p_tenant_id, p_query_text, p_query_embedding, p_match_count, p_role
--   })

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'all',
    embedding vector(1536) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_chunks_tenant_idx
    ON document_chunks (tenant_id);

CREATE INDEX IF NOT EXISTS document_chunks_document_idx
    ON document_chunks (tenant_id, document_id);

CREATE INDEX IF NOT EXISTS document_chunks_tsv_idx
    ON document_chunks USING gin (tsv);

-- Small-corpus default; switch to ivfflat lists when row counts grow.
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION hybrid_search(
    p_tenant_id TEXT,
    p_query_text TEXT,
    p_query_embedding vector(1536),
    p_match_count INTEGER DEFAULT 8,
    p_full_text_weight DOUBLE PRECISION DEFAULT 0.3,
    p_semantic_weight DOUBLE PRECISION DEFAULT 0.7,
    p_role TEXT DEFAULT 'ops'
)
RETURNS TABLE (
    chunk_id TEXT,
    document_id TEXT,
    title TEXT,
    content TEXT,
    score DOUBLE PRECISION
)
LANGUAGE sql
STABLE
AS $$
    WITH semantic AS (
        SELECT
            c.chunk_id,
            c.document_id,
            c.title,
            c.content,
            GREATEST(0::double precision, (1 - (c.embedding <=> p_query_embedding))::double precision) AS sem_score
        FROM document_chunks c
        WHERE c.tenant_id = p_tenant_id
          AND (
              p_role = 'admin'
              OR c.visibility = 'all'
              OR c.visibility = p_role
          )
        ORDER BY c.embedding <=> p_query_embedding
        LIMIT GREATEST(p_match_count * 4, 16)
    ),
    query AS (
        SELECT NULLIF(btrim(p_query_text), '') AS q
    ),
    lexical AS (
        SELECT
            c.chunk_id,
            c.document_id,
            c.title,
            c.content,
            ts_rank_cd(c.tsv, plainto_tsquery('english', query.q))::double precision AS lex_score
        FROM document_chunks c
        CROSS JOIN query
        WHERE c.tenant_id = p_tenant_id
          AND query.q IS NOT NULL
          AND (
              p_role = 'admin'
              OR c.visibility = 'all'
              OR c.visibility = p_role
          )
          AND c.tsv @@ plainto_tsquery('english', query.q)
        ORDER BY lex_score DESC
        LIMIT GREATEST(p_match_count * 4, 16)
    ),
    combined AS (
        SELECT
            COALESCE(s.chunk_id, l.chunk_id) AS chunk_id,
            COALESCE(s.document_id, l.document_id) AS document_id,
            COALESCE(s.title, l.title) AS title,
            COALESCE(s.content, l.content) AS content,
            (
                COALESCE(s.sem_score, 0) * p_semantic_weight
                + COALESCE(l.lex_score, 0) * p_full_text_weight
            ) AS score
        FROM semantic s
        FULL OUTER JOIN lexical l ON s.chunk_id = l.chunk_id
    )
    SELECT combined.chunk_id, combined.document_id, combined.title, combined.content, combined.score
    FROM combined
    ORDER BY combined.score DESC
    LIMIT p_match_count;
$$;
