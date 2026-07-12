import sqlite3

from langgraph.graph import END, StateGraph

from backend.query.agents.generation_agent import GenerationAgent
from backend.query.agents.query_cleanup_agent import QueryCleanupAgent
from backend.query.graph.nodes.citation_node import citation_node
from backend.query.graph.nodes.confidence_node import confidence_node
from backend.query.graph.nodes.insufficient_evidence_node import insufficient_evidence_node
from backend.query.graph.nodes.ranking_node import ranking_node
from backend.query.graph.nodes.respond_node import respond_node
from backend.query.graph.nodes.retrieval_node import make_retrieval_node
from backend.query.graph.state import RAGState
from backend.query.grounding.confidence_composer import has_sufficient_evidence
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def _route_after_ranking(state: RAGState) -> str:
    """Conditional edge: only spend an LLM generation call if retrieval actually found
    something worth answering from - otherwise route straight to the generic
    insufficient-evidence response (see grounding.confidence_composer.has_sufficient_evidence).
    """
    chunks = state.get("retrieved_chunks", [])
    confidence = state.get("retrieval_confidence", 0.0)
    if has_sufficient_evidence(confidence, len(chunks)):
        logger.debug(f"routing: rank -> generate (retrieval_confidence={confidence:.3f}, chunks={len(chunks)})")
        return "generate"
    logger.info(f"routing: rank -> insufficient (retrieval_confidence={confidence:.3f}, chunks={len(chunks)})")
    return "insufficient"


def build_graph(conn: sqlite3.Connection):
    """Phase 1 graph: clean_query -> retrieve -> rank -> [generate -> cite -> confidence | insufficient] -> respond.

    No CRAG grading loop or hallucination judge yet (Phase 2/3) - this is the
    straight-through path that already yields cited, confidence-scored answers.
    """
    query_cleanup_agent = QueryCleanupAgent()
    generation_agent = GenerationAgent()

    graph = StateGraph(RAGState)
    graph.add_node("clean_query", query_cleanup_agent.run)
    graph.add_node("retrieve", make_retrieval_node(conn))
    graph.add_node("rank", ranking_node)
    graph.add_node("generate", generation_agent.run)
    graph.add_node("cite", citation_node)
    graph.add_node("confidence", confidence_node)
    graph.add_node("insufficient", insufficient_evidence_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("clean_query")
    graph.add_edge("clean_query", "retrieve")
    graph.add_edge("retrieve", "rank")
    graph.add_conditional_edges("rank", _route_after_ranking, {"generate": "generate", "insufficient": "insufficient"})
    graph.add_edge("generate", "cite")
    graph.add_edge("cite", "confidence")
    graph.add_edge("confidence", "respond")
    graph.add_edge("insufficient", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


def run_query(conn: sqlite3.Connection, query: str) -> RAGState:
    app = build_graph(conn)
    return app.invoke({"original_query": query, "retry_count": 0, "needs_caveat": False})
