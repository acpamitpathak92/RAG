from groq import Groq

from backend.shared.llm.base import LLMProvider
from backend.shared.config.settings import get_settings


class GroqProvider(LLMProvider):
    def __init__(self, model: str, temperature: float = 0.0):
        super().__init__(model, temperature)
        self._client = Groq(api_key=get_settings().groq_api_key)

    def generate(self, messages: list[dict], **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.pop("temperature", self.temperature),
            **kwargs,
        )
        return response.choices[0].message.content or ""
