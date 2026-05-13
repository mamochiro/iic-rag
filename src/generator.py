from openai import OpenAI
from .config import settings
from .models import Retrieved

_client = OpenAI(
    api_key=settings.nvidia_api_key,
    base_url="https://integrate.api.nvidia.com/v1",
)

SYSTEM_PROMPT = """You are an internal knowledge assistant for the company. Answer the user's question using ONLY the provided context snippets.

Rules:
- Cite every factual claim with [N] markers matching the numbered snippets.
- If the context does not contain enough information to answer, say so explicitly. Do not guess.
- Do not invent citations. Do not cite [N] for a number not in the context.
- Prefer concise answers (2-4 paragraphs). Quote sparingly; paraphrase instead.
- After the answer, output a "Sources:" section listing each cited [N] with its URL on its own line."""


def _format_context(retrieved: list[Retrieved]) -> str:
    blocks = []
    for i, r in enumerate(retrieved, start=1):
        blocks.append(
            f"[{i}] {r.title}\n"
            f"URL: {r.source_url}\n"
            f"---\n"
            f"{r.content}\n"
        )
    return "\n\n".join(blocks)


def generate_answer(question: str, retrieved: list[Retrieved]) -> str:
    context = _format_context(retrieved)
    user_message = f"""Context:

{context}

Question: {question}

Answer the question using only the context above. Cite with [N] markers and list sources at the end."""

    resp = _client.chat.completions.create(
        model=settings.nvidia_chat_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1024,
    )
    return resp.choices[0].message.content
