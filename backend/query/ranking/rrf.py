def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    """Fuses multiple ranked id lists (e.g. dense hits, BM25 hits) into one score per id.

    score(id) = sum over lists containing id of 1 / (k + rank), rank is 1-indexed.
    `k` is RRF's standard smoothing constant (60 is the commonly used default).
    """
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, item_id in enumerate(ranked_list, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores
