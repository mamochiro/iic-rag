import psycopg
from datetime import datetime, timezone
from pgvector.psycopg import register_vector
from .config import settings
from .models import EmbeddedChunk, Retrieved


def _connect():
    conn = psycopg.connect(settings.database_url, autocommit=False)
    register_vector(conn)
    return conn


def upsert_chunks(chunks: list[EmbeddedChunk]) -> int:
    sql = """
        INSERT INTO chunks (source_type, source_id, source_url, title, space_key,
                            chunk_index, content, token_count, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_type, source_id, chunk_index) DO UPDATE SET
            source_url = EXCLUDED.source_url,
            title = EXCLUDED.title,
            space_key = EXCLUDED.space_key,
            content = EXCLUDED.content,
            token_count = EXCLUDED.token_count,
            embedding = EXCLUDED.embedding,
            updated_at = NOW();
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.executemany(sql, [
            (c.source_type, c.source_id, c.source_url, c.title, c.space_key,
             c.chunk_index, c.content, c.token_count, c.embedding)
            for c in chunks
        ])
        conn.commit()
    return len(chunks)


def search(query_embedding: list[float], top_k: int) -> list[Retrieved]:
    sql = """
        SELECT id, source_url, title, content,
               1 - (embedding <=> %s::vector) AS score
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (query_embedding, query_embedding, top_k))
        rows = cur.fetchall()
    return [
        Retrieved(chunk_id=r[0], source_url=r[1], title=r[2], content=r[3], score=r[4])
        for r in rows
    ]


def bm25_search(query_text: str, top_k: int) -> list[Retrieved]:
    sql = """
        SELECT id, source_url, title, content,
               ts_rank(tsv, plainto_tsquery('english', %s)) AS score
        FROM chunks
        WHERE tsv @@ plainto_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s;
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (query_text, query_text, top_k))
        rows = cur.fetchall()
    return [
        Retrieved(chunk_id=r[0], source_url=r[1], title=r[2], content=r[3], score=r[4])
        for r in rows
    ]


def hybrid_search(query_embedding: list[float], query_text: str, top_k: int) -> list[Retrieved]:
    """Combine vector + BM25 via RRF. Curated chunks get a score bonus."""
    fetch_k = top_k * 3

    vec_results = search(query_embedding, fetch_k)
    bm25_results = bm25_search(query_text, fetch_k)

    K = 60
    scores: dict[int, float] = {}
    meta: dict[int, Retrieved] = {}

    for rank, r in enumerate(vec_results):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0) + 1 / (K + rank + 1)
        meta[r.chunk_id] = r

    for rank, r in enumerate(bm25_results):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0) + 1 / (K + rank + 1)
        meta[r.chunk_id] = r

    # Apply curated boost — fetch curated flag for all candidate chunks
    if scores:
        curated_sql = "SELECT id FROM chunks WHERE id = ANY(%s) AND curated = TRUE;"
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(curated_sql, (list(scores.keys()),))
            curated_ids = {row[0] for row in cur.fetchall()}
        BOOST = 0.02
        for cid in curated_ids:
            scores[cid] += BOOST

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [Retrieved(**{**meta[cid].model_dump(), "score": score}) for cid, score in ranked]


def set_curated(source_url: str, curated: bool) -> int:
    sql = "UPDATE chunks SET curated = %s WHERE source_url = %s;"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (curated, source_url))
        count = cur.rowcount
        conn.commit()
    return count


def log_query(question: str, rewritten: str, retrieved_urls: list[str],
              answer: str, latency_ms: int) -> None:
    sql = """
        INSERT INTO query_log (question, rewritten_question, retrieved_urls, answer, latency_ms)
        VALUES (%s, %s, %s, %s, %s);
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (question, rewritten, retrieved_urls, answer, latency_ms))
        conn.commit()


def get_last_synced(source_type: str, source_key: str) -> datetime | None:
    sql = "SELECT last_synced_at FROM sync_log WHERE source_type = %s AND source_key = %s;"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (source_type, source_key))
        row = cur.fetchone()
    return row[0] if row else None


def set_last_synced(source_type: str, source_key: str, pages: int, chunks: int) -> None:
    sql = """
        INSERT INTO sync_log (source_type, source_key, last_synced_at, pages_fetched, chunks_upserted)
        VALUES (%s, %s, NOW(), %s, %s)
        ON CONFLICT (source_type, source_key) DO UPDATE SET
            last_synced_at  = NOW(),
            pages_fetched   = EXCLUDED.pages_fetched,
            chunks_upserted = EXCLUDED.chunks_upserted;
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (source_type, source_key, pages, chunks))
        conn.commit()
