from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    """Common interface every LLM backend must implement.

    Agents never import a concrete provider directly - they call
    llm.factory.get_llm(role=...) and only see this interface.
    """

    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def generate(self, messages: list[dict], **kwargs) -> str:
        """messages: list of {"role": "system"|"user"|"assistant", "content": str}. Returns the full text response."""
        raise NotImplementedError

    def stream(self, messages: list[dict], **kwargs) -> Iterator[str]:
        """Default streaming fallback: yield the full response as one chunk."""
        yield self.generate(messages, **kwargs)
