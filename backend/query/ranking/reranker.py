from functools import lru_cache

from sentence_transformers import CrossEncoder

from backend.shared.config.settings import get_llm_config, get_retrieval_config


class Reranker:
    """Lightweight local cross-encoder reranker (CPU-friendly, same "small model" spirit
    as the MiniLM embedder). Reranks the RRF-fused candidate list down to final top-k.

    Always local regardless of llm_config.yaml's aiaas.enabled - reranking is a scoring
    model, not an LLM or embedding call, and AIaaS doesn't necessarily expose an equivalent.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or get_llm_config()["embedding"]["reranker_model"]
        self._model = CrossEncoder(self.model_name)

    def rerank(self, query: str, chunks: list[dict], top_k: int | None = None) -> list[dict]:
        if not chunks:
            return []
        pairs = [(query, chunk["text"]) for chunk in chunks]
        scores = self._model.predict(pairs)
        scored = [{**chunk, "rerank_score": float(score)} for chunk, score in zip(chunks, scores)]
        scored.sort(key=lambda c: c["rerank_score"], reverse=True)
        top_k = top_k or get_retrieval_config()["top_k_final"]
        return scored[:top_k]


@lru_cache
def get_reranker() -> Reranker:
    return Reranker()
