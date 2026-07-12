import sqlite3


def get_current_doc_state(conn: sqlite3.Connection, doc_id: str) -> tuple[str, int] | None:
    """Returns (content_hash, version) for a previously-ingested doc, or None if new."""
    row = conn.execute(
        "SELECT content_hash, version FROM documents WHERE doc_id = ?", (doc_id,)
    ).fetchone()
    return (row[0], row[1]) if row else None


def sweep_orphaned_chunks(conn: sqlite3.Connection, doc_id: str, current_version: int) -> None:
    """Removes chunk rows (and their vectors) left behind by a doc that shrank on re-ingestion."""
    stale_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM chunks WHERE doc_id = ? AND version < ?", (doc_id, current_version)
        ).fetchall()
    ]
    if not stale_ids:
        return
    placeholders = ",".join("?" for _ in stale_ids)
    conn.execute(f"DELETE FROM chunks WHERE id IN ({placeholders})", stale_ids)
    conn.execute(f"DELETE FROM chunk_vectors WHERE chunk_id IN ({placeholders})", stale_ids)
