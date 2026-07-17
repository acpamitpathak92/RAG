# Architecture Diagram (draw.io)

A full draw.io / diagrams.net diagram of the system lives at
[`docs/architecture.drawio`](architecture.drawio) — open it to see the complete
ingestion + query flow as an editable flowchart.

## How to open it

- **Web**: go to [app.diagrams.net](https://app.diagrams.net) → *File → Open From →
  Device* → select `docs/architecture.drawio`.
- **VS Code**: install the "Draw.io Integration" extension (`hediet.vscode-drawio`),
  then just click `architecture.drawio` in the file tree — it renders and edits
  in-place, no separate app needed.
- **Desktop app**: the [draw.io desktop app](https://github.com/jgraph/drawio-desktop)
  opens `.drawio` files directly.

## What's in the diagram

It's laid out as two connected lanes plus a shared storage layer, matching how the
system actually runs:

- **Top lane — Ingestion Pipeline** (green boxes): runs once per document, from
  reading a file out of the knowledge source folder all the way to storing its
  embeddings.
- **Middle — Storage** (grey boxes): the local SQLite + sqlite-vec store and the
  in-process BM25 index that ingestion feeds and querying reads from.
- **Bottom lane — Query Pipeline** (blue boxes): runs every time a question is
  asked, from the chat UI through retrieval, reranking, a confidence gate, and
  finally back to the user.
- **Branch after the confidence gate**: a diamond decision box splits into the
  orange "insufficient evidence" fallback path (no LLM call) versus the purple
  "grounded generation" path, which calls out to the internal AIaaS gateway
  (dashed box) before continuing through citation mapping and confidence scoring.
  Reranking earlier in the pipeline also goes through AIaaS (a batched relevance-scoring
  prompt), not a separately-hosted model.

## Legend

| Color | Meaning |
|---|---|
| 🟩 Green | Ingestion-time steps (once per document) |
| ⬜ Grey | Persistent local storage |
| 🟦 Blue | Query-time steps that always run |
| 🟨 Yellow diamond | Decision point (conditional routing) |
| 🟧 Orange | Deterministic post-processing (no LLM call) |
| 🟪 Purple | Steps involving an LLM call |

## Text fallback (if you can't open draw.io right now)

```
INGESTION (once per document):
Knowledge Source (.md/.pdf) -> Document Parsing -> Text Cleaning -> Metadata Extraction
  -> Parent-Child + Semantic Chunking -> Dedup + Versioning -> Embedding Generation
  -> [stored in] SQLite + sqlite-vec (vectors) and In-process BM25 Index (chunk text)

QUERY (every question):
User Question -> Query Embedding -> Hybrid Retrieval (reads both stores, RRF-fused)
  -> Parent Document Retrieval -> LLM-Based Reranking (AIaaS) -> "Enough good evidence?"
       -- no  --> Insufficient Evidence Node (honest fallback message) --------\
       -- yes --> Grounded Generation Agent <--> Internal AIaaS Gateway         |
                     -> Citation Mapping -> Confidence Scoring -----------------+--> Respond Node -> shown to user
```

See [`docs/QUERY_FLOW.md`](QUERY_FLOW.md) for the plain-English walkthrough of the
bottom lane, and [`docs/HOW_IT_WORKS.md`](HOW_IT_WORKS.md) for both lanes with code
file references.
