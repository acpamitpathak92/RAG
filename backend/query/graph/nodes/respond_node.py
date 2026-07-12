from backend.query.graph.state import RAGState
from backend.shared.constants import LOW_CONFIDENCE_PREFIX
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def respond_node(state: RAGState) -> dict:
    """Deterministic node: assembles the final user-facing response, prepending a caveat
    when confidence is low, so low-confidence answers are never returned as if certain.
    """
    generation = state.get("generation", "")
    if state.get("needs_caveat") and not generation.startswith(LOW_CONFIDENCE_PREFIX):
        generation = LOW_CONFIDENCE_PREFIX + generation
    logger.debug(f"respond_node: final response is {len(generation)} chars")
    return {"final_response": generation}
