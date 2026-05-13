from openai import OpenAI
from .config import settings
from .models import Chunk, EmbeddedChunk

_client = OpenAI(
    api_key=settings.nvidia_api_key,
    base_url="https://integrate.api.nvidia.com/v1",
)

BATCH = 50


def embed_chunks(chunks: list[Chunk], input_type: str = "document") -> list[EmbeddedChunk]:
    # NVIDIA uses "passage" for documents, "query" for queries
    nvidia_input_type = "passage" if input_type == "document" else "query"
    out: list[EmbeddedChunk] = []
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        resp = _client.embeddings.create(
            model=settings.nvidia_embedding_model,
            input=[c.content for c in batch],
            encoding_format="float",
            extra_body={"input_type": nvidia_input_type, "truncate": "END"},
        )
        vecs = [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
        for c, vec in zip(batch, vecs):
            out.append(EmbeddedChunk(**c.model_dump(), embedding=vec))
    return out


def embed_query(text: str) -> list[float]:
    resp = _client.embeddings.create(
        model=settings.nvidia_embedding_model,
        input=[text],
        encoding_format="float",
        extra_body={"input_type": "query", "truncate": "END"},
    )
    return resp.data[0].embedding
