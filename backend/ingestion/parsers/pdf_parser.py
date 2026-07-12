import fitz  # PyMuPDF

from backend.ingestion.parsers.base import ParsedDocument


def parse_pdf(file_path: str) -> ParsedDocument:
    doc = fitz.open(file_path)
    page_texts = [page.get_text() for page in doc]
    full_text = "\n\n".join(page_texts).strip()
    metadata = {
        "source_path": file_path,
        "page_count": doc.page_count,
        "title": doc.metadata.get("title") or "",
    }
    doc.close()

    # PDFs have no heading markup, so treat each page as one "section" for parent/child chunking.
    sections = [(1, f"Page {i + 1}", text.strip()) for i, text in enumerate(page_texts) if text.strip()]
    if not sections:
        sections = [(1, "", full_text)]

    return ParsedDocument(text=full_text, metadata=metadata, links=[], sections=sections)
