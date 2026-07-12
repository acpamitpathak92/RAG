from functools import lru_cache

from backend.shared.llm.base import LLMProvider
from backend.shared.config.settings import get_llm_config
from backend.shared.logging_utils import get_logger

logger = get_logger(__name__)


def _load_provider_class(name: str):
    if name == "groq":
        from backend.shared.llm.groq_provider import GroqProvider
        return GroqProvider
    if name == "aiaas":
        from backend.shared.llm.aiaas_provider import AiaasProvider
        return AiaasProvider
    raise ValueError(f"Unknown LLM provider: {name!r} (supported: 'groq', 'aiaas')")


@lru_cache
def get_llm(role: str) -> LLMProvider:
    """Return the configured LLMProvider for a given agent role (e.g. 'router', 'grader', 'generation', 'judge').

    Provider selection is a single global switch (llm_config.yaml's aiaas.enabled), not a
    per-role setting: when AIaaS is enabled, EVERY role routes through it, using the shared
    aiaas.chat_model - no mixing providers across roles. When disabled, every role uses Groq
    with its own per-role model from the roles: block.
    """
    config = get_llm_config()
    role_config = config["roles"].get(role)
    if role_config is None:
        raise ValueError(f"No LLM config found for role '{role}' in llm_config.yaml")

    if config.get("aiaas", {}).get("enabled", False):
        provider_name = "aiaas"
        model = config["aiaas"]["chat_model"]
    else:
        provider_name = config["default_provider"]
        model = role_config["model"]

    provider_cls = _load_provider_class(provider_name)
    logger.info(f"LLM role '{role}' -> provider={provider_name} model={model}")
    return provider_cls(model=model, temperature=role_config.get("temperature", 0.0))
