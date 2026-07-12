from backend.query.graph.state import RAGState
from backend.shared.constants import GENERIC_INSUFFICIENT_EVIDENCE_MESSAGE
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def insufficient_evidence_node(state: RAGState) -> dict:
    """Deterministic node: when retrieval turned up nothing usable (see
    grounding.confidence_composer.has_sufficient_evidence), skip the LLM generation call
    entirely and return a clean, honest, generic message instead of letting the model
    stretch irrelevant chunks into a rambling forced answer.
    """
    logger.info("insufficient_evidence_node: skipping LLM generation, returning generic fallback message")
    return {
        "generation": GENERIC_INSUFFICIENT_EVIDENCE_MESSAGE,
        "citations": [],
        "confidence_score": state.get("retrieval_confidence", 0.0),
        "needs_caveat": True,
    }
