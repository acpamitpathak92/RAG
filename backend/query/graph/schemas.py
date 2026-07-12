from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    id: str
    doc_id: str
    doc_title: str = ""  # human-readable document name/title, shown to end users instead of the raw doc_id
    parent_id: str | None = None
    text: str
    parent_text: str | None = None
    heading: str = ""
    source: str = ""
    tags: str = ""
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    normalized_rerank_score: float = 0.0


class GradedChunk(BaseModel):
    chunk: RetrievedChunk
    grade: str  # "correct" | "ambiguous" | "incorrect"
    reason: str = ""


class Citation(BaseModel):
    marker: int  # the "[n]" the model emitted
    chunk_id: str
    doc_id: str
    doc_title: str = ""  # human-readable document name, for end-user display
    chunk_text: str = ""  # short snippet of the cited chunk's actual text, for end-user display
    source: str
    claim_text: str = ""


class ClaimVerdict(BaseModel):
    claim: str
    citation_marker: int | None
    verdict: str  # "entailed" | "contradicted" | "not_addressed"


class HallucinationReport(BaseModel):
    claims: list[ClaimVerdict] = []
    pass_rate: float = 1.0
