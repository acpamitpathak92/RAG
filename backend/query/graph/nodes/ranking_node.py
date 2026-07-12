from backend.query.graph.schemas import RetrievedChunk
from backend.query.graph.state import RAGState, effective_query
from backend.query.ranking.reranker import get_reranker
from backend.query.ranking.scoring import aggregate_retrieval_confidence, normalize_rerank_scores
from backend.shared.logging_utils import get_logger, log_stage

logger = get_logger(__name__)


def ranking_node(state: RAGState) -> dict:
    """Deterministic node: RRF-fused candidates -> cross-encoder rerank -> final top-k
    with normalized scores and an aggregate pre-generation retrieval confidence.
    """
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        logger.info("ranking_node: no retrieved chunks to rank, retrieval_confidence=0.0")
        return {"retrieved_chunks": [], "retrieval_confidence": 0.0}

    with log_stage(logger, "ranking_node", candidates=len(chunks)):
        chunk_dicts = [c.model_dump() for c in chunks]
        reranked = get_reranker().rerank(effective_query(state), chunk_dicts)
        reranked = normalize_rerank_scores(reranked)

        final_chunks = [
            RetrievedChunk(
                id=c["id"], doc_id=c["doc_id"], doc_title=c.get("doc_title", ""), parent_id=c.get("parent_id"),
                text=c["text"], parent_text=c.get("parent_text"), heading=c.get("heading", ""),
                source=c.get("source", ""), tags=c.get("tags", ""), rrf_score=c.get("rrf_score", 0.0),
                rerank_score=c.get("rerank_score", 0.0), normalized_rerank_score=c.get("normalized_rerank_score", 0.0),
            )
            for c in reranked
        ]
        confidence = aggregate_retrieval_confidence(reranked)
        logger.info(f"ranking_node: {len(chunks)} candidates -> top {len(final_chunks)}, retrieval_confidence={confidence:.3f}")

    return {"retrieved_chunks": final_chunks, "retrieval_confidence": confidence}
