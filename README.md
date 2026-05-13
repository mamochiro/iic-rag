# RAG Phase 1

Thinnest possible RAG over Confluence. Phase 1 of a multi-phase enterprise RAG build.

## Setup

1. Start Postgres with pgvector:
   ```
   docker run -d --name rag-pg -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag \
       -e POSTGRES_DB=rag -p 5437:5432 pgvector/pgvector:pg16
   ```
2. Apply schema: `psql $DATABASE_URL -f sql/schema.sql`
3. Copy `.env.example` to `.env` and fill in values
4. Install deps: `uv sync`

## Use

```
uv run python cli.py ingest --space ENG --limit 20   # start small
uv run python cli.py query "How does our auth work?"
```
