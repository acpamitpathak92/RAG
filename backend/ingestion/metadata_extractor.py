import time

from backend.ingestion.connectors.base import SourceDocument


def extract_metadata(source_doc: SourceDocument) -> dict:
    """Merges parser-provided front-matter/page metadata with source-level bookkeeping fields."""
    metadata = dict(source_doc.parsed.metadata)
    metadata.setdefault("source", source_doc.source)
    metadata.setdefault("doc_id", source_doc.doc_id)
    metadata.setdefault("ingested_at", int(time.time()))
    metadata.setdefault("tags", metadata.get("tags", ""))
    return metadata
