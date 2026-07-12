from pydantic import BaseModel

from backend.shared.constants import KNOWLEDGE_SOURCE_DIR_NAME


class QueryRequest(BaseModel):
    query: str


class CitationOut(BaseModel):
    marker: int
    chunk_id: str
    doc_id: str
    doc_title: str = ""
    chunk_text: str = ""
    source: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    confidence_score: float
    needs_caveat: bool
    original_query: str
    corrected_query: str | None = None  # only set when query_was_corrected is true
    query_was_corrected: bool = False


class IngestRequest(BaseModel):
    corpus_dir: str = KNOWLEDGE_SOURCE_DIR_NAME
    source_type: str = "markdown"  # "markdown" | "pdf"


class IngestResponse(BaseModel):
    ingested: int
    skipped_unchanged: int
    versions_bumped: int


class DocumentOut(BaseModel):
    doc_id: str
    title: str | None = None
    source: str | None = None
    file_path: str | None = None
    version: int
    chunk_count: int
    updated_at: int | None = None


class UpdateDocumentRequest(BaseModel):
    content: str


class DocumentStatusResponse(BaseModel):
    doc_id: str
    status: str


class DocumentContentResponse(BaseModel):
    doc_id: str
    filename: str
    content: str


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
