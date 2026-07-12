from pathlib import Path

import pytest

from backend.ingestion.connectors.markdown_connector import MarkdownConnector
from backend.ingestion.pipeline import ingest_documents


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_rag.db")
    monkeypatch.setenv("RAG_DB_PATH", db_path)
    from backend.shared.config.settings import get_settings
    get_settings.cache_clear()
    yield db_path
    get_settings.cache_clear()


def test_ingest_is_idempotent(temp_db):
    connector = MarkdownConnector("data/sample_corpus")
    first = ingest_documents(connector, db_path=temp_db)
    assert first["ingested"] == 3

    second = ingest_documents(connector, db_path=temp_db)
    assert second["ingested"] == 0
    assert second["skipped_unchanged"] == 3


def test_ingest_bumps_version_on_change(temp_db, tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    doc_path = corpus / "sample.md"
    doc_path.write_text("## Heading\n\nOriginal content about a bug.", encoding="utf-8")

    connector = MarkdownConnector(str(corpus))
    first = ingest_documents(connector, db_path=temp_db)
    assert first["ingested"] == 1

    doc_path.write_text("## Heading\n\nUpdated content about a different bug entirely.", encoding="utf-8")
    second = ingest_documents(connector, db_path=temp_db)
    assert second["versions_bumped"] == 1


def test_markdown_connector_follows_wikilinks(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_text("See [[b]] for details.", encoding="utf-8")
    (corpus / "b.md").write_text("Linked content.", encoding="utf-8")

    connector = MarkdownConnector(str(corpus), follow_links=True)
    docs = connector.list_documents()
    assert len(docs) == 2


def test_markdown_connector_excludes_readme(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "README.md").write_text("Folder usage instructions, not real content.", encoding="utf-8")
    (corpus / "issue.md").write_text("An actual troubleshooting doc.", encoding="utf-8")

    connector = MarkdownConnector(str(corpus), follow_links=False)
    docs = connector.list_documents()
    assert len(docs) == 1
    assert Path(docs[0]).name == "issue.md"
