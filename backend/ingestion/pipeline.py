import sqlite3
import time

from backend.shared.config.settings import get_retrieval_config, get_settings
from backend.shared.embeddings.embedder import Embedder, get_embedder
from backend.ingestion.chunking.parent_child import build_parent_child_chunks
from backend.ingestion.cleaning import clean_text
from backend.ingestion.connectors.base import DocumentConnector, SourceDocument
from backend.ingestion.dedup import content_hash
from backend.ingestion.metadata_extractor import extract_metadata
from backend.ingestion.versioning import get_current_doc_state, sweep_orphaned_chunks
from backend.shared.logging_utils import get_logger, log_stage
from backend.shared.storage.vector_store import init_default_db, upsert_chunk, upsert_document_record

logger = get_logger(__name__)


def process_source_document(
    conn: sqlite3.Connection, embedder: Embedder, chunk_config: dict, source_doc: SourceDocument
) -> str:
    """Runs one document through clean -> extract metadata -> chunk -> dedup/version -> embed -> index.

    Shared by the bulk folder-ingestion path (ingest_documents) and the single-document
    add/edit API path (ingestion.pipeline.ingest_single_document), so both go through
    identical processing. Returns "ingested" | "skipped_unchanged" | "versions_bumped".
    """
    doc_hash = content_hash(source_doc.raw_content_for_hash)

    existing = get_current_doc_state(conn, source_doc.doc_id)
    if existing is not None and existing[0] == doc_hash:
        logger.debug(f"skip_unchanged: {source_doc.identifier}")
        return "skipped_unchanged"

    new_version = (existing[1] + 1) if existing else 1
    status = "versions_bumped" if existing is not None else "ingested"

    cleaned_sections = [
        (level, heading, clean_text(body)) for level, heading, body in source_doc.parsed.sections
    ]
    base_metadata = extract_metadata(source_doc)

    parents, children = build_parent_child_chunks(
        doc_id=source_doc.doc_id,
        sections=cleaned_sections,
        embed_fn=embedder.embed,
        base_metadata=base_metadata,
        min_tokens=chunk_config["child_min_tokens"],
        max_tokens=chunk_config["child_max_tokens"],
        overlap_ratio=chunk_config["overlap_ratio"],
    )

    now = int(time.time())
    for parent in parents:
        upsert_chunk(
            conn,
            {
                "id": parent.id, "doc_id": parent.doc_id, "parent_id": None, "chunk_type": "parent",
                "chunk_index": None, "version": new_version, "source": source_doc.source, "text": parent.text,
                "heading": parent.metadata.get("heading", ""), "tags": parent.metadata.get("tags", ""),
                "content_hash": content_hash(parent.text), "created_at": now,
            },
            embedding=None,
        )

    if children:
        child_embeddings = embedder.embed([c.text for c in children])
        for child, vector in zip(children, child_embeddings):
            upsert_chunk(
                conn,
                {
                    "id": child.id, "doc_id": child.doc_id, "parent_id": child.parent_id, "chunk_type": "child",
                    "chunk_index": child.chunk_index, "version": new_version, "source": source_doc.source,
                    "text": child.text, "heading": child.metadata.get("heading", ""),
                    "tags": child.metadata.get("tags", ""), "content_hash": content_hash(child.text),
                    "created_at": now,
                },
                embedding=vector,
            )

    upsert_document_record(
        conn, doc_id=source_doc.doc_id, content_hash=doc_hash, version=new_version,
        title=base_metadata.get("title", ""), source=source_doc.source,
        file_path=source_doc.identifier, updated_at=now,
    )
    sweep_orphaned_chunks(conn, source_doc.doc_id, new_version)
    conn.commit()
    logger.info(
        f"{status}: {source_doc.identifier} (v{new_version}, {len(parents)} sections, {len(children)} chunks)"
    )
    return status


def ingest_documents(connector: DocumentConnector, db_path: str | None = None) -> dict:
    """Runs the full ingest flow for every document a connector exposes.

    Returns a summary dict: {ingested, skipped_unchanged, versions_bumped}.
    """
    db_path = db_path or get_settings().rag_db_path
    conn = init_default_db(db_path)
    embedder = get_embedder()
    chunk_config = get_retrieval_config()["chunk"]

    documents = connector.list_documents()
    summary = {"ingested": 0, "skipped_unchanged": 0, "versions_bumped": 0}
    with log_stage(logger, "ingest_documents", documents_found=len(documents)):
        for identifier in documents:
            source_doc = connector.fetch(identifier)
            status = process_source_document(conn, embedder, chunk_config, source_doc)
            summary[status] += 1
        logger.info(f"ingest_documents summary: {summary}")

    conn.close()
    return summary


def ingest_single_document(connector: DocumentConnector, identifier: str, db_path: str | None = None) -> str:
    """Fetches and ingests exactly one document (used by the add/edit-document API endpoints,
    so saving a single file doesn't require re-scanning the whole knowledge_source folder).
    Returns "ingested" | "skipped_unchanged" | "versions_bumped".
    """
    db_path = db_path or get_settings().rag_db_path
    conn = init_default_db(db_path)
    embedder = get_embedder()
    chunk_config = get_retrieval_config()["chunk"]

    source_doc = connector.fetch(identifier)
    status = process_source_document(conn, embedder, chunk_config, source_doc)
    conn.close()
    return status
