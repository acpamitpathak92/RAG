import json
import re
from functools import lru_cache

from backend.shared.config.settings import get_retrieval_config
from backend.shared.llm.factory import get_llm
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)

_CHUNK_PREVIEW_CHARS = 500  # only need enough text for a relevance judgment, not the full chunk

_SYSTEM_PROMPT = """You are a search relevance judge. You will be given a question and a numbered \
list of candidate text passages. Score how relevant each passage is to answering the question, on \
a scale from -10 (completely irrelevant) to +10 (directly and fully answers the question), with 0 \
meaning only tangentially related.

Respond with ONLY a JSON array, one object per passage, in this exact form:
[{"index": 1, "score": 7}, {"index": 2, "score": -3}, ...]

Include every passage index exactly once. No commentary, no markdown formatting, just the JSON array."""


class Reranker:
    """Scores every candidate chunk's relevance to the query in one batched LLM call,
    via get_llm(role="reranker") - the only supported reranking backend, no Hugging
    Face or local model dependency at all.
    """

    llm_role = "reranker"

    def __init__(self):
        self.llm = get_llm(self.llm_role)

    def rerank(self, query: str, chunks: list[dict], top_k: int | None = None) -> list[dict]:
        if not chunks:
            return []
        top_k = top_k or get_retrieval_config()["top_k_final"]

        passages = "\n\n".join(
            f"[{i + 1}] {c['text'][:_CHUNK_PREVIEW_CHARS]}" for i, c in enumerate(chunks)
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nPassages:\n{passages}"},
        ]

        scores_by_index = self._parse_scores(self.llm.generate(messages), len(chunks))

        scored = [{**c, "rerank_score": scores_by_index.get(i + 1, -10.0)} for i, c in enumerate(chunks)]
        scored.sort(key=lambda c: c["rerank_score"], reverse=True)
        return scored[:top_k]

    def _parse_scores(self, raw_response: str, expected_count: int) -> dict[int, float]:
        """Extracts {index: score} from the model's JSON response. Falls back to an empty
        mapping (every chunk defaults to the lowest score, preserving original order via
        Python's stable sort) rather than raising, so a malformed LLM response degrades
        the ranking quality instead of crashing the whole query.
        """
        match = re.search(r"\[.*\]", raw_response, re.DOTALL)
        if not match:
            logger.warning(f"Reranker: no JSON array found in response, keeping original order: {raw_response!r}")
            return {}

        try:
            entries = json.loads(match.group(0))
            scores = {int(entry["index"]): float(entry["score"]) for entry in entries}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Reranker: failed to parse scores ({e}), keeping original order: {raw_response!r}")
            return {}

        if len(scores) < expected_count:
            logger.warning(f"Reranker: scored {len(scores)}/{expected_count} passages - missing ones default to lowest score")
        return scores


@lru_cache
def get_reranker() -> Reranker:
    return Reranker()
