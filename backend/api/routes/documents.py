from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from backend.api.schemas import (
    DocumentContentResponse,
    DocumentOut,
    DocumentStatusResponse,
    DocumentUploadResponse,
    UpdateDocumentRequest,
)
from backend.shared.config.settings import get_settings
from backend.ingestion.connectors.markdown_connector import MarkdownConnector, doc_id_for_path
from backend.ingestion.connectors.pdf_connector import PDFConnector
from backend.ingestion.pipeline import ingest_single_document
from backend.shared.constants import KNOWLEDGE_SOURCE_DIR_NAME, README_FILENAME
from backend.shared.storage.vector_store import (
    delete_document,
    get_document,
    init_default_db,
    list_documents_summary,
)

router = APIRouter()

KNOWLEDGE_SOURCE_DIR = Path(KNOWLEDGE_SOURCE_DIR_NAME).resolve()


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()  # strips any directory components - no path traversal
    if not name or name.lower() == README_FILENAME:
        raise HTTPException(400, "Invalid filename")
    return name


@router.get("/documents", response_model=list[DocumentOut])
def list_documents():
    conn = init_default_db(get_settings().rag_db_path)
    try:
        return list_documents_summary(conn)
    finally:
        conn.close()


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile):
    """Adds a document by uploading a real .md or .pdf file - the one way to add
    a document, so the knowledge base always reflects actual files on disk."""
    filename = _safe_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in (".md", ".pdf"):
        raise HTTPException(400, "Only .md and .pdf files are supported")

    KNOWLEDGE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    doc_path = KNOWLEDGE_SOURCE_DIR / filename
    doc_path.write_bytes(await file.read())

    if suffix == ".pdf":
        connector = PDFConnector(str(KNOWLEDGE_SOURCE_DIR))
    else:
        connector = MarkdownConnector(str(KNOWLEDGE_SOURCE_DIR), follow_links=False)
    status = ingest_single_document(connector, str(doc_path))
    return DocumentUploadResponse(doc_id=doc_id_for_path(doc_path), filename=filename, status=status)


@router.post("/documents/{doc_id}/reingest", response_model=DocumentStatusResponse)
def reingest_document(doc_id: str):
    """Re-runs ingestion against whatever is currently on disk for this document - useful
    for PDFs (which can't be edited in-browser) or any file edited outside the app."""
    conn = init_default_db(get_settings().rag_db_path)
    try:
        existing = get_document(conn, doc_id)
    finally:
        conn.close()
    if existing is None or not existing.get("file_path"):
        raise HTTPException(404, "Document not found")

    doc_path = Path(existing["file_path"])
    if not doc_path.exists():
        raise HTTPException(404, "Source file is missing on disk")

    if existing.get("source") == "pdf":
        connector = PDFConnector(str(doc_path.parent))
    else:
        connector = MarkdownConnector(str(doc_path.parent), follow_links=False)
    status = ingest_single_document(connector, str(doc_path))
    return DocumentStatusResponse(doc_id=doc_id, status=status)


@router.get("/documents/{doc_id}", response_model=DocumentContentResponse)
def get_document_content(doc_id: str):
    conn = init_default_db(get_settings().rag_db_path)
    try:
        existing = get_document(conn, doc_id)
    finally:
        conn.close()
    if existing is None or not existing.get("file_path"):
        raise HTTPException(404, "Document not found")
    if existing.get("source") == "pdf":
        raise HTTPException(400, "PDF documents can't be edited as text - delete and re-add instead")

    doc_path = Path(existing["file_path"])
    if not doc_path.exists():
        raise HTTPException(404, "Source file is missing on disk")

    return DocumentContentResponse(doc_id=doc_id, filename=doc_path.name, content=doc_path.read_text(encoding="utf-8"))


@router.put("/documents/{doc_id}", response_model=DocumentStatusResponse)
def update_document(doc_id: str, request: UpdateDocumentRequest):
    conn = init_default_db(get_settings().rag_db_path)
    try:
        existing = get_document(conn, doc_id)
    finally:
        conn.close()
    if existing is None or not existing.get("file_path"):
        raise HTTPException(404, "Document not found")
    if existing.get("source") == "pdf":
        raise HTTPException(400, "PDF documents can't be edited as text - delete and re-add instead")

    doc_path = Path(existing["file_path"])
    doc_path.write_text(request.content, encoding="utf-8")

    connector = MarkdownConnector(str(doc_path.parent), follow_links=False)
    status = ingest_single_document(connector, str(doc_path))
    return DocumentStatusResponse(doc_id=doc_id, status=status)


@router.delete("/documents/{doc_id}", response_model=DocumentStatusResponse)
def remove_document(doc_id: str):
    conn = init_default_db(get_settings().rag_db_path)
    try:
        existing = get_document(conn, doc_id)
        if existing is None:
            raise HTTPException(404, "Document not found")
        delete_document(conn, doc_id)
    finally:
        conn.close()

    file_path = existing.get("file_path")
    if file_path:
        Path(file_path).unlink(missing_ok=True)

    return DocumentStatusResponse(doc_id=doc_id, status="deleted")
