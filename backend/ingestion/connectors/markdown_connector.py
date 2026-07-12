import hashlib
from pathlib import Path

from backend.ingestion.connectors.base import DocumentConnector, SourceDocument
from backend.ingestion.parsers.markdown_parser import parse_markdown
from backend.shared.constants import README_FILENAME


def doc_id_for_path(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


_doc_id = doc_id_for_path  # internal alias, kept short at call sites below


def _is_folder_readme(path: Path) -> bool:
    """README.md files are folder-usage instructions, not knowledge-base content -
    excluded so they don't pollute retrieval/generation with meta-documentation."""
    return path.name.lower() == README_FILENAME


class MarkdownConnector(DocumentConnector):
    """Reads .md files from a local directory and follows wikilinks/relative links
    to other .md files within the same root, so a linked knowledge graph gets
    ingested even if only the entry-point files were explicitly requested.
    """

    def __init__(self, root_dir: str, follow_links: bool = True):
        self.root_dir = Path(root_dir).resolve()
        self.follow_links = follow_links

    def list_documents(self) -> list[str]:
        seen: set[Path] = set()
        queue = [p for p in self.root_dir.rglob("*.md") if not _is_folder_readme(p)]

        while queue:
            path = queue.pop().resolve()
            if path in seen or not path.exists() or _is_folder_readme(path):
                continue
            seen.add(path)

            if self.follow_links:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for link in parse_markdown(text, str(path)).links:
                    if link.startswith(("http://", "https://")):
                        continue  # plain URLs are out of scope for this connector
                    candidate = (path.parent / link).resolve()
                    if not candidate.suffix:
                        candidate = candidate.with_suffix(".md")
                    if candidate.suffix == ".md" and candidate not in seen:
                        queue.append(candidate)

        return [str(p) for p in seen]

    def fetch(self, identifier: str) -> SourceDocument:
        path = Path(identifier)
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
        parsed = parse_markdown(raw_text, str(path))
        parsed.metadata.setdefault("title", path.stem)
        return SourceDocument(
            doc_id=_doc_id(path),
            source="markdown",
            parsed=parsed,
            raw_content_for_hash=raw_text,
            identifier=str(path),
        )
