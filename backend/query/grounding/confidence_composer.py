from backend.shared.config.settings import get_retrieval_config


def compose_confidence(
    retrieval_confidence: float,
    hallucination_pass_rate: float | None = None,
    needs_caveat: bool = False,
) -> float:
    """Blends retrieval/rerank confidence with hallucination pass-rate (Phase 3+) into one
    final confidence score. In Phase 1 (no hallucination judge yet), hallucination_pass_rate
    is None and treated as neutral (1.0) so the score reduces to the retrieval signal alone.
    """
    weights = get_retrieval_config()["confidence"]
    pass_rate = 1.0 if hallucination_pass_rate is None else hallucination_pass_rate
    # retrieval_confidence (from ranking/scoring.aggregate_retrieval_confidence) already blends
    # similarity + rerank signal, so its two weights are combined into one retrieval-side weight.
    retrieval_weight = weights["weight_similarity"] + weights["weight_rerank"]

    score = retrieval_weight * retrieval_confidence + weights["weight_hallucination_pass_rate"] * pass_rate
    if needs_caveat:
        score *= weights["caveat_penalty_multiplier"]
    return max(0.0, min(1.0, score))


def is_low_confidence(score: float) -> bool:
    return score < get_retrieval_config()["confidence"]["low_confidence_threshold"]


def has_sufficient_evidence(retrieval_confidence: float, chunk_count: int) -> bool:
    """Gate checked BEFORE generation: if retrieval turned up nothing or evidence is this weak,
    skip the LLM call entirely rather than let it stretch irrelevant chunks into a rambling,
    forced-sounding "answer". See retrieval_insufficient_threshold in retrieval_config.yaml.
    """
    if chunk_count == 0:
        return False
    return retrieval_confidence >= get_retrieval_config()["confidence"]["retrieval_insufficient_threshold"]
