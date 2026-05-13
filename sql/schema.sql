CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL DEFAULT 'confluence',
    source_id TEXT NOT NULL,        -- e.g., confluence page id
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    space_key TEXT,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    token_count INT NOT NULL,
    embedding vector(1024) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_source_idx
    ON chunks (source_type, source_id);
