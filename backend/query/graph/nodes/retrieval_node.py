import sqlite3

from backend.query.graph.schemas import RetrievedChunk
from backend.query.graph.state import RAGState, effective_query
from backend.query.retrieval.hybrid_search import hybrid_search
from backend.query.retrieval.parent_retriever import expand_to_parents
from backend.shared.logging_utils import get_logger, log_stage
from backend.shared.storage.vector_store import get_document_titles

logger = get_logger(__name__)


def make_retrieval_node(conn: sqlite3.Connection):
    """Deterministic node: runs hybrid search for the (possibly rewritten) query, expands
    child hits to their parent section text, and attaches each hit's document title (so
    downstream citations show a real document name rather than a raw doc_id). No LLM call.
    """

    def retrieval_node(state: RAGState) -> dict:
        queries = state.get("rewritten_queries") or [effective_query(state)]
        with log_stage(logger, "retrieval_node", queries=len(queries)):
            seen_ids: set[str] = set()
            merged: list[dict] = []
            for query in queries:
                hits = hybrid_search(conn, query)
                logger.debug(f"hybrid_search({query!r}) -> {len(hits)} hits")
                for hit in hits:
                    if hit["id"] not in seen_ids:
                        seen_ids.add(hit["id"])
                        merged.append(hit)

            expanded = expand_to_parents(conn, merged)
            titles = get_document_titles(conn, list({c["doc_id"] for c in expanded}))
            retrieved_chunks = [
                RetrievedChunk(
                    id=c["id"], doc_id=c["doc_id"], doc_title=titles.get(c["doc_id"], c["doc_id"]),
                    parent_id=c.get("parent_id"), text=c["text"],
                    parent_text=c.get("parent_text"), heading=c.get("heading", ""), source=c.get("source", ""),
                    tags=c.get("tags", ""), rrf_score=c.get("rrf_score", 0.0),
                )
                for c in expanded
            ]
            logger.debug(f"retrieval_node merged {len(merged)} unique chunks across {len(queries)} quer{'y' if len(queries) == 1 else 'ies'}")
        return {"retrieved_chunks": retrieved_chunks, "retrieval_sources_used": list({c.source for c in retrieved_chunks})}

    return retrieval_node
