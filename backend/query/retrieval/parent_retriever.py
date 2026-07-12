import sqlite3

from backend.shared.storage.vector_store import get_parent_text


def expand_to_parents(conn: sqlite3.Connection, child_hits: list[dict]) -> list[dict]:
    """For each child-chunk hit, attaches its parent section's full text (for generation context)
    while keeping the child text/score for citation precision.
    """
    expanded = []
    for hit in child_hits:
        parent_text = get_parent_text(conn, hit["parent_id"]) if hit.get("parent_id") else None
        expanded.append({**hit, "parent_text": parent_text})
    return expanded
