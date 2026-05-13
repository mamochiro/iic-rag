import base64
import gitlab
from datetime import datetime
from .config import settings
from .models import Page

_client = gitlab.Gitlab(settings.gitlab_url, private_token=settings.gitlab_token)


def _make_page(source_id: str, url: str, title: str, space_key: str, content: str) -> Page:
    return Page(
        source_id=source_id,
        source_url=url,
        title=title,
        space_key=space_key,
        content=content,
    )


def _fetch_wiki_pages(project, base_url: str) -> list[Page]:
    pages = []
    try:
        for wiki in project.wikis.list(get_all=True):
            full = project.wikis.get(wiki.slug)
            pages.append(_make_page(
                source_id=f"{project.id}:wiki:{wiki.slug}",
                url=f"{base_url}/{project.path_with_namespace}/-/wikis/{wiki.slug}",
                title=f"{project.name} — {wiki.title}",
                space_key=str(project.id),
                content=getattr(full, "content", "") or "",
            ))
    except Exception:
        pass
    return pages


def _fetch_md_files(project, base_url: str, ref: str = "main") -> list[Page]:
    pages = []
    try:
        items = project.repository_tree(recursive=True, ref=ref, get_all=True)
    except Exception:
        try:
            items = project.repository_tree(recursive=True, ref="master", get_all=True)
            ref = "master"
        except Exception:
            return pages

    for item in items:
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if not path.lower().endswith(".md"):
            continue
        try:
            f = project.files.get(file_path=path, ref=ref)
            content = base64.b64decode(f.content).decode("utf-8", errors="ignore")
            pages.append(_make_page(
                source_id=f"{project.id}:file:{path}",
                url=f"{base_url}/{project.path_with_namespace}/-/blob/{ref}/{path}",
                title=f"{project.name} — {path}",
                space_key=str(project.id),
                content=content,
            ))
        except Exception:
            continue
    return pages


def fetch_project(project_id: str | int, since: datetime | None = None) -> list[Page]:
    """Fetch wiki pages and .md files from a GitLab project."""
    base_url = settings.gitlab_url.rstrip("/")
    project = _client.projects.get(project_id)
    pages: list[Page] = []
    pages.extend(_fetch_wiki_pages(project, base_url))
    pages.extend(_fetch_md_files(project, base_url))
    return pages


def list_projects(search: str | None = None) -> list[dict]:
    """List accessible projects. Optionally filter by name."""
    kwargs = {"membership": True, "order_by": "last_activity_at", "get_all": False}
    if search:
        kwargs["search"] = search
    projects = _client.projects.list(**kwargs)
    return [{"id": p.id, "name": p.name, "path": p.path_with_namespace} for p in projects]
