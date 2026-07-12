import hashlib
from dataclasses import dataclass, field

from backend.ingestion.chunking.overlap import apply_overlap
from backend.ingestion.chunking.semantic_chunker import semantic_split


@dataclass
class ParentChunk:
    id: str
    doc_id: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ChildChunk:
    id: str
    doc_id: str
    parent_id: str
    chunk_index: int
    text: str
    metadata: dict = field(default_factory=dict)


def _chunk_id(doc_id: str, kind: str, index: int) -> str:
    return hashlib.sha256(f"{doc_id}:{kind}:{index}".encode("utf-8")).hexdigest()[:24]


def build_parent_child_chunks(
    doc_id: str,
    sections: list[tuple[int, str, str]],
    embed_fn,
    base_metadata: dict,
    min_tokens: int = 200,
    max_tokens: int = 400,
    overlap_ratio: float = 0.18,
) -> tuple[list[ParentChunk], list[ChildChunk]]:
    """One ParentChunk per section (full section text, not embedded), with N ChildChunks
    each (semantically split + overlapped, these are what get embedded and indexed).
    """
    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []
    child_counter = 0

    for section_index, (level, heading, body) in enumerate(sections):
        if not body.strip():
            continue

        parent_id = _chunk_id(doc_id, "parent", section_index)
        parents.append(
            ParentChunk(
                id=parent_id,
                doc_id=doc_id,
                text=body,
                metadata={**base_metadata, "heading": heading, "heading_level": level, "chunk_type": "parent"},
            )
        )

        raw_children = semantic_split(body, embed_fn, min_tokens=min_tokens, max_tokens=max_tokens)
        overlapped_children = apply_overlap(raw_children, ratio=overlap_ratio)

        for text in overlapped_children:
            children.append(
                ChildChunk(
                    id=_chunk_id(doc_id, "child", child_counter),
                    doc_id=doc_id,
                    parent_id=parent_id,
                    chunk_index=child_counter,
                    text=text,
                    metadata={**base_metadata, "heading": heading, "chunk_type": "child"},
                )
            )
            child_counter += 1

    return parents, children
