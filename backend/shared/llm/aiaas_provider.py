from backend.shared.llm.aiaas_client import get_aiaas_client, get_aiaas_config
from backend.shared.llm.base import LLMProvider


class AiaasProvider(LLMProvider):
    """UBS internal AIaaS gateway - an OpenAI-compatible endpoint behind an Azure AD broker.

    The only supported LLM provider (see llm/factory.py). Requires AIAAS_BROKER_URL and
    AIAAS_GATEWAY_BASE_URL set in .env, and the internal `aiaas-auth` package installed
    from the UBS Nexus index (see README setup notes).
    """

    def __init__(self, model: str | None = None, temperature: float = 0.0):
        config = get_aiaas_config()
        super().__init__(model or config["chat_model"], temperature)
        self._client = get_aiaas_client()

    def generate(self, messages: list[dict], **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.pop("temperature", self.temperature),
            max_tokens=kwargs.pop("max_tokens", 1200),
            **kwargs,
        )
        return response.choices[0].message.content or ""
