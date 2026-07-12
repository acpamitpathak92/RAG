from backend.query.grounding.citation_extractor import extract_citations
from backend.query.grounding.confidence_composer import compose_confidence, is_low_confidence


def test_citation_extraction_maps_markers_to_chunks():
    evidence = [
        {"id": "chunk-a", "doc_id": "doc-1", "source": "markdown"},
        {"id": "chunk-b", "doc_id": "doc-2", "source": "markdown"},
    ]
    generation = "The pool was exhausted [1]. Lowering maxSurge fixed it [2]. Also [2] again and [99] (out of range)."

    citations = extract_citations(generation, evidence)

    assert len(citations) == 2
    assert citations[0].marker == 1 and citations[0].chunk_id == "chunk-a"
    assert citations[1].marker == 2 and citations[1].chunk_id == "chunk-b"


def test_citation_extraction_ignores_out_of_range_markers():
    evidence = [{"id": "chunk-a", "doc_id": "doc-1", "source": "markdown"}]
    citations = extract_citations("Some claim [5].", evidence)
    assert citations == []


def test_confidence_composer_blends_retrieval_and_hallucination_signal():
    high = compose_confidence(retrieval_confidence=0.9, hallucination_pass_rate=1.0)
    low = compose_confidence(retrieval_confidence=0.2, hallucination_pass_rate=0.1)
    assert high > low
    assert 0.0 <= high <= 1.0


def test_confidence_composer_applies_caveat_penalty():
    without_caveat = compose_confidence(retrieval_confidence=0.8, hallucination_pass_rate=0.8, needs_caveat=False)
    with_caveat = compose_confidence(retrieval_confidence=0.8, hallucination_pass_rate=0.8, needs_caveat=True)
    assert with_caveat < without_caveat


def test_is_low_confidence_threshold():
    assert is_low_confidence(0.1) is True
    assert is_low_confidence(0.9) is False
