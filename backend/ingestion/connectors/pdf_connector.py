import hashlib
from pathlib import Path

from backend.ingestion.connectors.base import DocumentConnector, SourceDocument
from backend.ingestion.parsers.pdf_parser import parse_pdf


def _doc_id(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


class PDFConnector(DocumentConnector):
    """Reads .pdf files from a local directory."""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()

    def list_documents(self) -> list[str]:
        return [str(p) for p in self.root_dir.rglob("*.pdf")]

    def fetch(self, identifier: str) -> SourceDocument:
        path = Path(identifier)
        parsed = parse_pdf(str(path))
        parsed.metadata.setdefault("title", path.stem)
        raw_bytes = path.read_bytes()
        return SourceDocument(
            doc_id=_doc_id(path),
            source="pdf",
            parsed=parsed,
            raw_content_for_hash=hashlib.sha256(raw_bytes).hexdigest(),
            identifier=str(path),
        )
