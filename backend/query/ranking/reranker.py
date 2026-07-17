import json
import re
from functools import lru_cache

from backend.shared.config.settings import get_retrieval_config
from backend.shared.llm.factory import get_llm
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)

_CHUNK_PREVIEW_CHARS = 500  # only need enough text for a relevance judgment, not the full chunk
_NEUTRAL_SCORE = 0.0  # fallback when parsing fails - see _parse_scores docstring for why this isn't -10

_SYSTEM_PROMPT = """You are a search relevance judge. You will be given a question and a numbered \
list of candidate text passages. Score how relevant each passage is to answering the question, on \
a scale from -10 (completely irrelevant) to +10 (directly and fully answers the question), with 0 \
meaning only tangentially related.

Respond with ONLY a JSON array, one object per passage, in this exact form:
[{"index": 1, "score": 7}, {"index": 2, "score": -3}, ...]

Include every passage index exactly once. Do not include any reasoning, explanation, thinking, or
markdown formatting before or after the array - the response body must be the JSON array and
nothing else."""

# Some models (especially reasoning models) wrap output in <think>...</think> blocks or fence it
# in markdown code blocks despite instructions not to - strip those before looking for JSON.
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


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

        raw_response = self.llm.generate(messages)
        logger.debug(f"Reranker raw response ({len(raw_response)} chars): {raw_response[:300]!r}")
        scores_by_index = self._parse_scores(raw_response, len(chunks))

        scored = [{**c, "rerank_score": scores_by_index.get(i + 1, _NEUTRAL_SCORE)} for i, c in enumerate(chunks)]
        scored.sort(key=lambda c: c["rerank_score"], reverse=True)
        return scored[:top_k]

    def _parse_scores(self, raw_response: str, expected_count: int) -> dict[int, float]:
        """Extracts {index: score} from the model's JSON response, tolerating common
        reasoning-model quirks (a <think> block before the answer, or the JSON wrapped in a
        markdown code fence) before falling back to a plain regex search for the array.

        Falls back to an empty mapping (every chunk defaults to _NEUTRAL_SCORE = 0, NOT the
        minimum score) rather than raising. Defaulting to neutral - not the lowest possible
        score - matters: if reranking silently fails on every request, defaulting everything
        to the lowest score would make every single query look like "insufficient evidence"
        even though hybrid retrieval underneath is working fine. A parse failure should
        degrade reranking quality, not take down the whole answer.
        """
        cleaned = _THINK_BLOCK_RE.sub("", raw_response).strip()

        fence_match = _CODE_FENCE_RE.search(cleaned)
        candidate = fence_match.group(1) if fence_match else cleaned

        match = _JSON_ARRAY_RE.search(candidate)
        if not match:
            logger.warning(f"Reranker: no JSON array found in response, using neutral scores: {raw_response!r}")
            return {}

        try:
            entries = json.loads(match.group(0))
            scores = {int(entry["index"]): float(entry["score"]) for entry in entries}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Reranker: failed to parse scores ({e}), using neutral scores: {raw_response!r}")
            return {}

        if len(scores) < expected_count:
            logger.warning(f"Reranker: scored {len(scores)}/{expected_count} passages - missing ones default to neutral score")
        return scores


@lru_cache
def get_reranker() -> Reranker:
    return Reranker()
