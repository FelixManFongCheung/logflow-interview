CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'all',
    metadata JSONB NOT NULL DEFAULT '{}',
    header_path TEXT,
    embedding vector(1024) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(header_path, ''))
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS header_path TEXT;

CREATE INDEX IF NOT EXISTS document_chunks_tenant_idx
    ON document_chunks (tenant_id);

CREATE INDEX IF NOT EXISTS document_chunks_document_idx
    ON document_chunks (tenant_id, document_id);

CREATE INDEX IF NOT EXISTS document_chunks_header_path_idx
    ON document_chunks (tenant_id, header_path);

CREATE INDEX IF NOT EXISTS document_chunks_metadata_idx
    ON document_chunks USING gin (metadata);

CREATE INDEX IF NOT EXISTS document_chunks_tsv_idx
    ON document_chunks USING gin (tsv);

-- Small-corpus default; switch to ivfflat lists when row counts grow.
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

DROP FUNCTION IF EXISTS hybrid_search(TEXT, TEXT, vector, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION, TEXT);
DROP FUNCTION IF EXISTS hybrid_search(TEXT, TEXT, vector, INTEGER, DOUBLE PRECISION, DOUBLE PRECISION, TEXT, BOOLEAN, INTEGER);

CREATE OR REPLACE FUNCTION hybrid_search(
    p_tenant_id TEXT,
    p_query_text TEXT,
    p_query_embedding vector(1024),
    p_match_count INTEGER DEFAULT 8,
    p_full_text_weight DOUBLE PRECISION DEFAULT 0.5,
    p_semantic_weight DOUBLE PRECISION DEFAULT 0.5,
    p_role TEXT DEFAULT 'ops',
    p_expand_sections BOOLEAN DEFAULT TRUE,
    p_max_results INTEGER DEFAULT NULL
)
RETURNS TABLE (
    chunk_id TEXT,
    document_id TEXT,
    title TEXT,
    content TEXT,
    metadata JSONB,
    header_path TEXT,
    score DOUBLE PRECISION,
    is_primary_hit BOOLEAN
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
            c.metadata,
            c.header_path,
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
            c.metadata,
            c.header_path,
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
            COALESCE(s.metadata, l.metadata) AS metadata,
            COALESCE(s.header_path, l.header_path) AS header_path,
            (
                COALESCE(s.sem_score, 0) * p_semantic_weight
                + COALESCE(l.lex_score, 0) * p_full_text_weight
            ) AS score
        FROM semantic s
        FULL OUTER JOIN lexical l ON s.chunk_id = l.chunk_id
    ),
    ranked AS (
        SELECT
            combined.chunk_id,
            combined.document_id,
            combined.title,
            combined.content,
            combined.metadata,
            combined.header_path,
            combined.score
        FROM combined
        ORDER BY combined.score DESC
        LIMIT p_match_count
    ),
    section_hits AS (
        SELECT
            r.document_id,
            r.header_path,
            MAX(r.score) AS section_score
        FROM ranked r
        WHERE p_expand_sections
          AND r.header_path IS NOT NULL
          AND btrim(r.header_path) <> ''
        GROUP BY r.document_id, r.header_path
    ),
    expanded_sections AS (
        SELECT
            c.chunk_id,
            c.document_id,
            c.title,
            c.content,
            c.metadata,
            c.header_path,
            sh.section_score AS score,
            c.chunk_index
        FROM document_chunks c
        INNER JOIN section_hits sh
            ON c.document_id = sh.document_id
           AND c.header_path = sh.header_path
        WHERE c.tenant_id = p_tenant_id
          AND (
              p_role = 'admin'
              OR c.visibility = 'all'
              OR c.visibility = p_role
          )
    ),
    standalone_hits AS (
        SELECT
            r.chunk_id,
            r.document_id,
            r.title,
            r.content,
            r.metadata,
            r.header_path,
            r.score,
            c.chunk_index
        FROM ranked r
        INNER JOIN document_chunks c ON c.chunk_id = r.chunk_id
        WHERE p_expand_sections
          AND (r.header_path IS NULL OR btrim(r.header_path) = '')
    ),
    flat_hits AS (
        SELECT
            r.chunk_id,
            r.document_id,
            r.title,
            r.content,
            r.metadata,
            r.header_path,
            r.score,
            c.chunk_index
        FROM ranked r
        LEFT JOIN document_chunks c ON c.chunk_id = r.chunk_id
        WHERE NOT p_expand_sections
    ),
    merged AS (
        SELECT chunk_id, document_id, title, content, metadata, header_path, score, chunk_index
        FROM expanded_sections
        UNION ALL
        SELECT chunk_id, document_id, title, content, metadata, header_path, score, chunk_index
        FROM standalone_hits
        UNION ALL
        SELECT chunk_id, document_id, title, content, metadata, header_path, score, chunk_index
        FROM flat_hits
    )
    SELECT
        merged.chunk_id,
        merged.document_id,
        merged.title,
        merged.content,
        merged.metadata,
        merged.header_path,
        merged.score,
        EXISTS (
            SELECT 1
            FROM ranked r
            WHERE r.chunk_id = merged.chunk_id
        ) AS is_primary_hit
    FROM merged
    ORDER BY merged.score DESC, merged.chunk_index ASC
    LIMIT COALESCE(p_max_results, GREATEST(p_match_count * 4, p_match_count));
$$;
