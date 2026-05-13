from atlassian import Jira
from datetime import datetime
from .config import settings
from .models import Page

_client = Jira(
    url=settings.confluence_url,
    username=settings.confluence_username,
    password=settings.confluence_api_token,
    cloud=True,
)

_BASE_URL = settings.confluence_url.rstrip("/")


def _issue_to_text(issue: dict) -> str:
    fields = issue.get("fields", {})
    parts = []
    if fields.get("summary"):
        parts.append(fields["summary"])
    if fields.get("description"):
        desc = fields["description"]
        if isinstance(desc, str):
            parts.append(desc)
        elif isinstance(desc, dict):
            parts.append(_extract_adf_text(desc))
    if fields.get("comment", {}).get("comments"):
        for c in fields["comment"]["comments"]:
            body = c.get("body", "")
            if isinstance(body, str):
                parts.append(body)
            elif isinstance(body, dict):
                parts.append(_extract_adf_text(body))
    return "\n\n".join(filter(None, parts))


def _extract_adf_text(node: dict) -> str:
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_extract_adf_text(child) for child in node.get("content", [])]
    return " ".join(filter(None, parts))


def fetch_issues(project_key: str, limit: int | None = None,
                 since: datetime | None = None) -> list[Page]:
    pages: list[Page] = []
    next_page_token: str | None = None
    batch_size = 50

    jql = f"project = {project_key} AND status in ('In Progress', 'Done')"
    if since:
        since_str = since.strftime("%Y-%m-%d %H:%M")
        jql += f" AND updated >= '{since_str}'"
    jql += " ORDER BY updated DESC"

    while True:
        result = _client.enhanced_jql(
            jql,
            fields="summary,description,comment,status,issuetype",
            limit=batch_size,
            nextPageToken=next_page_token,
        )
        issues = result.get("issues", [])
        if not issues:
            break
        for issue in issues:
            key = issue["key"]
            fields = issue.get("fields", {})
            pages.append(Page(
                source_id=key,
                source_url=f"{_BASE_URL}/browse/{key}",
                title=f"[{key}] {fields.get('summary', '')}",
                space_key=project_key,
                content=_issue_to_text(issue),
            ))
            if limit and len(pages) >= limit:
                return pages
        next_page_token = result.get("nextPageToken")
        if not next_page_token or len(issues) < batch_size:
            break
    return pages
