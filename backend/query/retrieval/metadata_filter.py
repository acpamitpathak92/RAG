def build_where_clause(filters: dict | None) -> tuple[str, tuple]:
    """Turns a simple filter dict (e.g. {"source": "markdown", "tags": "networking"})
    into a SQL WHERE fragment + params, used by vector_store.dense_search's extra_filter.
    Unknown/empty filters are ignored rather than erroring, since CRAG's "broadened search"
    fallback works by progressively dropping filter keys.
    """
    if not filters:
        return "", ()

    clauses = []
    params: list = []
    if source := filters.get("source"):
        clauses.append("c.source = ?")
        params.append(source)
    if tag := filters.get("tags"):
        clauses.append("c.tags LIKE ?")
        params.append(f"%{tag}%")
    if doc_id := filters.get("doc_id"):
        clauses.append("c.doc_id = ?")
        params.append(doc_id)

    if not clauses:
        return "", ()
    return " AND ".join(clauses), tuple(params)
