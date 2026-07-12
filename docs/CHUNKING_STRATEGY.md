# Chunking Strategy

Everything about how documents get split into pieces before they're searchable —
what gets split, how, why, in what order, and how the pieces relate to each other
afterward. This only covers the *chunking* stage; see `docs/HOW_IT_WORKS.md` for where
it fits into the full ingestion pipeline.

---

## The core idea: two levels, not one

Most simple RAG systems split a document into fixed-size blocks (e.g. "every 300
words") and search those blocks directly. This system does something different: **every
document is split into two levels at once** — a small number of large **parent**
pieces, and many small **child** pieces nested inside them.

- **Child chunks** are what actually get embedded and searched. They're small on
  purpose, because small, focused pieces of text match a specific question more
  precisely than a large, topic-spanning one.
- **Parent chunks** are the full section a child chunk came from. They're never
  embedded or searched directly — they exist purely to be pulled back in *after* a
  child chunk is found, so the system (and the answer-writing model) gets full
  surrounding context instead of an isolated, out-of-context fragment.

This is why the strategy is called **Parent-Child Chunking**. Searching small and
reading large is the whole point: precision on the way in, context on the way out.

---

## Step 0: where a "parent" comes from in the first place

Before any chunking logic runs, every document is already broken into **sections** by
its format-specific parser — this is the seed structure that parent chunks are built
from. Chunking doesn't invent section boundaries; it inherits them.

- **Markdown documents**: a section is everything between one heading (`##`, `###`,
  etc.) and the next. The parser walks the document's heading structure and slices the
  raw text accordingly. A document with five `##` headings produces five sections. If a
  Markdown file has no headings at all, the whole document is treated as one single
  section.
- **PDF documents**: PDFs don't have reliable heading markup to parse, so each **page**
  is treated as one section instead. A 10-page PDF produces 10 sections, one per page.

Each section is handed forward as a `(heading_level, heading_text, body_text)` triple
(for PDFs, `heading_text` is just `"Page N"`). This is the raw material parent-child
chunking works with — one parent chunk will be created per section, no more, no fewer.

---

## Step 1: building the parent chunk

For every section, exactly one **parent chunk** is created, holding that section's
*entire* body text, completely unmodified and unsplit (aside from the text-cleaning
pass that already ran before chunking — stripped control characters, collapsed blank
lines). A parent chunk also carries the section's heading and heading level as metadata.

Parent chunks are stored in the database but are **never embedded** — there's no vector
attached to a parent chunk at all. They exist solely to be looked up by ID later, when a
child chunk beneath them gets matched by a search.

If a section's body is empty after cleaning (e.g. a heading with nothing under it), no
parent chunk is created for it at all — there'd be nothing useful to chunk or retrieve.

---

## Step 2: splitting each parent into child chunks — Semantic Chunking

This is the most involved part of the whole strategy. Within each section/parent, the
text needs to be broken into several smaller, independently-searchable child pieces.
The naive approach — split every N words regardless of content — was deliberately
rejected, because a fixed-size cut can land in the middle of a coherent idea just as
easily as at a natural boundary, which hurts search precision. Instead, splits are
chosen based on where the *meaning* actually shifts from one idea to the next.

### How a "meaning shift" is actually detected

1. The section's text is split into **individual sentences** first (a sentence-boundary
   pattern recognizing `.`, `!`, `?` followed by a capital letter or number, plus blank
   lines as paragraph breaks).
2. **Every single sentence gets its own embedding** — yes, the same embedding process
   used for full chunks, just run once per sentence within this section.
3. For every pair of *adjacent* sentences, their cosine similarity is computed — a
   number roughly between 0 and 1 saying how closely related sentence *i* and sentence
   *i+1* are in meaning.
4. All of these adjacent-pair similarity scores across the whole section are collected,
   and the bottom **25th percentile** (the lowest quarter) of them are marked as
   **candidate breakpoints** — i.e., "in this section, these are the biggest topic
   shifts between two consecutive sentences."

### How sentences actually get grouped into chunks

Sentences are then walked through in order, accumulating into a "current chunk," with
two rules governing when to cut:

- A cut is **allowed** at a candidate breakpoint only once the current chunk has
  already reached a **minimum size** — by default, **200 words**. This stops the system
  from creating a string of tiny, useless one-sentence chunks just because two adjacent
  sentences happen to look topically different.
- A cut is **forced**, regardless of whether it's a candidate breakpoint or not, once
  the current chunk reaches a **maximum size** — by default, **400 words**. This is a
  hard ceiling so no single child chunk ever grows unreasonably large, even if a
  section stays thematically consistent for a very long stretch.

In short: a chunk keeps growing, sentence by sentence, until either (a) it's grown past
400 words, at which point it's cut no matter what, or (b) it's grown past 200 words
*and* the next sentence boundary looks like a genuine topic shift — whichever comes
first.

A section with only one sentence (or none at all) skips this process entirely and
becomes a single child chunk on its own.

> **Word count vs. tokens:** the "200/400" bounds are measured in plain whitespace-split
> words, used as a fast, dependency-free stand-in for a true token count. It's an
> approximation, not an exact tokenizer count, but it's consistent and cheap to compute
> for every sentence.

---

## Step 3: Chunk Overlap

Even with meaning-aware splits, a search hit that lands right at the very start of a
child chunk can still feel like it's missing a sentence or two of lead-in context from
whatever came immediately before it. To soften this, a small amount of **overlap** is
added between consecutive child chunks within the same section:

- For every child chunk *after* the first one in a section, the **trailing 18%** of the
  *previous* chunk (by word count) is copied and prepended onto the start of this one.
- The first child chunk in a section never gets anything prepended (there's nothing
  before it to borrow from).
- If a section only produced one child chunk total, no overlap logic runs at all —
  there's nothing to overlap with.

This means consecutive child chunks share a small amount of duplicated text at their
boundary on purpose. That duplication is a deliberate, small tradeoff (slightly more
storage, slightly more embedding work) in exchange for a chunk never starting completely
cold with zero lead-in context.

---

## Step 4: IDs, storage, and versioning

Every parent and child chunk gets a **deterministic ID** — a hash built from the
document's ID, whether it's a `"parent"` or `"child"`, and its position/index. This
matters for re-ingestion: if you edit a document and re-ingest it, chunks in the same
position get the *same* IDs as before and are simply overwritten in place, rather than
creating brand-new duplicate rows every time you save. Chunks are also tagged with the
document's current *version number*; if re-chunking a shrunk document leaves some old
chunk IDs orphaned (positions that no longer exist in the new version), those get swept
away automatically as part of ingestion.

Chunks are stored in one shared table, distinguished by a `chunk_type` column of either
`"parent"` or `"child"`. A child chunk row also stores the ID of the parent it belongs
to, so the two levels can always be reconnected later. Only child chunks ever have a
vector attached — parent chunks intentionally have no embedding at all.

---

## How the two levels get used again at query time

This is the payoff for splitting things this way in the first place:

1. When a question comes in, **only child chunks** are ever searched (both the
   vector/meaning search and the keyword search operate exclusively over child-level
   text) — this is where the precision benefit of small chunks comes in.
2. For every child chunk that comes back as a match, the system separately looks up its
   **parent chunk's full text** by the stored parent ID and attaches it alongside the
   child hit.
3. From that point on, both are carried together: the small child chunk (precise,
   exactly what matched, and what gets cited back to you with an exact snippet) and its
   full parent section (used to give the answer-writing model complete surrounding
   context, not just an isolated fragment).

So a citation you see always points to the precise child chunk that actually matched —
but the model that wrote the answer had the benefit of reading the whole section around
it, not just that one small piece.

---

## Configuration — what's tunable, and where

All of the numeric knobs described above live in one place (`retrieval_config.yaml`,
under a `chunk:` section) rather than being hardcoded, so they can be tuned without
touching any chunking code:

| Setting | Default | What it controls |
|---|---|---|
| `child_min_tokens` | 200 words | The minimum size a child chunk must reach before a detected topic-shift is allowed to end it. |
| `child_max_tokens` | 400 words | The hard ceiling — a child chunk is force-cut here regardless of topic coherence. |
| `overlap_ratio` | 0.18 (18%) | How much of the previous child chunk's tail gets prepended onto the next one. |

The breakpoint sensitivity (currently fixed at the bottom 25th percentile of
sentence-to-sentence similarity drops) is not currently exposed as a config value — it's
a constant inside the semantic-splitting logic itself, on the reasoning that it's more
of an algorithm-tuning parameter than an operational one you'd want to change per
deployment.

---

## Why this design, specifically

- **Semantic over fixed-size**: issue/troubleshooting documents (bug reports, runbooks)
  have naturally uneven section lengths — a "Symptom" section might be two sentences,
  a "Resolution" section might be a numbered list of ten steps. Fixed-size chunking
  would cut through the middle of these unevenly and unpredictably; splitting where
  meaning actually shifts respects the document's real structure instead.
- **Parent-child over single-level**: searching small chunks is more precise (less
  topic-dilution per chunk means embeddings represent one idea, not several blended
  together), but *reading* small chunks in isolation loses context a human — or an
  answer-writing model — would want. Keeping both levels linked gets the precision of
  the former without sacrificing the completeness of the latter.
- **Overlap as a cheap insurance policy**: an 18% overlap is a small, bounded storage
  cost that meaningfully reduces the chance that a match "starts mid-thought" right at
  a semantic boundary the splitter chose.
- **Deterministic IDs over random ones**: re-ingesting an edited document should update
  what changed, not silently pile up duplicate stale copies of what didn't.

---

## A worked example

Take a Markdown document with one `## Root Cause` section containing five sentences:
two sentences about *what* broke, then a clear pivot to *why* it broke, continuing for
three more sentences — roughly 350 words total.

1. **Parsing** produces one section: `(level=2, heading="Root Cause", body=<the five sentences>)`.
2. **One parent chunk** is created holding all ~350 words, unsplit.
3. **Semantic chunking** embeds each of the five sentences individually, finds that the
   similarity between sentence 2 and sentence 3 is unusually low (a real topic pivot),
   and — since the accumulated word count by sentence 2 is already comfortably past the
   200-word minimum — cuts there. Two child chunks result: sentences 1-2 (~140 words)
   and sentences 3-5 (~210 words). Neither exceeds the 400-word ceiling, so no forced
   cut was needed.
4. **Overlap** copies the trailing ~18% of chunk 1 (about the last 25 words) onto the
   front of chunk 2.
5. Both child chunks get embedded and stored, each linked back to the same one parent
   chunk (the full "Root Cause" section).
6. Later, if a question matches specifically on the *why it broke* content, the second
   child chunk is what's found and cited — but the full "Root Cause" section (both the
   *what* and the *why*) is what gets handed to the model writing the answer.
