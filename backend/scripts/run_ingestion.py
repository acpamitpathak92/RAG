"""CLI: ingest a folder of MD or PDF docs. Usage:
  python -m backend.scripts.run_ingestion                              # ingests knowledge_source/ (default)
  python -m backend.scripts.run_ingestion knowledge_source markdown
  python -m backend.scripts.run_ingestion path/to/pdfs pdf
  python -m backend.scripts.run_ingestion data/sample_corpus markdown   # the demo corpus
"""
import sys

from backend.ingestion.connectors.markdown_connector import MarkdownConnector
from backend.ingestion.connectors.pdf_connector import PDFConnector
from backend.ingestion.pipeline import ingest_documents
from backend.shared.constants import KNOWLEDGE_SOURCE_DIR_NAME

if __name__ == "__main__":
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else KNOWLEDGE_SOURCE_DIR_NAME
    source_type = sys.argv[2] if len(sys.argv) > 2 else "markdown"

    connector = PDFConnector(corpus_dir) if source_type == "pdf" else MarkdownConnector(corpus_dir)
    summary = ingest_documents(connector)
    print(summary)
