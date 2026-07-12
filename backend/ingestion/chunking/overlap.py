def apply_overlap(chunks: list[str], ratio: float = 0.18) -> list[str]:
    """Prepends a trailing slice (by word count) of each chunk onto the next one,
    so context isn't lost at semantic-split boundaries.
    """
    if len(chunks) <= 1 or ratio <= 0:
        return chunks

    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_words = chunks[i - 1].split()
        overlap_word_count = max(1, int(len(prev_words) * ratio))
        overlap_text = " ".join(prev_words[-overlap_word_count:])
        overlapped.append(f"{overlap_text} {chunks[i]}")
    return overlapped
