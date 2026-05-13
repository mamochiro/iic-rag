from atlassian import Confluence
from datetime import datetime
from html.parser import HTMLParser
from .config import settings
from .models import Page

_client = Confluence(
    url=settings.confluence_url,
    username=settings.confluence_username,
    password=settings.confluence_api_token,
    cloud=True,
)

_BASE_URL = settings.confluence_url.rstrip("/")


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


def _html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html or "")
    return p.text()


def _raw_to_page(raw: dict, space_key: str) -> Page:
    return Page(
        source_id=str(raw["id"]),
        source_url=f"{_BASE_URL}/wiki/spaces/{space_key}/pages/{raw['id']}",
        title=raw["title"],
        space_key=space_key,
        content=_html_to_text(raw.get("body", {}).get("storage", {}).get("value", "")),
    )


def fetch_pages(space_key: str, limit: int | None = None,
                since: datetime | None = None) -> list[Page]:
    pages: list[Page] = []

    if since:
        # CQL incremental fetch — only pages modified after `since`
        since_str = since.strftime("%Y-%m-%d %H:%M")
        cql = f"space = '{space_key}' AND lastModified > '{since_str}' ORDER BY lastModified DESC"
        start = 0
        page_size = 50
        while True:
            result = _client.cql(cql, start=start, limit=page_size,
                                 expand="body.storage,version")
            batch = result.get("results", [])
            if not batch:
                break
            for item in batch:
                raw = item.get("content", item)
                pages.append(_raw_to_page(raw, space_key))
                if limit and len(pages) >= limit:
                    return pages
            start += page_size
            if len(batch) < page_size:
                break
        return pages

    # Full fetch
    start = 0
    page_size = 50
    while True:
        batch = _client.get_all_pages_from_space(
            space=space_key,
            start=start,
            limit=page_size,
            expand="body.storage,version",
        )
        if not batch:
            break
        for raw in batch:
            pages.append(_raw_to_page(raw, space_key))
            if limit and len(pages) >= limit:
                return pages
        start += page_size
        if len(batch) < page_size:
            break
    return pages
