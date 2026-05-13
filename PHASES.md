# RAG Implementation Phases

## Phase 1 — Confluence vertical slice ✅

### Infrastructure
- [x] Start Postgres with pgvector: `docker run -d --name rag-pg -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag -e POSTGRES_DB=rag -p 5437:5432 pgvector/pgvector:pg16`
- [x] Apply schema: `psql $DATABASE_URL -f sql/schema.sql`
- [x] Copy `.env.example` → `.env` and fill in all values

### Dependencies
- [x] Install uv and run `uv sync`
- [x] NVIDIA API key working (embeddings + generation)

### Credentials
- [x] `NVIDIA_API_KEY` set and valid
- [x] `CONFLUENCE_URL` / `CONFLUENCE_USERNAME` / `CONFLUENCE_API_TOKEN` set
- [x] `DATABASE_URL` points to running Postgres

### Smoke test
- [x] `uv run python cli.py ingest --space IIC --limit 20` completes without errors
- [x] `SELECT COUNT(*) FROM chunks;` returns > 0
- [x] `uv run python cli.py query "What is IIC Portal?"` returns cited answer
- [x] Re-run ingest on same space — row count stays the same (upsert, not duplicate)

### Full ingest
- [x] Run ingest without `--limit` on IIC space (14 pages, 33 chunks)

---

## Phase 2 — Hybrid retrieval ✅

- [x] Add `tsvector` column + GIN index to `chunks`
- [x] Auto-update trigger on insert/update
- [x] `store.bm25_search()` using `ts_rank` + `plainto_tsquery`
- [x] `store.hybrid_search()` combining vector + BM25 via Reciprocal Rank Fusion (RRF)
- [x] `query.py` uses hybrid search
- [ ] Populate `eval/questions.yaml` with 30–50 real questions
- [ ] Eval harness script (`eval/run_eval.py`)
- [ ] Reranker (Cohere free tier or similar)

---

## Phase 3 — Jira source ✅

- [x] `src/jira.py` fetching issues (In Progress + Done) via `enhanced_jql`
- [x] ADF (Atlassian Document Format) text extraction
- [x] `source_type` field on `Chunk` model — multi-source aware
- [x] `ingest-jira` CLI command
- [x] 102 Jira issues indexed (142 chunks) for IIC project
- [ ] GitLab source (`src/gitlab.py`)
- [ ] Figma source (`src/figma.py`)

---

## Phase 4 — Incremental sync ✅

- [x] `sync_log` table tracking last sync per source
- [x] Confluence: CQL `lastModified >` filter for incremental fetch
- [x] Jira: JQL `updated >=` filter for incremental fetch
- [x] `sync` CLI command (incremental by default)
- [x] `status` CLI command showing last sync time per source
- [x] `--incremental` flag on `ingest` and `ingest-jira`
- [ ] ACL extraction + permission filtering (per-user access control)
- [ ] Scheduled auto-sync (cron)

---

## Phase 5 — Quality improvements ✅

- [x] `src/rewriter.py` — LLM query rewriting before embedding
- [x] Curated flag on chunks — score boost for high-signal pages
- [x] `query_log` table — every query logged with latency + rewritten form
- [x] `curate` / `uncurate` CLI commands
- [x] `logs` CLI command showing recent queries
- [x] `--show-rewritten` flag on `query` command
- [ ] Populate `eval/questions.yaml` and run eval harness
- [ ] Prompt tuning (chain-of-thought vs direct)

---

## Phase 6 — Web API ✅

- [x] Add `fastapi` + `uvicorn` to deps
- [x] `api.py` with `POST /query`, `POST /ingest/confluence`, `POST /ingest/jira`, `POST /ingest/gitlab`
- [x] `GET /status`, `GET /logs`, `GET /chunks/count`, `GET /health`
- [x] API key auth via `X-API-Key` header
- [x] Ingest runs in background (non-blocking)
- [x] Swagger UI at `http://localhost:8000/docs`
- [x] CLI still works alongside API

---

## Current CLI reference

```bash
# Ingest
uv run python cli.py ingest --space IIC
uv run python cli.py ingest-jira --project IIC
uv run python cli.py sync --space IIC --project IIC   # incremental

# Query
uv run python cli.py query "How does auth work?"
uv run python cli.py query "..." --show-rewritten

# Admin
uv run python cli.py status                            # sync history
uv run python cli.py logs                              # recent queries
uv run python cli.py curate <url>                      # boost a page
uv run python cli.py uncurate <url>                    # remove boost
```

---

## Available spaces & projects

| Key | Name | Type |
|---|---|---|
| IIC | IIC Portal | Confluence + Jira ✅ |
| DEV | DevOps | Confluence |
| ROAV2 | Doc - internal team | Confluence |
| FS | Finance squad | Confluence + Jira |
| IP | Investment Platform | Confluence |
| FUN | fundii | Jira |
| FC | fundii Working | Jira |
