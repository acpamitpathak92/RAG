# Backend Build Order — Ingestion + Retrieval (Minimum Viable)

If you were rewriting this backend from scratch, this is the order to write files in,
and why that order. Scope is deliberately limited to the two most basic parts:
**ingestion** (getting documents into a searchable store) and **retrieval** (searching
that store and getting ranked results back). It stops right before generation/agents/API
— i.e., it gets you to "I can hand a query to a function and get back a ranked list of
relevant text chunks," which is the foundation everything else sits on top of.

For every file, the same four things are covered, in this order:
1. **The file** — its path and why it needs to exist at this point in the build.
2. **Imports** — every import it needs, and what each one is *for*.
3. **What it defines** — every function/class in it, and what it actually does.
4. **How to sanity-check it** — a quick way to confirm the file works before moving on.

Build strictly in this order. Every step only depends on files from *earlier* steps,
never later ones — so at every point, what you've built so far actually runs.

---

## Phase 0 — Foundations

Nothing here touches documents or search yet. This is the shared plumbing that every
later file will import: configuration, math utilities, the embedding model wrapper, and
the local database. Get this working first because everything else is built on top of it.

### Step 1 — `shared/constants.py`

**Why now:** You'll immediately start hardcoding small values (default folder names,
thresholds, filenames to ignore) as you write later files. Putting them in one file from
day one means you never have the same magic string typed in three different places.

**Imports:** none — this file only *defines* values, it doesn't need anything else.

**What it defines:** plain constants, e.g. a default folder name for where documents
live, a default path for the local database file, a filename to always skip during
ingestion (like `README.md`), a max length for text previews shown to users later. No
functions yet — just named values other files will import.

**Sanity check:** `python -c "from shared.constants import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH)"`
should print your chosen default path with no errors.

---

### Step 2 — `shared/config/settings.py`

**Why now:** Almost every file you write after this needs to know things like "where's
the database file" or "what's my API key" — and that needs to come from environment
variables/a `.env` file, not be hardcoded. Write this early so every later file can
depend on it.

**Imports:**
- `pathlib.Path` — for building filesystem paths in an OS-independent way (works the
  same on Windows and Linux).
- `functools.lru_cache` — a decorator that makes a function compute its result once and
  reuse it forever after, instead of recomputing every call. You use this so "load
  settings from disk" only happens once per run, not on every single access.
- A settings library (e.g. `pydantic-settings`'s `BaseSettings`) — gives you a class
  where each attribute automatically gets filled in from an environment variable or a
  `.env` file, with type checking, instead of you writing manual `os.environ.get(...)`
  calls everywhere.
- `yaml` — for reading `.yaml` config files (you'll add small YAML files later for
  retrieval tuning knobs — top-k values, chunk sizes, etc.).
- Your own `shared.constants` module from Step 1 — for the default values.

**What it defines:**
- A `Settings` class (subclassing the settings-library base) with fields like the
  database file path and any API keys — these get their values from environment
  variables automatically.
- `get_settings()` — a cached function that returns one shared `Settings` instance.
- A small YAML-loading helper, plus one or two cached functions like
  `get_retrieval_config()` that read a specific YAML file and return it as a plain
  dictionary — this is where things like "how many results to return" will live, so you
  can tune them without touching code.

**Sanity check:** create a `.env` file with one dummy value, then confirm
`get_settings()` reads it back correctly.

---

### Step 3 — `shared/embeddings/normalize.py`

**Why now:** This is pure math with zero dependencies on anything else you've built —
a good, low-risk first file in the embeddings area.

**Imports:**
- `numpy` — for fast array/vector math. Embeddings are just lists of numbers (vectors),
  and numpy is what makes operating on thousands of them per second practical.

**What it defines:**
- A `normalize(vector_or_matrix)` function that rescales a vector (or a batch of them)
  so its length is exactly 1 — "L2 normalization." This matters because later, when you
  compare two vectors for similarity, having both at length 1 turns that comparison into
  a simple dot product instead of a more expensive calculation.

**Sanity check:** normalize a random vector and confirm its length (`numpy.linalg.norm`)
comes out to `1.0`.

---

### Step 4 — `shared/embeddings/similarity.py`

**Why now:** Also pure math, and it's used immediately once you have real embeddings
(Step 6 onward), so write it right after normalization.

**Imports:**
- `numpy` — same reason as Step 3.

**What it defines:**
- A `cosine_similarity(vector_a, vector_b)` function returning a single number between
  -1 and 1 (in practice, close to 0-1 for real embeddings) representing how similar two
  vectors' *directions* are — the core "how alike do these two pieces of text mean" check.
- Optionally, a batch version that compares one vector against a whole matrix of others
  at once (comparing a question against every stored chunk in one call instead of a slow
  loop).

**Sanity check:** compare a vector against itself — should return `1.0` (or very close,
accounting for floating-point rounding).

---

### Step 5 — `shared/embeddings/cache.py`

**Why now:** Before writing the actual embedding model wrapper, build its cache, since
the embedder will depend on this, not the other way around.

**Imports:**
- `sqlite3` — Python's built-in database library. The cache itself is just a tiny local
  SQL table: (content hash, model name) → (stored vector).
- `hashlib` — to turn a piece of text into a short, fixed-length fingerprint (a hash),
  used as the cache's lookup key instead of storing the full text twice.
- `threading` — a `Lock` object, so that if two requests try to read/write the cache
  from different threads at the same time, they don't corrupt each other.
- `numpy` — vectors are stored/retrieved as raw number arrays.

**What it defines:**
- An `EmbeddingCache` class with:
  - A constructor that opens (or creates) a small SQLite file and makes sure the cache
    table exists.
  - `get(text)` — hash the text, look it up, return the cached vector if found, else
    `None`.
  - `put(text, vector)` — hash the text and store the vector under that hash.
  - Both methods are wrapped with the lock, so concurrent access from multiple requests
    doesn't crash.

**Sanity check:** put a fake vector in under some text, then get it back with the exact
same text and confirm it matches.

---

### Step 6 — `shared/embeddings/base_embedder.py`

**Why now:** You're about to write two different embedding backends (a local model, and
later possibly a remote API). Rather than duplicate the caching/batching logic in both,
write one shared base class first that both will inherit from.

**Imports:**
- `abc` — `ABC` and `abstractmethod`, Python's tools for saying "this is a template;
  concrete subclasses *must* implement this one method, or Python will refuse to let you
  instantiate them."
- `numpy` — vectors, as always.
- Your `EmbeddingCache` from Step 5.
- Your `normalize` from Step 3.

**What it defines:**
- A `BaseEmbedder` abstract class with:
  - A constructor that sets up the shared `EmbeddingCache`.
  - An abstract `_encode_raw(texts)` method — deliberately left unimplemented here; each
    concrete subclass fills this in with its own way of actually calling a model.
  - `embed(texts)` — the real logic: for each input text, check the cache first; only
    call `_encode_raw()` (the expensive part) for texts that weren't already cached;
    normalize everything; return one array of vectors. This method never changes
    between subclasses — only `_encode_raw` does.
  - `embed_query(text)` — a convenience wrapper for embedding a single piece of text.

**Sanity check:** this class can't be tested directly (it's abstract) — you'll verify it
indirectly in the next step.

---

### Step 7 — `shared/embeddings/embedder.py`

**Why now:** Now you have everywhere it depends on ready (cache, normalize, base class,
settings). This is the first file that actually produces real embeddings.

**Imports:**
- `sentence_transformers.SentenceTransformer` — the library that loads a small,
  pretrained text-embedding model and runs it locally, no external API needed.
- Your `BaseEmbedder` from Step 6.
- Your `get_retrieval_config` (or wherever you decide to store the model name) from
  Step 2.

**What it defines:**
- An `Embedder` class (extends `BaseEmbedder`):
  - Constructor: loads the model by name (e.g. a small, CPU-friendly model), and records
    its output vector size (`dimension`) — you'll need this exact number later when
    creating the vector database table.
  - `_encode_raw(texts)` — the one method the base class asked for: hand a batch of
    texts to the loaded model and get raw vectors back.
- A module-level `get_embedder()` function, cached so the (somewhat slow-to-load) model
  is only loaded into memory once per process, not once per request.

**Sanity check:** `get_embedder().embed(["hello world"])` should return one 1-row array
with as many columns as the model's known dimension.

---

### Step 8 — `shared/storage/vector_store.py`

**Why now:** This is the last foundational piece — the actual local database. Both
ingestion (which writes to it) and retrieval (which reads from it) depend on this file,
so it must exist before either.

**Imports:**
- `sqlite3` — the database itself.
- `sqlite_vec` — a SQLite extension that adds vector similarity search directly inside
  SQLite, so you don't need a separate specialized vector database server.
- `numpy` — vectors go in and out as numpy arrays; SQLite stores them as raw bytes.
- `pathlib.Path` — to make sure the folder for the database file exists before opening it.

**What it defines:**
- `connect(db_path)` — opens a SQLite connection, turns on the `sqlite_vec` extension for
  that connection, and enables a couple of performance-related SQLite settings (WAL
  mode, which lets reads and writes coexist better).
- `init_schema(conn, embedding_dim)` — creates the tables if they don't already exist:
  one table for document-level bookkeeping (id, content hash, version), one for the
  actual text chunks (with columns for id, parent id, chunk type, the text itself,
  heading, source, tags, etc.), and one special *virtual table* (via `sqlite_vec`) sized
  to exactly `embedding_dim` columns, for the vectors themselves.
- `upsert_chunk(conn, chunk_row, embedding)` — insert a new chunk row (or overwrite an
  existing one with the same id), and separately insert/replace its vector in the vector
  table.
- `dense_search(conn, query_vector, top_k, ...)` — the actual nearest-neighbor vector
  search: given a query vector, ask `sqlite_vec` for the `top_k` closest stored vectors,
  join back to the chunks table to get the real text/metadata for each hit.
- A few small lookup helpers: fetching a parent chunk's full text by id, fetching a
  document's current stored version/content-hash, listing all child chunks (needed later
  for building the keyword index), deleting a document and all its chunks.

**Sanity check:** call `init_schema` on a throwaway database file, `upsert_chunk` one
fake row with a fake vector, then `dense_search` using that same vector as the query and
confirm you get exactly that one chunk back.

---

**Phase 0 checkpoint:** at this point you can load an embedding model, turn text into
vectors, cache them, and store/search them in a local database — with nothing about
documents, parsing, or chunking yet. Everything below builds on this foundation.

---

## Phase 1 — Ingestion

Now you start turning real files into searchable chunks in the store from Phase 0.

### Step 9 — `ingestion/parsers/base.py`

**Why now:** Before writing a parser for any specific file format, define the common
shape every parser's output will have — so Markdown and PDF parsers (and anything you
add later) all hand back the same kind of object.

**Imports:** `dataclasses.dataclass` — a quick way to define a simple data-holding class
without writing a manual `__init__`.

**What it defines:** a `ParsedDocument` data class holding: the extracted text, a
metadata dictionary (title, tags, whatever the format provides), a list of any links
found in the document, and a list of "sections" (heading level, heading text, section
body) — this last field is what later chunking will split on.

**Sanity check:** none needed yet — it's just a data shape.

---

### Step 10 — `ingestion/parsers/markdown_parser.py`

**Why now:** Pick one format to support first (Markdown is simplest — plain text with
light structure). Write its parser now so the connector in the next step has something
to call.

**Imports:**
- `re` — regular expressions, used to spot `[[wikilink]]`-style links and normal Markdown
  links inside the text.
- A Markdown parsing library (e.g. `markdown-it-py`) — turns raw Markdown text into a
  structured token stream so you can reliably find heading boundaries, instead of
  guessing with regex.
- Your `ParsedDocument` from Step 9.

**What it defines:**
- A link-extraction helper that scans raw text for wikilinks and Markdown links.
- A section-extraction helper that walks the Markdown token stream, finds every heading,
  and slices the raw text between one heading and the next into `(level, heading_text,
  body)` tuples.
- `parse_markdown(raw_text, source_path)` — the main entry point: pulls out any YAML
  front-matter block at the top of the file (simple `key: value` pairs between `---`
  lines) as metadata, then returns a fully populated `ParsedDocument`.

**Sanity check:** parse a small string with two `##` headings and confirm you get back
two sections with the right heading text and body.

---

### Step 11 — `ingestion/connectors/base.py`

**Why now:** Same reasoning as Step 9 — define the common shape/interface before writing
a concrete implementation, so later "sources" (uploaded file, PDF, and eventually
non-file sources) all plug in the same way.

**Imports:**
- `abc` — `ABC`/`abstractmethod`, same reasoning as Step 6: this defines a contract
  concrete connectors must follow.
- `dataclasses.dataclass`.
- Your `ParsedDocument` from Step 9.

**What it defines:**
- A `SourceDocument` data class: a stable `doc_id`, which connector produced it
  (`"markdown"`, `"pdf"`, ...), the `ParsedDocument` itself, the raw content used for
  hashing/versioning, and the original file path/identifier.
- A `DocumentConnector` abstract class with two required methods: `list_documents()`
  (return identifiers for everything this source has available) and `fetch(identifier)`
  (load and parse one specific document by identifier).

**Sanity check:** none yet — abstract.

---

### Step 12 — `ingestion/connectors/markdown_connector.py`

**Why now:** The first concrete connector — this is what actually reads `.md` files off
disk and hands back `SourceDocument`s.

**Imports:**
- `hashlib` — to compute a stable id for a document from its file path.
- `pathlib.Path` — filesystem operations: listing files, reading text, resolving paths.
- Your `DocumentConnector`/`SourceDocument` from Step 11.
- Your `parse_markdown` from Step 10.

**What it defines:**
- `doc_id_for_path(path)` — hashes a resolved file path into a short, stable id (the same
  file always produces the same id, so re-ingesting it updates the same record instead of
  creating a duplicate).
- A `MarkdownConnector` class:
  - `list_documents()` — recursively finds every `.md` file under a root folder
    (skipping `README.md`, since that's folder documentation, not real content), and
    optionally follows wikilinks/relative links found inside each file to also pick up
    linked documents that live outside the folder you pointed it at.
  - `fetch(identifier)` — reads one file's text, parses it, and wraps it in a
    `SourceDocument`.

**Sanity check:** point it at a small test folder with two linked `.md` files and
confirm `list_documents()` finds both.

---

### Step 13 — `ingestion/cleaning.py`

**Why now:** A small, standalone utility with no dependencies — write it whenever, but
you need it before the pipeline (Step 20) so text is clean before it gets chunked.

**Imports:** `re` — for stripping unwanted characters/whitespace patterns.

**What it defines:** `clean_text(text)` — removes stray control characters, collapses
three-or-more blank lines down to at most two, strips trailing whitespace from each line.

**Sanity check:** feed it a string with excessive blank lines and confirm the output is
collapsed correctly.

---

### Step 14 — `ingestion/metadata_extractor.py`

**Why now:** Another small, standalone utility, needed before the pipeline.

**Imports:** `time` — to record an ingestion timestamp. Your `SourceDocument` type from
Step 11 (only for type-hinting/reading its fields).

**What it defines:** `extract_metadata(source_doc)` — merges whatever metadata the parser
already found (title, tags) with bookkeeping fields (which connector this came from, the
document id, an ingestion timestamp), returning one flat dictionary that gets attached to
every chunk from this document.

**Sanity check:** pass in a fake `SourceDocument` and confirm the returned dictionary has
all the expected keys.

---

### Step 15 — `ingestion/dedup.py`

**Why now:** Needed by the pipeline (Step 20) to decide whether a document/chunk has
actually changed.

**Imports:** `hashlib` — for computing a content fingerprint.

**What it defines:** `content_hash(text)` — normalizes whitespace and casing, then
returns a SHA-256 hash of the result. Two pieces of text that are meaningfully identical
(just different capitalization or spacing) hash the same, so trivial formatting-only
edits don't trigger unnecessary reprocessing.

**Sanity check:** hash the same sentence twice with different spacing/capitalization and
confirm the hashes match; change an actual word and confirm the hash changes.

---

### Step 16 — `ingestion/versioning.py`

**Why now:** Needed by the pipeline to know whether a document is brand new, unchanged,
or has been edited since last time.

**Imports:** `sqlite3` (only for type-hinting the connection parameter).

**What it defines:**
- `get_current_doc_state(conn, doc_id)` — looks up the stored content-hash and version
  number for a document, or `None` if it's never been seen before.
- `sweep_orphaned_chunks(conn, doc_id, current_version)` — after re-ingesting a changed
  document, deletes any chunk rows left over from an *older* version (e.g. if the
  document got shorter and some old chunks no longer correspond to anything).

**Sanity check:** insert a fake document row directly, then confirm
`get_current_doc_state` returns it correctly; insert some chunks tagged with an old
version number and confirm the sweep removes exactly those.

---

### Step 17 — `ingestion/chunking/semantic_chunker.py`

**Why now:** The most conceptually involved ingestion file — write it once cleaning
(Step 13) and embeddings (Step 7) both already exist, since it needs both.

**Imports:**
- `re` — a simple sentence-boundary splitter.
- `numpy` — for handling the array of similarity scores between sentences.
- Your `cosine_similarity` from Step 4.

**What it defines:**
- A private sentence-splitting helper.
- A private word-count helper (used as a cheap stand-in for "token count").
- `semantic_split(text, embed_fn, min_tokens, max_tokens, ...)` — the core idea: embed
  every sentence individually, measure how similar each sentence is to the *next* one,
  and treat a big drop in similarity as a sign the topic just changed (a good place to
  split). It only actually splits at these "breakpoints" once the current chunk has
  reached a minimum size, and force-splits regardless if a chunk grows past a maximum
  size. Returns a list of chunk-sized text strings.

**Sanity check:** feed it a paragraph that clearly covers two different topics and
confirm it splits into two chunks roughly where the topic changes.

---

### Step 18 — `ingestion/chunking/overlap.py`

**Why now:** A small, standalone follow-up to Step 17.

**Imports:** none needed beyond the standard library.

**What it defines:** `apply_overlap(chunks, ratio)` — for each chunk after the first,
prepends the tail end (by word count, sized by `ratio`) of the *previous* chunk onto its
own beginning, so a reader/searcher never hits a hard, contextless cutoff right at a
chunk boundary.

**Sanity check:** pass in two short fake chunks and confirm the second one now starts
with the tail words of the first.

---

### Step 19 — `ingestion/chunking/parent_child.py`

**Why now:** This ties Steps 17 and 18 together with the section structure from parsing
(Step 10) — write it last in the chunking group since it depends on both.

**Imports:**
- `hashlib` — for deterministic chunk ids.
- `dataclasses.dataclass`.
- Your `apply_overlap` from Step 18 and `semantic_split` from Step 17.

**What it defines:**
- `ParentChunk` and `ChildChunk` data classes — a parent chunk is a whole section's text;
  a child chunk is one small, searchable piece with a link back to its parent's id.
- A private deterministic-id helper (hash of document id + chunk type + index, so
  re-ingesting the same document produces the same ids instead of new random ones every
  time).
- `build_parent_child_chunks(doc_id, sections, embed_fn, base_metadata, ...)` — for every
  section: create one `ParentChunk`; run `semantic_split` + `apply_overlap` on its body
  to get however many `ChildChunk`s it needs. Returns the full lists of both.

**Sanity check:** feed it two fake sections and confirm you get back one parent per
section, and a reasonable number of child chunks whose text, concatenated, roughly
reconstructs the original sections.

---

### Step 20 — `ingestion/pipeline.py`

**Why now:** The final ingestion file — it wires together every single file from Steps
1-19 into one end-to-end process. Nothing in ingestion works as a whole system until
this file exists.

**Imports:** everything you've built so far in this phase — the connector base type, the
cleaning function, the dedup/versioning helpers, the chunking builder, the metadata
extractor — plus your embedder (Step 7) and vector store (Step 8) from Phase 0. Also
`time`, for recording timestamps.

**What it defines:**
- `process_source_document(conn, embedder, chunk_config, source_doc)` — the real
  per-document logic: compute a content hash; if unchanged, stop immediately
  (`"skipped_unchanged"`); otherwise clean the text, extract metadata, build parent/child
  chunks, embed every child chunk, save everything (parents without embeddings, children
  with), update the document's stored version, sweep away any orphaned old chunks, and
  report whether this was a first-time ingest or a version bump.
- `ingest_documents(connector, db_path)` — the bulk entry point: ask a connector for
  every document it knows about, run `process_source_document` on each one, and return a
  summary count of how many were ingested / skipped / bumped.
- `ingest_single_document(connector, identifier, db_path)` — the same logic for exactly
  one document, used when you already know which file changed and don't want to rescan
  an entire folder.

**Sanity check — the real end-to-end test:** point a `MarkdownConnector` at a small
folder of two or three real-looking `.md` files, run `ingest_documents`, then directly
query the vector store's chunk table and confirm rows exist with real text, real
metadata, and real vectors attached. Run it a second time immediately and confirm
everything reports `"skipped_unchanged"`.

---

**Phase 1 checkpoint:** you can now point this at a folder of Markdown files and end up
with a fully populated, deduplicated, versioned, chunked, embedded local database. Only
retrieval is missing.

---

## Phase 2 — Retrieval

Everything here only *reads* from the store Phase 1 built — nothing here writes to it.

### Step 21 — `query/ranking/rrf.py`

**Why now:** A tiny, pure, standalone function with zero dependencies on anything
retrieval-specific — a good first file in this phase.

**Imports:** none needed beyond the standard library.

**What it defines:** `reciprocal_rank_fusion(ranked_lists, k)` — given several separate
ranked lists of ids (e.g. one from vector search, one from keyword search), produces one
merged score per id by summing `1 / (k + rank)` across every list it appears in. An id
that ranks well in *either* list gets a meaningfully high combined score, rather than one
method completely dominating.

**Sanity check:** fuse two tiny fake ranked lists by hand and confirm the combined
ranking matches what you'd expect (an id near the top of both lists should end up on top
overall).

---

### Step 22 — `query/retrieval/bm25_index.py`

**Why now:** Needed before hybrid search (Step 24), which calls it directly.

**Imports:**
- `re` — a simple tokenizer (splitting text into lowercase word tokens).
- `sqlite3` (type-hinting only).
- A BM25 library (e.g. `rank_bm25`'s `BM25Okapi`) — implements the actual BM25 keyword
  relevance-scoring algorithm so you don't have to write it by hand.

**What it defines:**
- A private tokenizer helper.
- A `BM25Index` class: on construction, reads every stored chunk's text out of the
  database and builds an in-memory keyword index over all of it; `search(query, top_k)`
  tokenizes the query and returns the best-matching chunk ids with their BM25 scores.
- `build_bm25_index(conn)` — a thin wrapper that constructs a fresh `BM25Index` from
  whatever's currently in the database (rebuilt on demand rather than kept permanently
  in sync, since it's cheap enough at this scale).

**Sanity check:** ingest two documents with clearly distinct vocabulary, build the index,
and confirm a keyword unique to one document only returns that document's chunks.

---

### Step 23 — `query/retrieval/metadata_filter.py`

**Why now:** A small standalone utility, needed by hybrid search for optional filtering.

**Imports:** none needed beyond the standard library.

**What it defines:** `build_where_clause(filters)` — turns a simple dictionary (like
`{"source": "markdown"}`) into a SQL `WHERE` fragment plus its parameter values, safely
parameterized (never string-concatenating user input directly into SQL). Returns an
empty clause if no filters were given, so callers don't need special-case handling.

**Sanity check:** pass in a filter dict and confirm the SQL fragment plus parameters
look correct and match what you'd hand-write yourself.

---

### Step 24 — `query/retrieval/hybrid_search.py`

**Why now:** This is where vector search (Step 8), BM25 (Step 22), RRF (Step 21), and
metadata filtering (Step 23) all come together — write it once all four exist.

**Imports:** your `get_embedder` (Phase 0), your vector store's `dense_search` (Phase 0),
your `build_bm25_index` (Step 22), your `reciprocal_rank_fusion` (Step 21), your
`build_where_clause` (Step 23), plus `get_retrieval_config` (Phase 0) for tunable values
like how many candidates to pull from each method.

**What it defines:** `hybrid_search(conn, query, filters, top_k)` — the full retrieval
entry point: embed the query; run vector search and BM25 search independently; fuse
their two ranked id lists with RRF; look up full chunk records (text, metadata) for the
final merged ranking; attach each chunk's fused score; return the ranked list.

**Sanity check:** run a query you know should match one of your ingested test documents
and confirm that document's chunks come back near the top.

---

### Step 25 — `query/retrieval/parent_retriever.py`

**Why now:** A small, standalone follow-up to hybrid search.

**Imports:** `sqlite3` (type-hinting); your vector store's parent-text lookup helper
(Phase 0).

**What it defines:** `expand_to_parents(conn, child_hits)` — for every child-chunk hit,
looks up and attaches its parent chunk's full section text, so downstream consumers get
both the precise matching snippet *and* its full surrounding context.

**Sanity check:** run hybrid search, expand the results, and confirm each result now
carries a non-empty parent-section text alongside its original chunk text.

---

### Step 26 — `query/ranking/reranker.py`

**Why now:** Independent of everything else in Phase 2 except that it needs candidates
to rerank — write it any time after Step 24, before Step 27 (which needs its output).

**Imports:** a cross-encoder model class from `sentence_transformers` (e.g.
`CrossEncoder`); `get_retrieval_config`/wherever you store the model name (Phase 0).

**What it defines:**
- A `Reranker` class: on construction, loads a small cross-encoder model (a model that
  reads a query and a candidate *together*, rather than comparing separately computed
  vectors — slower, but much more precise for a small final shortlist).
  `rerank(query, chunks, top_k)` — scores every candidate chunk against the query, sorts
  by score, and returns only the best `top_k`.
- A cached `get_reranker()` accessor, same reasoning as the cached embedder — this model
  is somewhat slow to load, so load it once per process.

**Sanity check:** hand it a query plus a handful of chunks (some obviously relevant, some
not) and confirm the obviously-relevant ones score higher and end up on top.

---

### Step 27 — `query/ranking/scoring.py`

**Why now:** The final file — turns raw reranker scores into something usable as a
confidence signal.

**Imports:** `math` (for a sigmoid function); nothing else new.

**What it defines:**
- `sigmoid(x)` — squashes an unbounded number into the 0-1 range, since raw cross-encoder
  scores aren't naturally bounded and you want something interpretable as "how confident
  is this."
- `normalize_rerank_scores(chunks)` — applies `sigmoid` to every chunk's raw rerank
  score and attaches the normalized version.
- `aggregate_retrieval_confidence(chunks)` — averages the normalized scores across the
  final chunk set into one overall number summarizing how strong the retrieved evidence
  looks as a whole.

**Sanity check:** hand it a few chunks with known rerank scores and confirm the
normalized values and the aggregate average come out in the 0-1 range as expected.

---

**Phase 2 checkpoint — you're done with the minimum viable backend.** At this point, you
can:
1. Point `ingest_documents` at a folder of Markdown files (Phase 1), and
2. Call `hybrid_search`, expand to parents, and rerank (Phase 2)

...and get back a ranked, confidence-scored list of real, relevant text chunks for any
question — with nothing about LLMs, agents, or an API involved yet. That's the natural
next layer once this foundation is solid, but it's a separate concern built on top of,
not required to have, working ingestion and retrieval.
