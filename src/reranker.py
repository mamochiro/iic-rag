import json
from openai import OpenAI
from .config import settings
from .models import Retrieved

_client = OpenAI(
    api_key=settings.nvidia_api_key,
    base_url="https://integrate.api.nvidia.com/v1",
)

_PROMPT = """You are a relevance ranker. Given a question and a list of numbered passages,
output a JSON array of passage indices ordered from MOST to LEAST relevant to the question.
Include ALL indices. Output ONLY the JSON array, nothing else. Example: [2, 0, 4, 1, 3]"""


def rerank(question: str, candidates: list[Retrieved], top_k: int) -> list[Retrieved]:
    if not candidates:
        return candidates

    # Compact passages — title only + 200 chars to keep prompt small
    passages = "\n".join(
        f"[{i}] {c.title}: {c.content[:200]}"
        for i, c in enumerate(candidates)
    )

    resp = _client.chat.completions.create(
        model=settings.nvidia_chat_model,
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": f"Question: {question}\n\nPassages:\n{passages}"},
        ],
        max_tokens=256,
        temperature=0.0,
    )

    raw = resp.choices[0].message.content.strip()

    try:
        # Extract JSON array from response (model may wrap it in markdown)
        start = raw.find("[")
        end = raw.rfind("]") + 1
        indices = json.loads(raw[start:end])
        # Validate indices and pick top_k
        valid = [i for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
        if valid:
            return [
                Retrieved(**{**candidates[i].model_dump(), "score": len(valid) - rank})
                for rank, i in enumerate(valid[:top_k])
            ]
    except Exception:
        pass

    # Fallback: return original order
    return candidates[:top_k]
