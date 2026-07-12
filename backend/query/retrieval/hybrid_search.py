import sqlite3

from backend.shared.config.settings import get_retrieval_config
from backend.shared.embeddings.embedder import get_embedder
from backend.query.ranking.rrf import reciprocal_rank_fusion
from backend.query.retrieval.bm25_index import build_bm25_index
from backend.query.retrieval.metadata_filter import build_where_clause
from backend.shared.storage.vector_store import dense_search


def hybrid_search(conn: sqlite3.Connection, query: str, filters: dict | None = None, top_k: int | None = None) -> list[dict]:
    """Runs dense (sqlite-vec) + lexical (BM25) search and fuses results with RRF.

    Returns chunk dicts (deduped by id) ordered by fused score, each carrying
    `rrf_score`, plus a lookup back to the raw text/metadata needed downstream.
    """
    config = get_retrieval_config()
    top_k = top_k or config["top_k_fused"]
    where_sql, where_params = build_where_clause(filters)

    embedder = get_embedder()
    query_vector = embedder.embed_query(query)
    dense_hits = dense_search(conn, query_vector, top_k=config["top_k_dense"], where_sql=where_sql, where_params=where_params)
    dense_by_id = {hit["id"]: hit for hit in dense_hits}
    dense_ranked_ids = [hit["id"] for hit in dense_hits]

    bm25_index = build_bm25_index(conn)
    bm25_hits = bm25_index.search(query, top_k=config["top_k_bm25"])
    bm25_ranked_ids = [chunk_id for chunk_id, _ in bm25_hits]

    fused_scores = reciprocal_rank_fusion([dense_ranked_ids, bm25_ranked_ids], k=config["rrf_k"])
    ranked_ids = sorted(fused_scores.keys(), key=lambda cid: fused_scores[cid], reverse=True)[:top_k]

    # backfill any chunk metadata not already fetched via dense_search (i.e. BM25-only hits)
    missing_ids = [cid for cid in ranked_ids if cid not in dense_by_id]
    if missing_ids:
        placeholders = ",".join("?" for _ in missing_ids)
        rows = conn.execute(
            f"SELECT id, doc_id, parent_id, text, heading, source, tags FROM chunks WHERE id IN ({placeholders})",
            missing_ids,
        ).fetchall()
        for row in rows:
            dense_by_id[row["id"]] = dict(row)

    results = []
    for cid in ranked_ids:
        chunk = dense_by_id.get(cid)
        if chunk is None:
            continue
        results.append({**chunk, "rrf_score": fused_scores[cid]})
    return results
