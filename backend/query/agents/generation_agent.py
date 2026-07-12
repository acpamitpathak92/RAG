from backend.query.agents.base import Agent
from backend.query.graph.state import RAGState, effective_query
from backend.query.grounding.prompts import REGENERATE_WITH_FEEDBACK_SUFFIX, build_generation_prompt
from backend.shared.logging_utils import get_logger, log_stage

logger = get_logger(__name__)


def _evidence_chunks(state: RAGState) -> list[dict]:
    """Prefers CRAG-graded correct/ambiguous chunks (Phase 2+); falls back to raw reranked
    retrieved_chunks so the Phase 1 straight-through path (no grader yet) still works.
    """
    graded = state.get("graded_chunks")
    if graded:
        chunks = [g.chunk.model_dump() for g in graded if g.grade in ("correct", "ambiguous")]
        if chunks:
            return chunks
    return [c.model_dump() if hasattr(c, "model_dump") else c for c in state.get("retrieved_chunks", [])]


class GenerationAgent(Agent):
    """Composes the answer strictly from evidence chunks, with inline [n] citations.

    No tool access by design: this agent can only reason over the evidence handed to it in
    the prompt, so it cannot "invent" its way around missing evidence via an external call.
    """

    llm_role = "generation"

    def run(self, state: RAGState) -> dict:
        evidence = _evidence_chunks(state)
        if not evidence:
            logger.info("GenerationAgent: no evidence chunks available, skipping LLM call")
            return {
                "generation": "I could not find any supporting evidence in the knowledge base for this question.",
                "needs_caveat": True,
            }

        with log_stage(logger, "GenerationAgent.run", evidence_chunks=len(evidence), model=self.llm.model):
            messages = build_generation_prompt(
                query=effective_query(state), evidence_chunks=evidence, caveat=state.get("needs_caveat", False)
            )
            generation = self.llm.generate(messages)
            logger.debug(f"GenerationAgent produced {len(generation)} chars")
        return {"generation": generation, "_evidence_used": evidence}

    def regenerate_with_feedback(self, state: RAGState, failed_claims: list[str]) -> dict:
        evidence = state.get("_evidence_used") or _evidence_chunks(state)
        messages = build_generation_prompt(query=effective_query(state), evidence_chunks=evidence, caveat=True)
        messages.append(
            {
                "role": "user",
                "content": REGENERATE_WITH_FEEDBACK_SUFFIX.format(failed_claims="\n".join(f"- {c}" for c in failed_claims)),
            }
        )
        generation = self.llm.generate(messages)
        return {"generation": generation}
