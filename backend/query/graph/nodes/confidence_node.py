from backend.query.graph.state import RAGState
from backend.query.grounding.confidence_composer import compose_confidence, is_low_confidence
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def confidence_node(state: RAGState) -> dict:
    """Deterministic node: blends retrieval confidence + hallucination pass-rate (Phase 3+)
    into the final confidence score, and flags whether a low-confidence caveat is needed.
    """
    hallucination_check = state.get("hallucination_check")
    pass_rate = hallucination_check.pass_rate if hallucination_check else None

    score = compose_confidence(
        retrieval_confidence=state.get("retrieval_confidence", 0.0),
        hallucination_pass_rate=pass_rate,
        needs_caveat=state.get("needs_caveat", False),
    )
    needs_caveat = state.get("needs_caveat", False) or is_low_confidence(score)
    logger.info(f"confidence_node: confidence_score={score:.3f} needs_caveat={needs_caveat}")
    return {"confidence_score": score, "needs_caveat": needs_caveat}
