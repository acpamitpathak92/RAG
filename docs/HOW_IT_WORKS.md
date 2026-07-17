# How It Works

A complete, plain-language walkthrough of everything the system does — first for a
question you ask, then for a document you add. Each step is explained in simple terms
first; the technical name for that step is given afterward, in case you want to look
it up or discuss it with someone else.

There are two independent flows:
- **Answering a question** — runs every single time you ask something.
- **Ingesting a document** — runs once per document, whenever you add, upload, edit, or reingest a file.

They're independent: you can ask questions against whatever is already ingested at any
time, and ingesting new documents doesn't interrupt or depend on anything happening in
the question-answering flow.

---

# Part 1 — What happens when you type a question

Say you type a slightly messy question and hit send. Here is exactly what happens,
in order, before an answer appears on screen.

### Step 1 — Your question is received

The app takes exactly what you typed, character for character, and hands it to the
backend as-is. Nothing has been touched yet at this point — this raw version is kept
around for the entire rest of the process, because it's shown back to you later for
comparison if anything gets corrected.

> **Technically, this is called:** the *original query*.

### Step 2 — Typos, grammar, and extra spaces get cleaned up

Before anything else happens, a small, fast AI model reads your question and fixes
purely mechanical problems: misspelled words, broken grammar, and double/extra spaces.
It is deliberately told **not** to change what you're actually asking — it can't add
information, remove information, or rephrase your question to sound different. If your
question was already clean, it's left completely untouched.

As an extra safety net, the system then compares the "corrected" version against what
you originally typed. If the two are too different from each other — a sign the fix
went too far and may have drifted away from your actual meaning — the correction is
thrown away and your original wording is used instead. This is a deliberate guardrail:
a spelling/grammar fix should never plausibly change what's being asked, so a big
difference is treated as something having gone wrong, not a legitimate improvement.

If a correction *was* accepted, both versions (yours and the corrected one) are
carried forward together, so the answer screen can later show you both and be
transparent about what was actually searched for.

> **Technically, this is called:** *Query Cleanup*, done by a dedicated **Query
> Cleanup Agent**, with a similarity check acting as a safety net against meaning drift.

### Step 3 — Your (cleaned) question is turned into a list of numbers

The cleaned-up question gets fed through the same small AI model that was used when
your documents were ingested (see Part 2). It converts the *meaning* of your question
into a list of a few hundred numbers — a "vector." Two questions that mean similar
things end up with similar-looking number lists, even if they're phrased completely
differently and share no exact words.

> **Technically, this is called:** *Query Embedding*.

### Step 4 — The knowledge base gets searched two different ways at once

**(a) Search by meaning.** The question's number-list from Step 3 is compared against
the number-list of every chunk of text that's ever been ingested, and the system pulls
out the ones that are mathematically closest — i.e., the ones that mean something
similar to your question, regardless of exact wording.

> **Technically, this is called:** *Dense Vector Search* (a nearest-neighbor search
> over embeddings).

**(b) Search by keyword, at the same time.** A completely separate, more old-fashioned
method looks for chunks that literally contain the same significant words as your
question. This catches sharp, exact-term matches (error codes, product names, specific
terminology) that a pure "meaning" search can sometimes blur past.

> **Technically, this is called:** *BM25 Lexical Search*.

**(c) The two result lists get merged fairly.** Rather than trusting one method over
the other, the system combines both ranked lists using a formula that rewards a chunk
for appearing near the top of *either* list. A chunk that only one of the two methods
found still gets a fair shot at being included, instead of being drowned out.

> **Technically, this is called:** *Reciprocal Rank Fusion (RRF)*.

### Step 5 — Full context is pulled back in around each match

The chunks matched so far are deliberately small (a paragraph or two), because small
pieces are easier to search precisely. But a small piece alone can lose surrounding
context. So for every matching small chunk, the system also fetches the *entire
section* of the original document it came from — not just the one paragraph that
matched, but the whole section around it — so nothing important gets lost right before
an answer gets written.

> **Technically, this is called:** *Parent Document Retrieval* (the small searched
> piece is the "child"; the full section it belongs to is the "parent").

### Step 6 — A slower, more careful pass re-ranks the candidates

Steps 4-5 are fast, but speed comes at the cost of precision — a merely-okay match can
occasionally rank ahead of a genuinely better one. So the system takes the merged
shortlist (often 20-30 candidates) and runs a second, much more careful pass: the AIaaS
chat model reads your actual question *side-by-side* with each candidate chunk in one
batched prompt (not just comparing number-lists anymore) and re-scores how well each one
truly answers what you asked. Only the very best few survive this pass.

> **Technically, this is called:** *LLM-Based Reranking* (an AIaaS chat-completion call,
> not a separately-hosted model).

At the end of this step, the system also computes a rough number summarizing "how
strong does this evidence look overall?" — this becomes an important ingredient in the
confidence score you'll see at the very end.

> **Technically, this is called:** *Retrieval Confidence Scoring*.

### Step 7 — A decision point: is there actually enough to go on?

Before spending any effort writing an answer, the system checks whether the surviving
evidence is strong enough to be worth answering from at all. This matters because if
the evidence is weak or basically irrelevant, an AI model asked to "answer anyway" will
often stretch and force a plausible-sounding response out of scraps — which can read as
confident even though it isn't actually well-supported.

- **If the evidence is too weak** (or there's no evidence at all), the system skips
  writing an answer altogether and immediately returns a short, honest message saying
  it couldn't find enough relevant information — along with a suggestion to rephrase
  the question or check that a relevant document has been ingested. Nothing is
  fabricated to fill the gap.
- **If the evidence looks strong enough,** the process continues to the next step.

> **Technically, this is called:** the *insufficient-evidence gate* (a conditional
> routing decision based on the retrieval confidence score from Step 6).

### Step 8 — An AI writes an answer, but only from what was found

The surviving evidence chunks (with their full parent-section context from Step 5) are
handed to a language model with strict instructions:
- Answer **using only this evidence** — no outside knowledge, nothing made up.
- Mark every factual sentence with a reference number like `[1]`, `[2]` pointing back
  to exactly which evidence chunk it came from.
- If the evidence doesn't fully answer the question, say so plainly instead of
  guessing.
- Format the answer for readability (short paragraphs, bullet points for
  multi-step information, bold for key terms) rather than one dense wall of text.

This model is deliberately given no other tools or outside access — it can only work
with the evidence it was handed, so it has no way to "invent" its way around missing
information.

> **Technically, this is called:** *Grounded Generation*, performed by the **Grounded
> Generation Agent**.

### Step 9 — Every citation marker gets independently verified

The system does not simply trust that the model's `[1]`, `[2]` reference numbers are
accurate. It goes back through the generated answer, finds every one of those markers,
and looks up — in its own records, not the model's word — exactly which chunk and which
source document each number really points to. This turns "the AI claims this came from
source 2" into "here is the exact, verifiable chunk and file that source 2 actually is,"
including a short preview of that chunk's real text and the document's real name.

> **Technically, this is called:** *Citation Mapping* (or *Citation Extraction*).

### Step 10 — An overall confidence score is calculated

The system combines how strong the retrieved evidence was (from Step 6) into a single
confidence number between 0 and 1. (In a future phase, this will also fold in a
claim-by-claim fact-check of the generated answer against its cited evidence; today it
is based primarily on retrieval strength.)

> **Technically, this is called:** *Confidence Scoring*.

### Step 11 — If confidence is low, you're told honestly

If that confidence number comes out low, the system doesn't quietly hand you a shaky
answer as if it were certain — it prepends a clearly visible warning to the response,
telling you the supporting evidence was incomplete or unclear, so you know to double
check rather than take the answer at face value.

> **Technically, this is called:** *Low-Confidence Caveat Surfacing*.

### Step 12 — Everything is packaged up and sent to your screen

The final answer text, the verified list of citations, the confidence score, and (if
Step 2 made a correction) both your original and corrected question text are all
bundled together and sent back to the chat window in one response.

> **Technically, this is called:** *Response Assembly*.

### Step 13 — The chat window displays everything clearly

- If your question was corrected in Step 2, a small note appears above the answer:
  *"Understood as: \<corrected version\>"* alongside what you originally typed — so
  nothing is silently reinterpreted behind your back.
- The answer itself is rendered with proper formatting (paragraphs, lists, bold text),
  not as one dense line of text.
- A **Copy** button sits at the top of the answer for quickly copying the response text.
- A confidence badge (green for confident, orange for low-confidence) sits below the
  answer.
- The citations are available in a collapsed "Citations (n)" section you can expand,
  each showing the source document's real name and a quoted snippet of the actual text
  it's based on.

---

# Part 2 — What happens when you ingest a document

This runs once for each document, whenever you add a new file, upload a PDF, edit an
existing markdown document, or explicitly click "reingest." Here is exactly what
happens, in order, for one document.

### Step 1 — The file is located and its raw content is read

The system opens the file — either a Markdown (`.md`) file or a PDF — from wherever it
lives (your knowledge folder, or a freshly uploaded file) and reads its raw content.

### Step 2 — The system checks: "have I seen this exact content before?"

Before doing any real work, the system fingerprints the document's full content and
compares it against what it already has on record for this same document.
- If the fingerprint is identical to last time, ingestion stops right here — nothing
  is reprocessed, and no time is wasted.
- If it's different (a new document, or an edited one), processing continues below.

> **Technically, this is called:** *content-hash based Deduplication/Versioning*
> (an unchanged document is *skipped*; a changed one gets a new *version number* and
> its outdated pieces are cleaned up automatically once reprocessing finishes).

### Step 3 — The file is parsed into structured text

The raw file gets turned into clean, structured pieces:
- For Markdown, this means recognizing headings (so section boundaries are known),
  pulling out any front-matter header info (like a title or tags written at the very
  top of the file), and identifying links to other documents.
- For PDF, this means extracting the actual text content page by page.

> **Technically, this is called:** *Document Parsing*.

### Step 4 — The text gets tidied up

Stray control characters, inconsistent blank lines, and trailing whitespace are
stripped out, leaving clean, consistent text. This matters because messy raw text can
confuse later steps, especially the meaning-based splitting in Step 6.

> **Technically, this is called:** *Text Cleaning*.

### Step 5 — Useful facts about the document are recorded

Information like which file this came from, its title, any tags, which connector
ingested it (Markdown vs. PDF), and when it was ingested all get recorded and attached
to the document, so it can be filtered, searched, and correctly labeled later
(including showing a real, human-readable document name in citations, rather than an
internal ID).

> **Technically, this is called:** *Metadata Extraction*.

### Step 6 — The document is split into a two-level structure

First, each natural section of the document (for Markdown, each heading's section; for
PDF, each page) is kept as one complete "parent" piece, word-for-word — this is what
eventually gets shown to you as full context around a match.

Then, within each section, the system looks at where the *meaning* naturally shifts
from one idea to the next — not just "every 300 words" mechanically, but where the
actual topic changes — and splits there into smaller "child" pieces. These smaller
pieces are what actually get searched and matched against your questions.

> **Technically, this is called:** *Parent-Child Chunking*, with the child-level split
> points chosen via *Semantic Chunking*.

### Step 7 — A little of each piece is repeated into the next one

So that a small chunk sitting right at a topic-boundary doesn't lose context, the tail
end of one child piece is copied onto the beginning of the next one. This way, a search
match near a boundary still carries a bit of the preceding context with it.

> **Technically, this is called:** *Chunk Overlap*.

### Step 8 — Each small piece is turned into a list of numbers

The same small AI model used for questions (see Part 1, Step 3) reads each child piece
and converts its *meaning* into a list of numbers — a vector. Pieces about similar
topics end up with similar-looking number lists, even if they use completely different
words to say it.

> **Technically, this is called:** *Embedding Generation*.

To avoid unnecessary repeated work, previously-computed number-lists for identical text
are reused rather than recalculated from scratch every time.

> **Technically, this is called:** an *embedding cache*.

### Step 9 — Everything is saved locally

The full parent-section text, the smaller searchable child pieces, their metadata, and
their number-lists all get saved into one local database file on your machine — nothing
is sent to or stored in any external database or cloud service as part of this step.

> **Technically, this is called:** *Vector Indexing* (via a local SQLite database with
> vector-search support built in).

**Ingestion is now complete.** The document — and every piece of it — is immediately
searchable the next time anyone asks a question.

### A note on "reingest"

If you edit a document's underlying file outside the app (or upload a replacement),
clicking "reingest" simply re-runs this entire process (Steps 1-9) against whatever is
currently on disk for that document. If nothing actually changed, Step 2 catches that
and nothing is reprocessed; if it did change, a new version is created and the old,
now-outdated pieces are automatically cleaned up.

---

# The whole system, at a glance

```
ASKING A QUESTION (every time):
  you type a question
    -> typos/grammar cleaned up (with a safety check against meaning drift)
    -> question converted to a number-list
    -> searched by meaning AND by keyword, at the same time
    -> the two result lists merged fairly
    -> full surrounding context pulled back in for each match
    -> candidates carefully re-ranked
    -> confidence checked: is there enough evidence to bother answering?
         -- not enough --> honest "couldn't find enough evidence" message, no guessing
         -- enough      --> an answer is written using ONLY that evidence, with citations
                             -> every citation verified against real chunks
                             -> overall confidence scored
                             -> a warning added if confidence is low
    -> everything (answer, citations, confidence, any question correction) sent to your screen

INGESTING A DOCUMENT (once per document):
  file is read
    -> checked against what's already stored (skip if unchanged)
    -> parsed into structured text
    -> cleaned up
    -> useful facts about it recorded
    -> split into full sections ("parent") and smaller searchable pieces ("child")
    -> a bit of overlap added between neighboring pieces
    -> each small piece converted to a number-list
    -> everything saved locally
```

All of this runs as one connected, automatic process each time — nothing here is a
manual step, and no step is ever skipped. The only data that leaves your machine at
all is the actual question text and evidence chunks sent to whichever language model
provider you've configured — nothing else.
