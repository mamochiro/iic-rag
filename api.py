from typing import Annotated
import uuid

from fastapi import FastAPI, HTTPException, Security, BackgroundTasks
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src.config import settings
from src.query import answer_question
from src.ingest import ingest_space, ingest_jira_project, ingest_gitlab

_jobs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _require_key(key: Annotated[str | None, Security(_api_key_header)]):
    if not settings.api_key or key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="RAG API", version="1.0.0", docs_url="/docs")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None

class QueryResponse(BaseModel):
    answer: str
    rewritten: list[str] | str
    retrieved: list[dict]

class IngestConfluenceRequest(BaseModel):
    space: str
    limit: int | None = None
    incremental: bool = False

class IngestJiraRequest(BaseModel):
    project: str
    limit: int | None = None
    incremental: bool = False

class IngestGitLabRequest(BaseModel):
    project_id: str
    limit: int | None = None
    incremental: bool = False

class IngestResponse(BaseModel):
    status: str
    job_id: str
    pages: int
    chunks: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, _: str = Security(_require_key)):
    result = answer_question(req.question, top_k=req.top_k)
    return QueryResponse(
        answer=result["answer"],
        rewritten=result.get("rewritten", req.question),
        retrieved=result["retrieved"],
    )


def _make_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "pages": 0, "chunks": 0, "error": None}
    return job_id


def _finish_job(job_id: str, result: dict) -> None:
    _jobs[job_id] = {"status": "done", **result, "error": None}


def _fail_job(job_id: str, exc: Exception) -> None:
    _jobs[job_id] = {"status": "error", "pages": 0, "chunks": 0, "error": str(exc)}


@app.post("/ingest/confluence", response_model=IngestResponse)
def ingest_confluence(req: IngestConfluenceRequest, background: BackgroundTasks,
                      _: str = Security(_require_key)):
    job_id = _make_job()
    def run():
        try:
            result = ingest_space(req.space, limit=req.limit, incremental=req.incremental)
            _finish_job(job_id, result)
        except Exception as e:
            _fail_job(job_id, e)
    background.add_task(run)
    return IngestResponse(status="started", job_id=job_id, pages=0, chunks=0)


@app.post("/ingest/jira", response_model=IngestResponse)
def ingest_jira(req: IngestJiraRequest, background: BackgroundTasks,
                _: str = Security(_require_key)):
    job_id = _make_job()
    def run():
        try:
            result = ingest_jira_project(req.project, limit=req.limit, incremental=req.incremental)
            _finish_job(job_id, result)
        except Exception as e:
            _fail_job(job_id, e)
    background.add_task(run)
    return IngestResponse(status="started", job_id=job_id, pages=0, chunks=0)


@app.post("/ingest/gitlab", response_model=IngestResponse)
def ingest_gl(req: IngestGitLabRequest, background: BackgroundTasks,
              _: str = Security(_require_key)):
    job_id = _make_job()
    def run():
        try:
            result = ingest_gitlab(req.project_id, limit=req.limit, incremental=req.incremental)
            _finish_job(job_id, result)
        except Exception as e:
            _fail_job(job_id, e)
    background.add_task(run)
    return IngestResponse(status="started", job_id=job_id, pages=0, chunks=0)


@app.get("/jobs/{job_id}")
def job_status(job_id: str, _: str = Security(_require_key)):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@app.get("/status")
def status(_: str = Security(_require_key)):
    import psycopg
    with psycopg.connect(settings.database_url) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT source_type, source_key, last_synced_at, pages_fetched, chunks_upserted
            FROM sync_log ORDER BY last_synced_at DESC;
        """)
        rows = cur.fetchall()
    return [
        {"source": r[0], "key": r[1], "last_synced_at": r[2].isoformat(),
         "pages": r[3], "chunks": r[4]}
        for r in rows
    ]


@app.get("/logs")
def logs(limit: int = 20, _: str = Security(_require_key)):
    import psycopg
    with psycopg.connect(settings.database_url) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT created_at, latency_ms, question, rewritten_question, retrieved_urls
            FROM query_log ORDER BY created_at DESC LIMIT %s;
        """, (limit,))
        rows = cur.fetchall()
    return [
        {"created_at": r[0].isoformat(), "latency_ms": r[1],
         "question": r[2], "rewritten": r[3], "retrieved_urls": r[4]}
        for r in rows
    ]


@app.get("/chunks/count")
def chunks_count(_: str = Security(_require_key)):
    import psycopg
    with psycopg.connect(settings.database_url) as conn:
        cur = conn.cursor()
        cur.execute("SELECT source_type, COUNT(*) FROM chunks GROUP BY source_type ORDER BY source_type;")
        rows = cur.fetchall()
    return {r[0]: r[1] for r in rows}
