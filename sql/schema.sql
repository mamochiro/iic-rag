CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL DEFAULT 'confluence',
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    space_key TEXT,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    token_count INT NOT NULL,
    embedding vector(1024) NOT NULL,
    curated BOOLEAN NOT NULL DEFAULT FALSE,
    tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_source_idx
    ON chunks (source_type, source_id);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx
    ON chunks USING GIN (tsv);

CREATE TABLE IF NOT EXISTS sync_log (
    source_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pages_fetched INT NOT NULL DEFAULT 0,
    chunks_upserted INT NOT NULL DEFAULT 0,
    PRIMARY KEY (source_type, source_key)
);

CREATE TABLE IF NOT EXISTS query_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    question TEXT NOT NULL,
    rewritten_question TEXT,
    retrieved_urls TEXT[],
    answer TEXT,
    latency_ms INT
);
