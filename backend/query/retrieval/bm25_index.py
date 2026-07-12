import re
import sqlite3

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    """In-process lexical index over all child chunks, rebuilt from the SQLite store.

    Kept in-process (no server) per the user's requirement to avoid any extra services;
    rebuilding on demand is cheap at the corpus sizes this system targets.
    """

    def __init__(self, conn: sqlite3.Connection):
        rows = conn.execute("SELECT id, text FROM chunks WHERE chunk_type = 'child'").fetchall()
        self.chunk_ids = [row["id"] for row in rows]
        tokenized_corpus = [_tokenize(row["text"]) for row in rows]
        self._bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Returns [(chunk_id, bm25_score), ...] sorted descending by score."""
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.chunk_ids, scores), key=lambda pair: pair[1], reverse=True)
        return [(cid, score) for cid, score in ranked[:top_k] if score > 0]


def build_bm25_index(conn: sqlite3.Connection) -> BM25Index:
    """Rebuilds the in-process BM25 index from the current chunk store.

    Called once per process/query-batch rather than per query - cache the instance
    at the call site (e.g. in hybrid_search) if querying repeatedly without re-ingesting.
    """
    return BM25Index(conn)
