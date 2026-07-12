from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

from backend.shared.config.settings import get_settings
from backend.shared.constants import EMBEDDING_CACHE_SUFFIX
from backend.shared.embeddings.cache import EmbeddingCache
from backend.shared.embeddings.normalize import normalize


class BaseEmbedder(ABC):
    """Shared caching/batching logic for any embedding backend (local model or AIaaS).

    Subclasses implement _encode_raw() - the actual model/API call - and get caching,
    normalization, and the embed()/embed_query() interface used by the rest of the app
    for free, so swapping backends never touches retrieval/ranking/ingestion code.
    """

    dimension: int  # subclasses must set this before the first embed() call

    def __init__(self, model_name: str, use_cache: bool = True):
        self.model_name = model_name
        if use_cache:
            db_path = Path(get_settings().rag_db_path)
            cache_path = db_path.with_name(db_path.stem + EMBEDDING_CACHE_SUFFIX + db_path.suffix)
            self._cache = EmbeddingCache(str(cache_path), self.model_name)
        else:
            self._cache = None

    @abstractmethod
    def _encode_raw(self, texts: list[str]) -> np.ndarray:
        """Returns raw (unnormalized) embeddings for a batch of texts."""
        raise NotImplementedError

    def embed(self, texts: list[str]) -> np.ndarray:
        """Returns an (N, dim) float32 array of L2-normalized embeddings."""
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        if self._cache is None:
            return normalize(self._encode_raw(texts))

        vectors = [None] * len(texts)
        to_compute_idx = []
        to_compute_text = []
        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                vectors[i] = cached
            else:
                to_compute_idx.append(i)
                to_compute_text.append(text)

        if to_compute_text:
            computed = normalize(self._encode_raw(to_compute_text))
            for idx, vec, text in zip(to_compute_idx, computed, to_compute_text):
                vectors[idx] = vec
                self._cache.put(text, vec)

        return np.vstack(vectors).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
