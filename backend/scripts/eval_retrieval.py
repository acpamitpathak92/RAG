"""Computes retrieval hit-rate/MRR against data/eval/qa_eval_set.jsonl, and runs each
question through the full Phase 1 graph to spot-check citation correctness.

Usage: python scripts/eval_retrieval.py
"""
import json
from pathlib import Path

from backend.shared.config.settings import get_settings
from backend.query.graph.build import run_query
from backend.ingestion.connectors.markdown_connector import MarkdownConnector
from backend.query.retrieval.hybrid_search import hybrid_search
from backend.shared.storage.vector_store import connect

EVAL_SET_PATH = "data/eval/qa_eval_set.jsonl"
CORPUS_DIR = "data/sample_corpus"


def _stem_to_doc_id(corpus_dir: str) -> dict[str, str]:
    connector = MarkdownConnector(corpus_dir, follow_links=False)
    mapping = {}
    for path_str in connector.list_documents():
        doc = connector.fetch(path_str)
        mapping[Path(path_str).stem] = doc.doc_id
    return mapping


def load_eval_set(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    stem_to_doc_id = _stem_to_doc_id(CORPUS_DIR)
    eval_set = load_eval_set(EVAL_SET_PATH)
    conn = connect(get_settings().rag_db_path)

    hits_at_k = 0
    reciprocal_ranks = []
    answerable = [row for row in eval_set if row["expected_doc_ids"]]

    print(f"Evaluating {len(eval_set)} questions ({len(answerable)} answerable, {len(eval_set) - len(answerable)} intentionally unanswerable)\n")

    for row in eval_set:
        expected_doc_ids = {stem_to_doc_id[stem] for stem in row["expected_doc_ids"] if stem in stem_to_doc_id}
        retrieved = hybrid_search(conn, row["question"], top_k=5)
        retrieved_doc_ids = [c["doc_id"] for c in retrieved]

        rank = None
        for i, doc_id in enumerate(retrieved_doc_ids, start=1):
            if doc_id in expected_doc_ids:
                rank = i
                break

        if expected_doc_ids:
            if rank:
                hits_at_k += 1
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)

        result = run_query(conn, row["question"])
        cited_doc_ids = {c.doc_id for c in result.get("citations", [])}
        citation_grounded = (not expected_doc_ids) or bool(cited_doc_ids & expected_doc_ids)

        print(f"Q: {row['question']}")
        print(f"  expected_doc_ids={sorted(expected_doc_ids) or '(none - unanswerable)'} rank={rank}")
        print(f"  confidence={result['confidence_score']:.3f} needs_caveat={result['needs_caveat']} citation_grounded={citation_grounded}")
        print()

    if answerable:
        print(f"Hit-rate@5: {hits_at_k}/{len(answerable)} = {hits_at_k / len(answerable):.2f}")
        print(f"MRR: {sum(reciprocal_ranks) / len(reciprocal_ranks):.2f}")

    conn.close()


if __name__ == "__main__":
    main()
