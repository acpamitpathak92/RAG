import math


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def normalize_rerank_scores(chunks: list[dict]) -> list[dict]:
    """Cross-encoder scores are unbounded logits; squash to (0,1) via sigmoid so they can be
    blended with other (already 0-1) signals downstream in grounding/confidence_composer.py.
    """
    return [{**c, "normalized_rerank_score": sigmoid(c["rerank_score"])} for c in chunks]


def aggregate_retrieval_confidence(chunks: list[dict]) -> float:
    """Mean of normalized rerank scores across the final chunk set - a quick pre-generation
    signal of how strong the retrieved evidence is, distinct from the post-generation
    confidence_score computed in grounding/confidence_composer.py (which also folds in
    hallucination pass-rate).
    """
    if not chunks:
        return 0.0
    scores = [c.get("normalized_rerank_score", sigmoid(c.get("rerank_score", 0.0))) for c in chunks]
    return sum(scores) / len(scores)
