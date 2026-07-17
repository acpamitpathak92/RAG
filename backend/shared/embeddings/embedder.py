from functools import lru_cache

import numpy as np

from backend.shared.embeddings.base_embedder import BaseEmbedder
from backend.shared.llm.aiaas_client import get_aiaas_client, get_aiaas_config
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


class Embedder(BaseEmbedder):
    """Embeddings via the internal AIaaS gateway's OpenAI-compatible embeddings endpoint -
    the only supported embedding backend.
    """

    def __init__(self, use_cache: bool = True):
        config = get_aiaas_config()
        model_name = config.get("embedding_model", "")
        if not model_name:
            raise ValueError(
                "AIAAS_EMBEDDING_MODEL must be set in .env to use embeddings."
            )
        super().__init__(model_name, use_cache)
        self._client = get_aiaas_client()
        # The gateway's embedding dimension isn't known in advance - determine it from one
        # real (uncached) call rather than hardcoding a guess that could drift out of date.
        self.dimension = len(self._encode_raw(["dimension probe"])[0])
        logger.info(f"Embedder using model={self.model_name}, dimension={self.dimension}")

    def _encode_raw(self, texts: list[str]) -> np.ndarray:
        response = self._client.embeddings.create(model=self.model_name, input=texts)
        return np.array([item.embedding for item in response.data], dtype=np.float32)


@lru_cache
def get_embedder() -> Embedder:
    return Embedder()
