GENERATION_SYSTEM_PROMPT = """You are a support engineer assistant answering questions about known issues, \
bug reports, and troubleshooting runbooks using ONLY the evidence chunks provided below.

Rules:
- Answer using ONLY the provided evidence. Do not use outside knowledge.
- For every factual claim, add an inline citation marker like [1], [2] referencing the evidence chunk number \
it came from. Every sentence that states a fact must have at least one citation.
- If the evidence does not fully answer the question, say so explicitly instead of guessing or inventing details.
- Be concise and technical - this is for an engineer troubleshooting a live issue, not a general audience.
- Format for readability using Markdown: short paragraphs, a numbered or bulleted list for any sequence of \
steps/causes/fixes, and **bold** for key terms (error names, config keys, commands). Do not put the entire \
answer in a single dense paragraph if it covers more than one point."""


def build_generation_prompt(query: str, evidence_chunks: list[dict], caveat: bool = False) -> list[dict]:
    evidence_block = "\n\n".join(
        f"[{i + 1}] (source: {c.get('source', 'unknown')}, doc: {c.get('heading') or c.get('doc_id')})\n{c['text']}"
        for i, c in enumerate(evidence_chunks)
    )
    caveat_note = (
        "\nNote: retrieval confidence for this query was low - be extra conservative about what you claim, "
        "and prefer stating uncertainty over guessing.\n"
        if caveat
        else ""
    )
    user_content = f"Question: {query}\n{caveat_note}\nEvidence:\n{evidence_block}\n\nAnswer with inline [n] citations:"
    return [
        {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


REGENERATE_WITH_FEEDBACK_SUFFIX = """

Your previous answer included claims that were NOT supported by the cited evidence:
{failed_claims}

Regenerate your answer using only claims that the evidence actually supports. If the evidence doesn't
support a claim, omit it or explicitly say the evidence is insufficient."""
