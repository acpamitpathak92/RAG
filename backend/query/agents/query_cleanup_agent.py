from difflib import SequenceMatcher

from backend.query.agents.base import Agent
from backend.query.graph.state import RAGState
from backend.shared.constants import QUERY_CORRECTION_MIN_SIMILARITY
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You clean up a user's question before it is used to search a knowledge base. \
Fix spelling mistakes and typos, correct grammar, and collapse extra/unnecessary whitespace into \
single spaces. Do not change what is being asked: do not add information, remove information, \
answer the question, or rephrase it for style beyond correcting these mechanical errors. \
If the question is already clean, return it unchanged. \
Respond with ONLY the corrected question - no quotes, no commentary, no explanation."""


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class QueryCleanupAgent(Agent):
    """Scope: fix typos/grammar/whitespace in the raw user question before anything else runs.

    Deliberately narrow - unlike a full query-rewrite/expansion agent (Phase 2+), this must
    never change what's being asked, only how cleanly it's expressed. Runs first in the graph,
    before retrieval, so a messy question doesn't degrade embedding/keyword search quality.

    Safety net: if the model's "corrected" version drifts too far from the original (see
    QUERY_CORRECTION_MIN_SIMILARITY), the correction is rejected and the original question is
    used instead - a mechanical typo/grammar fix should never plausibly change the question's
    substance, so a large drift is treated as a sign something went wrong, not a legitimate fix.
    """

    llm_role = "query_cleanup"

    def run(self, state: RAGState) -> dict:
        original = state["original_query"]
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": original},
        ]
        cleaned = self.llm.generate(messages).strip().strip('"').strip()

        if not cleaned:
            logger.info("QueryCleanupAgent: empty result, falling back to original query")
            return {"cleaned_query": original, "query_was_corrected": False}

        if cleaned == original:
            return {"cleaned_query": original, "query_was_corrected": False}

        similarity = _similarity(original, cleaned)
        if similarity < QUERY_CORRECTION_MIN_SIMILARITY:
            logger.warning(
                f"QueryCleanupAgent: rejected correction, similarity={similarity:.2f} below "
                f"threshold ({original!r} -> {cleaned!r}), using original question instead"
            )
            return {"cleaned_query": original, "query_was_corrected": False}

        logger.info(f"QueryCleanupAgent: {original!r} -> {cleaned!r} (similarity={similarity:.2f})")
        return {"cleaned_query": cleaned, "query_was_corrected": True}
