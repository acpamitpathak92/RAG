import hashlib
import sqlite3
import threading
from pathlib import Path

import numpy as np


class EmbeddingCache:
    """Content-hash keyed embedding cache backed by a small SQLite table.

    Avoids re-embedding unchanged chunk text across ingestion re-runs.

    This cache is created once (via embeddings.embedder.get_embedder's lru_cache) and
    reused for the lifetime of the process, but FastAPI runs sync route handlers across
    a thread pool - so the same connection can be hit from different threads on
    different requests. check_same_thread=False plus a lock make that safe: SQLite
    connections tolerate being used from any thread as long as access is serialized.
    """

    def __init__(self, db_path: str, model_name: str):
        self.model_name = model_name
        self._lock = threading.Lock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_cache (
                content_hash TEXT NOT NULL,
                model_name TEXT NOT NULL,
                vector BLOB NOT NULL,
                PRIMARY KEY (content_hash, model_name)
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> np.ndarray | None:
        content_hash = self.hash_text(text)
        with self._lock:
            row = self._conn.execute(
                "SELECT vector FROM embedding_cache WHERE content_hash = ? AND model_name = ?",
                (content_hash, self.model_name),
            ).fetchone()
        if row is None:
            return None
        return np.frombuffer(row[0], dtype=np.float32)

    def put(self, text: str, vector: np.ndarray) -> None:
        content_hash = self.hash_text(text)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO embedding_cache (content_hash, model_name, vector) VALUES (?, ?, ?)",
                (content_hash, self.model_name, np.asarray(vector, dtype=np.float32).tobytes()),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
