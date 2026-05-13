from rich.console import Console
from .confluence import fetch_pages
from .jira import fetch_issues
from .gitlab_source import fetch_project
from .chunker import chunk_page
from .embedder import embed_chunks
from .store import upsert_chunks, get_last_synced, set_last_synced

console = Console()


def _run_pipeline(pages, source_label: str) -> dict:
    all_chunks = []
    for p in pages:
        chunks = chunk_page(p)
        for c in chunks:
            c.source_type = source_label
        all_chunks.extend(chunks)
    console.log(f"Produced {len(all_chunks)} chunks")

    if not all_chunks:
        return {"pages": len(pages), "chunks": 0}

    console.log("Embedding chunks...")
    embedded = embed_chunks(all_chunks, input_type="document")

    console.log("Writing to Postgres...")
    n = upsert_chunks(embedded)
    console.log(f"Upserted {n} chunks")
    return {"pages": len(pages), "chunks": n}


def ingest_space(space_key: str, limit: int | None = None, incremental: bool = False) -> dict:
    since = get_last_synced("confluence", space_key) if incremental else None
    if since:
        console.log(f"Incremental sync — fetching Confluence pages modified since {since:%Y-%m-%d %H:%M}")
    else:
        console.log(f"Full sync — fetching all Confluence pages from space {space_key}...")

    pages = fetch_pages(space_key, limit=limit, since=since)
    console.log(f"Fetched {len(pages)} pages")

    result = _run_pipeline(pages, "confluence")
    set_last_synced("confluence", space_key, result["pages"], result["chunks"])
    return result


def ingest_jira_project(project_key: str, limit: int | None = None, incremental: bool = False) -> dict:
    since = get_last_synced("jira", project_key) if incremental else None
    if since:
        console.log(f"Incremental sync — fetching Jira issues updated since {since:%Y-%m-%d %H:%M}")
    else:
        console.log(f"Full sync — fetching all Jira issues from project {project_key}...")

    pages = fetch_issues(project_key, limit=limit, since=since)
    console.log(f"Fetched {len(pages)} issues")

    result = _run_pipeline(pages, "jira")
    set_last_synced("jira", project_key, result["pages"], result["chunks"])
    return result


def ingest_gitlab(project_id: str, limit: int | None = None, incremental: bool = False) -> dict:
    since = get_last_synced("gitlab", project_id) if incremental else None
    if since:
        console.log(f"Incremental sync — fetching GitLab changes since {since:%Y-%m-%d %H:%M}")
    else:
        console.log(f"Full sync — fetching GitLab project {project_id}...")

    pages = fetch_project(project_id, since=since)
    if limit:
        pages = pages[:limit]
    console.log(f"Fetched {len(pages)} pages/files")

    result = _run_pipeline(pages, "gitlab")
    set_last_synced("gitlab", project_id, result["pages"], result["chunks"])
    return result
