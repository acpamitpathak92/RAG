from backend.ingestion.connectors.base import DocumentConnector, SourceDocument


class SharePointConnector(DocumentConnector):
    """Phase 4 stub: will fetch documents from a SharePoint document library via the Microsoft
    Graph API. Implements the DocumentConnector interface now so the rest of the system never
    needs to change when this is implemented - only this file does.
    """

    def __init__(self, site_url: str, client_id: str, client_secret: str):
        self.site_url = site_url
        self.client_id = client_id
        self.client_secret = client_secret

    def list_documents(self) -> list[str]:
        raise NotImplementedError("SharePointConnector is a Phase 4 stub - not yet implemented")

    def fetch(self, identifier: str) -> SourceDocument:
        raise NotImplementedError("SharePointConnector is a Phase 4 stub - not yet implemented")
