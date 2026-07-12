from fastapi import APIRouter

from backend.api.schemas import IngestRequest, IngestResponse
from backend.ingestion.connectors.markdown_connector import MarkdownConnector
from backend.ingestion.connectors.pdf_connector import PDFConnector
from backend.ingestion.pipeline import ingest_documents

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest):
    if request.source_type == "pdf":
        connector = PDFConnector(request.corpus_dir)
    else:
        connector = MarkdownConnector(request.corpus_dir)
    summary = ingest_documents(connector)
    return IngestResponse(**summary)
