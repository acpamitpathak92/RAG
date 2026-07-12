import numpy as np

from backend.shared.embeddings.base_embedder import BaseEmbedder
from backend.shared.llm.aiaas_client import get_aiaas_client, get_aiaas_config
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


class AiaasEmbedder(BaseEmbedder):
    """Embeddings via the internal AIaaS gateway's OpenAI-compatible embeddings endpoint.

    Only constructed when llm_config.yaml's aiaas.enabled is true - see
    embeddings/embedder.py's get_embedder(), the sole place that decides which embedding
    backend to use.
    """

    def __init__(self, use_cache: bool = True):
        config = get_aiaas_config()
        model_name = config.get("embedding_model", "")
        if not model_name:
            raise ValueError(
                "aiaas.embedding_model must be set in llm_config.yaml to use AIaaS for embeddings."
            )
        super().__init__(model_name, use_cache)
        self._client = get_aiaas_client()
        # The gateway's embedding dimension isn't known in advance - determine it from one
        # real (uncached) call rather than hardcoding a guess that could drift out of date.
        self.dimension = len(self._encode_raw(["dimension probe"])[0])
        logger.info(f"AiaasEmbedder using model={self.model_name}, dimension={self.dimension}")

    def _encode_raw(self, texts: list[str]) -> np.ndarray:
        response = self._client.embeddings.create(model=self.model_name, input=texts)
        return np.array([item.embedding for item in response.data], dtype=np.float32)
