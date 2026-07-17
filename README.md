# Advanced RAG System for Issue Retrieval

A local, multi-agent Retrieval-Augmented Generation system for troubleshooting/issue
knowledge bases (Markdown, PDF now; GitLab/SharePoint interfaces stubbed for later).
Built with LangGraph, SQLite + sqlite-vec (no external services), and the internal
UBS **AIaaS** gateway for every LLM call and every embedding call - the only supported
provider (no Groq, no local Hugging Face models).

See `C:\Users\Amit Chandra Pathak\.claude\plans\i-want-to-create-parallel-twilight.md`
for the full architecture plan (multi-agent design, CRAG, Grounding subsystems, phased
build order), [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) for a complete, plain-English,
step-by-step walkthrough of both the question-answering flow and the document-ingestion
flow (no code references — anyone should be able to follow it), and
[`docs/ARCHITECTURE_DIAGRAM.md`](docs/ARCHITECTURE_DIAGRAM.md) for a visual draw.io
flowchart of the whole system, [`docs/BACKEND_BUILD_ORDER.md`](docs/BACKEND_BUILD_ORDER.md)
for a from-scratch, file-by-file build order covering the minimum viable ingestion +
retrieval backend (what file to write next, its imports and their purpose, and what
each function does), and [`docs/CHUNKING_STRATEGY.md`](docs/CHUNKING_STRATEGY.md) for a
deep dive into exactly how documents get split (parent-child chunking, semantic
splitting, overlap, and the config values behind them).

## Project Layout

All Python source lives under `backend/`, split by what runs when:

```
backend/
├── shared/       # infra used by both pipelines: config, constants, logging, LLM providers, embeddings, SQLite storage
├── ingestion/    # runs once per document: connectors, parsers, cleaning, chunking, dedup, versioning
├── query/        # runs once per question: retrieval, ranking, agents, grounding, the LangGraph pipeline
├── api/          # FastAPI app gluing both together over HTTP
├── scripts/      # CLI utilities (init_db, run_ingestion, eval_retrieval)
└── tests/
```

`backend/shared/constants.py` holds cross-cutting magic numbers/strings (default paths,
thresholds, prefixes) so they aren't scattered across files. Everything is a proper
Python package (`backend.shared.llm.factory`, `backend.query.graph.build`, etc.) run
from the project root.

## How to Run

### 1. Install dependencies

```
python -m venv venv
source venv/Scripts/activate   # Windows cmd/PowerShell: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**AIaaS is the only supported LLM/embedding/reranking provider** — every LLM call
(query cleanup, grading, generation, reranking, etc.) and every embedding call goes
through the internal UBS gateway. There's no Groq fallback and no local
Hugging Face model to download.

Connection details (tenant, broker/gateway URLs, OAuth scopes, model names) are
environment-specific and sensitive, so they're **all set in `.env`, never committed**
— fill these in after `cp .env.example .env`:

```
AIAAS_AUTH_MODE=devpod
AIAAS_TENANT_ID=...
AIAAS_BROKER_URL=...
AIAAS_SCOPES=api://...
AIAAS_GATEWAY_BASE_URL=...
AIAAS_CHAT_MODEL=Qwen/Qwen3.0-27B
AIAAS_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
```

The only AIaaS-related setting that stays in `backend/shared/config/llm_config.yaml`
(committed, not sensitive) is the per-role temperature block, since it doesn't vary by
environment.

Since there's nothing to run locally, ingestion and every question **require live
AIaaS connectivity** — there is no offline/local mode.

The `aiaas-auth` package AIaaS depends on lives on UBS's internal Nexus registry, not
public PyPI — one-time setup:

```
pip config set global.extra-index-url https://nexus-write.artifactmgmt.ubs.net/service/...
```

### 2. Initialize the local database (one-time, idempotent)

```
python -m backend.scripts.init_db
```

### 3. Add your documents to `knowledge_source/`

Drop your `.md` and/or `.pdf` issue/troubleshooting docs into the
[`knowledge_source/`](knowledge_source/README.md) folder (subfolders are fine). A
demo corpus also lives in `data/sample_corpus/` if you just want to try the system
out first.

### 4. Ingest

```
python -m backend.scripts.run_ingestion                      # ingests knowledge_source/ (markdown)
python -m backend.scripts.run_ingestion knowledge_source pdf  # if your docs are PDFs
python -m backend.scripts.run_ingestion data/sample_corpus markdown  # try the demo corpus instead
```

Re-run this any time you add or edit files — unchanged files are skipped automatically.

### 5. Start the app

```
uvicorn backend.api.main:app --port 8000
```

Then open **http://localhost:8000/** in a browser for a zero-setup static test UI
(ingest + ask questions, no build step), or call the API directly:

- `GET /health`
- `POST /ingest {"corpus_dir": "knowledge_source", "source_type": "markdown"|"pdf"}`
- `POST /query {"query": "..."}` → `{answer, citations, confidence_score, needs_caveat}`
- `GET /documents`, `POST /documents`, `POST /documents/upload` (PDF), `GET/PUT/DELETE /documents/{doc_id}` — manage the knowledge base

### 6. (Optional) React UI

A fuller React app lives in [`frontend/`](frontend/README.md) - same capabilities as
the static UI, plus a dedicated "Upload PDF" flow. With the backend running (step 5):

```
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173/**. Vite's dev server proxies `/query`, `/documents`,
`/ingest`, `/health` straight to the backend on port 8000 - no CORS setup needed.

### Optional: check retrieval quality

```
python -m backend.scripts.eval_retrieval
```

Runs the sample eval set (`data/eval/qa_eval_set.jsonl`) through the full pipeline
and reports hit-rate/MRR plus a citation-correctness spot-check.

### Logging

Requests log at INFO by default (one line per pipeline stage: retrieval, ranking,
routing decision, generation, citations, confidence, final response) so you can
follow a request's path through the system in the terminal. Set `VERBOSE_LOGGING=true`
in `.env` for DEBUG-level detail (per-query hit counts, chunk scores, timings per stage).

## Tests

```
pytest backend/tests/
```

## Status

**Phase 1 (done)**: ingestion (MD/PDF, semantic + parent-child chunking, dedup, versioning),
AIaaS embeddings (+ local cache), hybrid retrieval (sqlite-vec dense + BM25, RRF-fused),
LLM-based reranking (batched relevance scoring via AIaaS), Grounded Generation Agent with
citations, deterministic confidence scoring (with a pre-generation insufficient-evidence
gate to avoid rambling answers on weak retrieval), FastAPI + document management
endpoints + test UI, logging.

**Phase 2 (not yet implemented)**: CRAG grading/retry loop - a grader agent, query
refinement agent, bounded retry loop, and fallback ladder, wired into
`backend/query/graph/build.py`'s conditional edges. Reusable prompt-building patterns
already exist in `backend/query/grounding/prompts.py` to build from.

**Phase 3 (not yet implemented)**: hallucination judge agent (claim-by-claim entailment
checking against cited evidence).

**Phase 4 (stubbed)**: `backend/ingestion/connectors/gitlab_connector.py` and
`sharepoint_connector.py` implement `DocumentConnector` but raise `NotImplementedError`.
