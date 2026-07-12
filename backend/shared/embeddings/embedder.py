from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.shared.config.settings import get_llm_config
from backend.shared.embeddings.base_embedder import BaseEmbedder


class Embedder(BaseEmbedder):
    """Local sentence-transformers embedding model (default: MiniLM, 384-dim, CPU-friendly).

    Used when llm_config.yaml's aiaas.enabled is false - see get_embedder() below, the sole
    place that decides which embedding backend to construct.
    """

    def __init__(self, model_name: str | None = None, use_cache: bool = True):
        model_name = model_name or get_llm_config()["embedding"]["local_model"]
        super().__init__(model_name, use_cache)
        self._model = SentenceTransformer(self.model_name)
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self.dimension = get_dim()

    def _encode_raw(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, convert_to_numpy=True)


@lru_cache
def get_embedder() -> BaseEmbedder:
    """Returns the configured embedder - local MiniLM by default, or the AIaaS gateway
    embedding model if llm_config.yaml's aiaas.enabled is true. Every caller (ingestion,
    retrieval) goes through this instead of constructing an embedder directly, so the
    master AIaaS switch actually covers embeddings too, not just LLM chat calls.
    """
    if get_llm_config().get("aiaas", {}).get("enabled", False):
        from backend.shared.embeddings.aiaas_embedder import AiaasEmbedder
        return AiaasEmbedder()
    return Embedder()
