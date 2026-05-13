from openai import OpenAI
from .config import settings

_client = OpenAI(
    api_key=settings.nvidia_api_key,
    base_url="https://integrate.api.nvidia.com/v1",
)

_REWRITE_PROMPT = """You are a search query optimizer for an internal company knowledge base.
Rewrite the user's question to improve retrieval. Keep company-specific terms, product
names, and project codes exactly as given — do not expand them. Only clarify vague
pronouns, fix grammar, and add generic technical synonyms where helpful.
Output ONLY the rewritten query — no explanation, no quotes, no prefix."""

_MULTI_QUERY_PROMPT = """You are a search query generator for an internal company knowledge base.
Given a question, generate 2 alternative search queries that approach the same information need
from different angles. Keep company-specific terms, product names, and project codes unchanged.
Output ONLY the 2 queries, one per line, nothing else."""


def rewrite_query(question: str) -> str:
    resp = _client.chat.completions.create(
        model=settings.nvidia_chat_model,
        messages=[
            {"role": "system", "content": _REWRITE_PROMPT},
            {"role": "user", "content": question},
        ],
        max_tokens=128,
        temperature=0.1,
    )
    rewritten = resp.choices[0].message.content.strip()
    return rewritten if len(rewritten) > 5 else question


def generate_queries(question: str) -> list[str]:
    """Return the original question + 2 alternative phrasings."""
    resp = _client.chat.completions.create(
        model=settings.nvidia_chat_model,
        messages=[
            {"role": "system", "content": _MULTI_QUERY_PROMPT},
            {"role": "user", "content": question},
        ],
        max_tokens=200,
        temperature=0.4,
    )
    lines = [l.strip() for l in resp.choices[0].message.content.strip().splitlines()
             if l.strip() and len(l.strip()) > 5]
    # Always include original; deduplicate
    all_queries = [question] + lines[:2]
    seen, unique = set(), []
    for q in all_queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique
