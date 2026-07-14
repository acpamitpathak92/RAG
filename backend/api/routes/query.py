from fastapi import APIRouter

from backend.api.schemas import QueryRequest, QueryResponse
from backend.shared.config.settings import get_settings
from backend.query.graph.build import run_query
from backend.shared.logging_utils import log_stage, get_logger
from backend.shared.storage.vector_store import init_default_db

router = APIRouter()
logger = get_logger(__name__)


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    logger.info(f"POST /query received: {request.query!r}")
    conn = init_default_db(get_settings().rag_db_path)
    try:
        with log_stage(logger, "full query pipeline", query=request.query):
            result = run_query(conn, request.query)
    finally:
        conn.close()

    query_was_corrected = result.get("query_was_corrected", False)
    response = QueryResponse(
        answer=result.get("final_response", ""),
        citations=[c.model_dump() for c in result.get("citations", [])],
        confidence_score=result.get("confidence_score", 0.0),
        needs_caveat=result.get("needs_caveat", False),
        original_query=result.get("original_query", request.query),
        corrected_query=result.get("cleaned_query") if query_was_corrected else None,
        query_was_corrected=query_was_corrected,
    )
    logger.info(
        f"POST /query response: confidence={response.confidence_score:.3f} "
        f"needs_caveat={response.needs_caveat} citations={len(response.citations)} "
        f"query_was_corrected={query_was_corrected}"
    )
    return response
