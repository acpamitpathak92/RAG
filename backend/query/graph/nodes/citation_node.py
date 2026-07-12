from backend.query.graph.state import RAGState
from backend.query.grounding.citation_extractor import extract_citations
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def citation_node(state: RAGState) -> dict:
    """Deterministic node: parses [n] markers out of the generation and maps them back
    to real chunk/doc ids. Runs right after generation, before any hallucination check.
    """
    evidence = state.get("_evidence_used")
    if not evidence:
        evidence = [c.model_dump() for c in state.get("retrieved_chunks", [])]
    citations = extract_citations(state.get("generation", ""), evidence)
    logger.info(f"citation_node: extracted {len(citations)} citation(s) from generation")
    return {"citations": citations}
