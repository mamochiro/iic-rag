# IIC RAG — Enterprise Knowledge Base

Retrieval-Augmented Generation over Confluence, Jira, and GitLab. Answers questions in natural language with cited sources. No LangChain, no LlamaIndex — every layer is explicit and tunable.

---

## Big Picture

```
┌─────────────────────────────────────────────────────────────────────┐
│  DATA SOURCES          INGEST PIPELINE            STORAGE           │
│                                                                      │
│  Confluence ──────▶  Fetcher (HTML strip)  ──▶                      │
│  Jira        ──────▶  Chunker (tiktoken)   ──▶  Postgres            │
│  GitLab      ──────▶  Embedder (NVIDIA)    ──▶  + pgvector          │
│                                                  + tsvector          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  QUERY PIPELINE                                                      │
│                                                                      │
│  Question                                                            │
│    │                                                                 │
│    ▼                                                                 │
│  [Rewriter]  ── llama-3.3-70b generates 3 phrasings                 │
│    │                                                                 │
│    ├──▶ [Vector Search]  cosine distance on HNSW index              │
│    └──▶ [BM25 Search]    Postgres tsvector full-text                │
│               │                                                      │
│               ▼                                                      │
│         [RRF Fusion]  Reciprocal Rank Fusion (k=60)                 │
│               │                                                      │
│               ▼                                                      │
│         [Reranker]  llama-3.3-70b listwise reranker                 │
│               │                                                      │
│               ▼                                                      │
│         [Generator]  cited answer with [1] [2] [3] footnotes        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  INTERFACE                                                           │
│                                                                      │
│  Streamlit UI  ◀──▶  FastAPI  ◀──▶  CLI (typer)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **LLM** | NVIDIA NIM `meta/llama-3.3-70b-instruct` | Free-tier hosted, strong instruction following |
| **Embeddings** | NVIDIA NIM `nvidia/nv-embedqa-e5-v5` | Free, 1024-dim, retrieval-optimized |
| **Vector store** | `pgvector` + Postgres HNSW index | No extra infra; cosine similarity at scale |
| **Full-text search** | Postgres `tsvector` (generated column) | BM25-grade keyword search, no Elasticsearch |
| **Hybrid ranking** | Reciprocal Rank Fusion (hand-written, k=60) | Combines vector + BM25 without a black box |
| **Reranker** | LLM listwise reranker (same NVIDIA LLM) | Improves top-k precision; no paid reranker API |
| **Query expansion** | Multi-query rewriting (3 phrasings) | Improves recall for ambiguous questions |
| **Confluence source** | `atlassian-python-api` | Official client with CQL incremental sync |
| **Jira source** | `atlassian-python-api` | JQL + cursor-based pagination (`nextPageToken`) |
| **GitLab source** | `python-gitlab` | Wiki pages + all `.md` files per project |
| **Chunking** | `tiktoken` cl100k_base | Token-accurate, 1000 tok / 200 overlap, title-prefixed |
| **API** | FastAPI + background tasks | Ingest runs async; job status via `/jobs/{id}` |
| **UI** | Streamlit | Chat history, source expanders, sync status sidebar |
| **CLI** | `typer` + `rich` | Ingest, query, status, curate — all scriptable |
| **Config** | `pydantic-settings` | Type-safe `.env` loading with sensible defaults |
| **DB driver** | `psycopg3` + `psycopg-pool` | Connection pool (min=2, max=10) for concurrent use |

### What was deliberately skipped

| Skipped | Reason |
|---|---|
| LangChain / LlamaIndex | Hides the pipeline; hard to debug and tune |
| Elasticsearch | Postgres `tsvector` is enough for BM25 at this scale |
| Redis cache | Add only when load demands it |
| Celery / task queues | In-process background tasks are sufficient |
| Dedicated reranker API | NVIDIA reranker returned 404 on free tier; LLM listwise is equivalent |

---

## Setup

### 1. Start Postgres with pgvector

```bash
docker run -d --name rag-pg \
  -e POSTGRES_USER=rag \
  -e POSTGRES_PASSWORD=rag \
  -e POSTGRES_DB=rag \
  -p 5437:5432 \
  pgvector/pgvector:pg16
```

### 2. Apply schema

```bash
psql postgresql://rag:rag@localhost:5437/rag -f sql/schema.sql
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:

```env
NVIDIA_API_KEY=nvapi-...            # https://build.nvidia.com
CONFLUENCE_URL=https://yourorg.atlassian.net
CONFLUENCE_USERNAME=you@yourorg.com
CONFLUENCE_API_TOKEN=...
GITLAB_URL=https://gitlab.yourorg.com
GITLAB_TOKEN=glpat-...
API_KEY=your-secret-api-key         # for FastAPI auth
```

### 4. Install dependencies

```bash
uv sync
```

---

## Ingest

```bash
# Confluence space
uv run python cli.py ingest --space IIC

# Jira project
uv run python cli.py ingest-jira --project IIC

# GitLab project (by ID or namespace/path)
uv run python cli.py ingest-gl --project 499

# Incremental sync (only content changed since last run)
uv run python cli.py sync --space IIC --project IIC --gl 499

# List accessible GitLab projects
uv run python cli.py gl-list
```

---

## Query

```bash
# Ask via CLI
uv run python cli.py query "How does the auth flow work?"

# Show the rewritten query forms
uv run python cli.py query "How does the auth flow work?" --show-rewritten
```

---

## API

Start the API server:

```bash
uv run uvicorn api:app --reload
```

Endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/query` | Ask a question |
| `POST` | `/ingest/confluence` | Ingest a Confluence space (background) |
| `POST` | `/ingest/jira` | Ingest a Jira project (background) |
| `POST` | `/ingest/gitlab` | Ingest a GitLab project (background) |
| `GET` | `/jobs/{job_id}` | Poll ingest job status |
| `GET` | `/status` | Last sync times per source |
| `GET` | `/logs` | Recent query log |
| `GET` | `/chunks/count` | Indexed chunk counts by source |

All endpoints except `/health` require `X-API-Key` header.

Example:

```bash
curl -s http://localhost:8000/query \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "How does the IIC payment flow work?"}' | jq .
```

---

## Streamlit UI

```bash
uv run streamlit run app.py
```

Opens at `http://localhost:8501`. Shows chat history, cited sources, sync status, and chunk counts per source.

---

## Curating high-quality chunks

Mark specific pages as "curated" to give their chunks a retrieval score boost (+0.02 on top of RRF score):

```bash
uv run python cli.py curate https://yourorg.atlassian.net/wiki/spaces/IIC/pages/123
uv run python cli.py uncurate https://yourorg.atlassian.net/wiki/spaces/IIC/pages/123
```

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full Mermaid diagram and step-by-step flow.
