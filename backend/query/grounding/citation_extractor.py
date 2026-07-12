import re

from backend.query.graph.schemas import Citation
from backend.shared.constants import CITATION_SNIPPET_MAX_CHARS

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


def _snippet(text: str, max_chars: int = CITATION_SNIPPET_MAX_CHARS) -> str:
    """Short, end-user-facing preview of a chunk's text, cut at a word boundary."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def extract_citations(generation: str, evidence_chunks: list[dict]) -> list[Citation]:
    """Deterministically parses [n] markers out of the generation and maps them back to the
    actual evidence chunk metadata (chunk_id/doc_id/source), plus a human-readable document
    title and a short text snippet so end users see what a citation actually says instead of
    just an id. Never trusts anything the model claims about the mapping beyond the marker
    number itself, so citations are auditable.
    """
    citations = []
    seen_markers = set()
    for match in _CITATION_MARKER_RE.finditer(generation):
        marker = int(match.group(1))
        if marker in seen_markers:
            continue
        index = marker - 1
        if 0 <= index < len(evidence_chunks):
            chunk = evidence_chunks[index]
            citations.append(
                Citation(
                    marker=marker,
                    chunk_id=chunk["id"],
                    doc_id=chunk["doc_id"],
                    doc_title=chunk.get("doc_title") or chunk["doc_id"],
                    chunk_text=_snippet(chunk.get("text", "")),
                    source=chunk.get("source", ""),
                )
            )
            seen_markers.add(marker)
    return citations
