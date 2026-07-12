from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.ingestion.parsers.base import ParsedDocument


@dataclass
class SourceDocument:
    """A raw document handed off from a connector to the ingestion pipeline, pre-parsing."""

    doc_id: str  # stable id derived from source path/URL, unchanged across re-ingestion
    source: str  # connector name, e.g. "markdown", "pdf", "gitlab", "sharepoint"
    parsed: ParsedDocument
    raw_content_for_hash: str  # exact bytes/text used to compute content_hash for versioning/dedup
    identifier: str = ""  # the path/URL this was fetched from - used by the UI to edit/delete the source file


class DocumentConnector(ABC):
    """Common interface for all document sources.

    Concrete connectors (markdown, PDF) are implemented now; GitLab/SharePoint are
    stubbed against this same interface so ingestion/pipeline.py never has to change
    when those sources are wired in later (Phase 4).
    """

    @abstractmethod
    def list_documents(self) -> list[str]:
        """Return identifiers (paths/URLs) of documents available from this source."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self, identifier: str) -> SourceDocument:
        """Fetch and parse a single document by identifier."""
        raise NotImplementedError
