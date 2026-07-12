import sqlite3
from pathlib import Path

import numpy as np
import sqlite_vec

from backend.shared.embeddings.embedder import get_embedder

# PRAGMA is a SQLite command used to configure database behavior.
# Here it changes the journal mode to WAL (Write-Ahead Logging).
# Readers can continue while a writer is active.

# Benefits:
# Better concurrency
# Faster reads
# Great for RAG systems where many queries happen while new documents may be indexed
def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def init_schema(conn: sqlite3.Connection, embedding_dim: int) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            title TEXT,
            source TEXT,
            file_path TEXT,
            updated_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            parent_id TEXT,
            chunk_type TEXT NOT NULL,       -- 'parent' | 'child'
            chunk_index INTEGER,
            version INTEGER NOT NULL DEFAULT 1,
            source TEXT,
            text TEXT NOT NULL,
            heading TEXT,
            tags TEXT,
            content_hash TEXT,
            created_at INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_parent_id ON chunks(parent_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);
        """
    )
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0(
            chunk_id TEXT PRIMARY KEY,
            embedding FLOAT[{embedding_dim}]
        )
        """
    )
    _migrate_documents_table(conn)
    conn.commit()


def _migrate_documents_table(conn: sqlite3.Connection) -> None:
    """Adds columns introduced after the initial schema to any pre-existing local DB file."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    for column, ddl_type in (("title", "TEXT"), ("source", "TEXT"), ("file_path", "TEXT"), ("updated_at", "INTEGER")):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {column} {ddl_type}")


def upsert_chunk(conn: sqlite3.Connection, chunk_row: dict, embedding: np.ndarray | None) -> None:
    conn.execute(
        """
        INSERT INTO chunks (id, doc_id, parent_id, chunk_type, chunk_index, version, source, text, heading, tags, content_hash, created_at)
        VALUES (:id, :doc_id, :parent_id, :chunk_type, :chunk_index, :version, :source, :text, :heading, :tags, :content_hash, :created_at)
        ON CONFLICT(id) DO UPDATE SET
            text = excluded.text, version = excluded.version, content_hash = excluded.content_hash,
            heading = excluded.heading, tags = excluded.tags, created_at = excluded.created_at
        """,
        chunk_row,
    )
    if embedding is not None:
        conn.execute("DELETE FROM chunk_vectors WHERE chunk_id = ?", (chunk_row["id"],))
        conn.execute(
            "INSERT INTO chunk_vectors (chunk_id, embedding) VALUES (?, ?)",
            (chunk_row["id"], np.asarray(embedding, dtype=np.float32).tobytes()),
        )


def dense_search(conn: sqlite3.Connection, query_vector: np.ndarray, top_k: int, where_sql: str = "", where_params: tuple = ()) -> list[dict]:
    """KNN search over child chunks via sqlite-vec, optionally joined against a metadata WHERE clause."""
    query_bytes = np.asarray(query_vector, dtype=np.float32).tobytes()
    extra_filter = f"AND {where_sql}" if where_sql else ""
    rows = conn.execute(
        f"""
        SELECT c.id, c.doc_id, c.parent_id, c.text, c.heading, c.source, c.tags, v.distance
        FROM (
            SELECT chunk_id, distance FROM chunk_vectors
            WHERE embedding MATCH ? AND k = ?
        ) v
        JOIN chunks c ON c.id = v.chunk_id
        WHERE c.chunk_type = 'child' {extra_filter}
        ORDER BY v.distance ASC
        """,
        (query_bytes, top_k, *where_params),
    ).fetchall()
    return [dict(row) for row in rows]


def get_all_child_chunks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, doc_id, text FROM chunks WHERE chunk_type = 'child'").fetchall()
    return [dict(row) for row in rows]


def get_document_titles(conn: sqlite3.Connection, doc_ids: list[str]) -> dict[str, str]:
    """Batch-fetches human-readable document titles for a set of doc_ids - used so end users
    see a real document name instead of the raw doc_id in retrieval results/citations.
    Falls back to the source filename (from file_path) when no title was set.
    """
    if not doc_ids:
        return {}
    placeholders = ",".join("?" for _ in doc_ids)
    rows = conn.execute(
        f"SELECT doc_id, title, file_path FROM documents WHERE doc_id IN ({placeholders})", doc_ids
    ).fetchall()
    titles = {}
    for row in rows:
        if row["title"]:
            titles[row["doc_id"]] = row["title"]
        elif row["file_path"]:
            titles[row["doc_id"]] = Path(row["file_path"]).name
        else:
            titles[row["doc_id"]] = row["doc_id"]
    return titles


def get_parent_text(conn: sqlite3.Connection, parent_id: str) -> str | None:
    row = conn.execute("SELECT text FROM chunks WHERE id = ?", (parent_id,)).fetchone()
    return row["text"] if row else None


def upsert_document_record(
    conn: sqlite3.Connection, doc_id: str, content_hash: str, version: int, title: str, source: str,
    file_path: str, updated_at: int,
) -> None:
    conn.execute(
        """
        INSERT INTO documents (doc_id, content_hash, version, title, source, file_path, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            content_hash = excluded.content_hash, version = excluded.version, title = excluded.title,
            source = excluded.source, file_path = excluded.file_path, updated_at = excluded.updated_at
        """,
        (doc_id, content_hash, version, title, source, file_path, updated_at),
    )


def list_documents_summary(conn: sqlite3.Connection) -> list[dict]:
    """One row per document, with a live chunk_count - used by the UI's document list panel."""
    rows = conn.execute(
        """
        SELECT d.doc_id, d.title, d.source, d.file_path, d.version, d.updated_at,
               (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id AND c.chunk_type = 'child') AS chunk_count
        FROM documents d
        ORDER BY d.updated_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_document(conn: sqlite3.Connection, doc_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def delete_document(conn: sqlite3.Connection, doc_id: str) -> None:
    """Removes a document's chunks, vectors, and its own record entirely (used by hard delete via the UI)."""
    chunk_ids = [row["id"] for row in conn.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall()]
    if chunk_ids:
        placeholders = ",".join("?" for _ in chunk_ids)
        conn.execute(f"DELETE FROM chunk_vectors WHERE chunk_id IN ({placeholders})", chunk_ids)
        conn.execute(f"DELETE FROM chunks WHERE id IN ({placeholders})", chunk_ids)
    conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    conn.commit()


def init_default_db(db_path: str) -> sqlite3.Connection:
    embedder = get_embedder()
    conn = connect(db_path)
    init_schema(conn, embedder.dimension)
    return conn
