from backend.ingestion.connectors.base import DocumentConnector, SourceDocument


class GitLabConnector(DocumentConnector):
    """Phase 4 stub: will fetch issues/comments from a GitLab project via its REST/GraphQL API.

    Implements the DocumentConnector interface now so ingestion/pipeline.py and the rest
    of the system never need to change when this is implemented - only this file does.
    """

    def __init__(self, project_id: str, api_token: str, base_url: str = "https://gitlab.com"):
        self.project_id = project_id
        self.api_token = api_token
        self.base_url = base_url

    def list_documents(self) -> list[str]:
        raise NotImplementedError("GitLabConnector is a Phase 4 stub - not yet implemented")

    def fetch(self, identifier: str) -> SourceDocument:
        raise NotImplementedError("GitLabConnector is a Phase 4 stub - not yet implemented")
