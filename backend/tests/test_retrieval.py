import pytest

from backend.ingestion.connectors.markdown_connector import MarkdownConnector
from backend.ingestion.pipeline import ingest_documents
from backend.query.retrieval.hybrid_search import hybrid_search
from backend.shared.storage.vector_store import connect


@pytest.fixture
def ingested_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_rag.db")
    monkeypatch.setenv("RAG_DB_PATH", db_path)
    from backend.shared.config.settings import get_settings
    get_settings.cache_clear()

    connector = MarkdownConnector("data/sample_corpus")
    ingest_documents(connector, db_path=db_path)

    conn = connect(db_path)
    yield conn
    conn.close()
    get_settings.cache_clear()


def test_hybrid_search_finds_relevant_chunk(ingested_db):
    hits = hybrid_search(ingested_db, "why are billing service pods getting killed after a deploy?", top_k=5)
    assert len(hits) > 0
    assert any("TooManyConnectionsError" in h["text"] or "connection pool" in h["text"].lower() for h in hits)


def test_hybrid_search_returns_rrf_scores(ingested_db):
    hits = hybrid_search(ingested_db, "stale cache prices", top_k=5)
    assert all("rrf_score" in h for h in hits)
    scores = [h["rrf_score"] for h in hits]
    assert scores == sorted(scores, reverse=True)
