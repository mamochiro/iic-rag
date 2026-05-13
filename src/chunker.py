import tiktoken
from .config import settings
from .models import Page, Chunk

# cl100k is a reasonable token approximation for non-OpenAI models
_enc = tiktoken.get_encoding("cl100k_base")


def chunk_page(page: Page) -> list[Chunk]:
    text = page.content.strip()
    if not text:
        return []
    tokens = _enc.encode(text)
    size = settings.chunk_token_size
    overlap = settings.chunk_overlap
    if size <= overlap:
        raise ValueError("chunk_token_size must be greater than chunk_overlap")
    chunks: list[Chunk] = []
    step = size - overlap
    for i, start in enumerate(range(0, len(tokens), step)):
        window = tokens[start:start + size]
        if not window:
            break
        content = _enc.decode(window)
        prefix = f"{page.title}\n\n"
        content_with_title = prefix + content
        chunks.append(Chunk(
            source_id=page.source_id,
            source_url=page.source_url,
            title=page.title,
            space_key=page.space_key,
            chunk_index=i,
            content=content_with_title,
            token_count=len(window) + len(_enc.encode(prefix)),
        ))
        if start + size >= len(tokens):
            break
    return chunks
