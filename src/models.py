from pydantic import BaseModel


class Page(BaseModel):
    source_id: str          # confluence page id as string
    source_url: str
    title: str
    space_key: str | None
    content: str            # plain text, HTML stripped


class Chunk(BaseModel):
    source_type: str = "confluence"
    source_id: str
    source_url: str
    title: str
    space_key: str | None
    chunk_index: int
    content: str
    token_count: int


class EmbeddedChunk(Chunk):
    embedding: list[float]


class Retrieved(BaseModel):
    chunk_id: int
    source_url: str
    title: str
    content: str
    score: float
