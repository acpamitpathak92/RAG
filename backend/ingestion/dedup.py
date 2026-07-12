import hashlib


def content_hash(text: str) -> str:
    """Exact-match hash used to skip re-processing unchanged content."""
    normalized = " ".join(text.split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
