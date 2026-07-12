from typing import TypedDict

from backend.query.graph.schemas import Citation, GradedChunk, HallucinationReport, RetrievedChunk


class RAGState(TypedDict, total=False):
    # Query lifecycle
    original_query: str
    cleaned_query: str  # original_query with typos/grammar/whitespace fixed by QueryCleanupAgent
    query_was_corrected: bool  # True only if cleaned_query differs from original_query and passed the safety check
    conversation_history: list[dict]
    query_analysis: dict
    rewritten_queries: list[str]
    decomposed_subqueries: list[str]  # future - unused in Phase 1-3

    # Retrieval
    retrieved_chunks: list[RetrievedChunk]
    parent_chunks: list[RetrievedChunk]
    retrieval_sources_used: list[str]

    # Grading / CRAG (Phase 2+)
    graded_chunks: list[GradedChunk]
    overall_retrieval_grade: str
    retry_count: int
    max_retries: int
    refined_queries: list[str]
    fallback_source_used: str | None

    # Ranking
    rrf_scores: dict[str, float]
    rerank_scores: dict[str, float]
    similarity_scores: dict[str, float]
    retrieval_confidence: float

    # Generation & Grounding
    generation: str
    citations: list[Citation]
    hallucination_check: HallucinationReport
    confidence_score: float
    needs_caveat: bool

    # Control / meta
    final_response: str
    error: str | None


def effective_query(state: RAGState) -> str:
    """The query to use for retrieval/ranking/generation: the cleaned-up version if the
    QueryCleanupAgent has run, otherwise the raw original_query."""
    return state.get("cleaned_query") or state["original_query"]
