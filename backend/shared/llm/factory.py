from functools import lru_cache

from backend.shared.llm.aiaas_provider import AiaasProvider
from backend.shared.config.settings import get_llm_config
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


@lru_cache
def get_llm(role: str) -> AiaasProvider:
    """Return the AIaaS-backed LLM for a given agent role (e.g. 'router', 'grader',
    'generation', 'judge', 'reranker'). AIaaS is the only supported LLM provider - every
    role uses the shared aiaas.chat_model, with its own per-role temperature from the
    roles: block in llm_config.yaml.
    """
    config = get_llm_config()
    role_config = config["roles"].get(role)
    if role_config is None:
        raise ValueError(f"No LLM config found for role '{role}' in llm_config.yaml")

    model = config["aiaas"]["chat_model"]
    logger.info(f"LLM role '{role}' -> model={model}")
    return AiaasProvider(model=model, temperature=role_config.get("temperature", 0.0))
