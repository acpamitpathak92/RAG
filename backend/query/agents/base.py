from abc import ABC, abstractmethod

from backend.query.graph.state import RAGState
from backend.shared.llm.factory import get_llm


class Agent(ABC):
    """Base class for every LLM-driven agent in the system.

    Each concrete agent owns exactly one narrow scope (see the Multi-Agent Design table
    in the architecture plan): what state fields it reads, what it writes, and which
    LLM role (config/llm_config.yaml) it calls. Agents never call each other directly -
    they only communicate through the shared RAGState, wired together in graph/build.py.
    """

    llm_role: str

    def __init__(self):
        self.llm = get_llm(self.llm_role)

    @abstractmethod
    def run(self, state: RAGState) -> dict:
        """Returns a partial state update (a dict of the fields this agent writes)."""
        raise NotImplementedError
