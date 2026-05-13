import time
from .config import settings
from .embedder import embed_query
from .rewriter import generate_queries
from .store import hybrid_search, log_query
from .reranker import rerank
from .generator import generate_answer
from .models import Retrieved


def _dedupe(results: list[Retrieved]) -> list[Retrieved]:
    seen, out = set(), []
    for r in results:
        if r.chunk_id not in seen:
            seen.add(r.chunk_id)
            out.append(r)
    return out


def answer_question(question: str, top_k: int | None = None) -> dict:
    start = time.monotonic()
    k = top_k or settings.top_k

    # 1. Generate multiple query phrasings
    queries = generate_queries(question)

    # 2. Hybrid search for each query, collect all candidates (cap at 12 for reranker)
    candidates: list[Retrieved] = []
    for q in queries:
        q_emb = embed_query(q)
        results = hybrid_search(q_emb, q, top_k=k * 2)
        candidates.extend(results)

    candidates = _dedupe(candidates)[:12]

    if not candidates:
        return {"answer": "I have no indexed content yet.", "retrieved": [], "rewritten": queries[0]}

    # 3. Rerank all candidates down to top-k using cross-encoder
    reranked = rerank(question, candidates, top_k=k)

    # 4. Generate cited answer
    answer = generate_answer(question, reranked)
    latency_ms = int((time.monotonic() - start) * 1000)

    log_query(
        question=question,
        rewritten=" | ".join(queries[1:]) if len(queries) > 1 else queries[0],
        retrieved_urls=[r.source_url for r in reranked],
        answer=answer,
        latency_ms=latency_ms,
    )

    return {
        "answer": answer,
        "rewritten": queries,
        "retrieved": [{"title": r.title, "url": r.source_url, "score": round(r.score, 4)}
                      for r in reranked],
    }
