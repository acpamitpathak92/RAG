import re

import numpy as np

from backend.shared.embeddings.similarity import cosine_similarity

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n{2,}")


def _split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return sentences or ([text.strip()] if text.strip() else [])


def _word_count(text: str) -> int:
    return len(text.split())


def semantic_split(
    text: str,
    embed_fn,
    min_tokens: int = 200,
    max_tokens: int = 400,
    breakpoint_percentile: float = 0.25,
) -> list[str]:
    """Splits `text` into semantically coherent chunks between min/max token bounds.

    Adjacent sentences are embedded and consecutive cosine similarity is computed;
    a "breakpoint" (candidate split point) is any gap whose similarity falls in the
    bottom `breakpoint_percentile` of all gaps - i.e. a topic-boundary drop. Sentences
    are then grouped into chunks, only splitting at breakpoints once a chunk has
    reached `min_tokens`, and force-splitting if `max_tokens` is exceeded regardless.
    """
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    embeddings = embed_fn(sentences)
    gaps = np.array(
        [cosine_similarity(embeddings[i], embeddings[i + 1]) for i in range(len(embeddings) - 1)]
    )
    threshold = np.percentile(gaps, breakpoint_percentile * 100) if len(gaps) else 1.0
    is_breakpoint = gaps <= threshold  # True at index i means sentence i/i+1 boundary is a good split

    chunks: list[str] = []
    current: list[str] = [sentences[0]]
    current_tokens = _word_count(sentences[0])

    for i in range(1, len(sentences)):
        sentence = sentences[i]
        sentence_tokens = _word_count(sentence)
        boundary_is_breakpoint = is_breakpoint[i - 1]

        should_split = current_tokens >= max_tokens or (
            current_tokens >= min_tokens and boundary_is_breakpoint
        )
        if should_split:
            chunks.append(" ".join(current))
            current = [sentence]
            current_tokens = sentence_tokens
        else:
            current.append(sentence)
            current_tokens += sentence_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks
