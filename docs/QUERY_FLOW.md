# What Happens When You Ask a Question

This walks through everything that happens, in order, from the moment you type a
question into the chat box to the moment an answer appears — no code, just the
concepts, in the order they actually run. At the end of each stage you'll see a
line like:

> **This stage is called:** _Something Technical_

so you know what to call it if you read the architecture plan or hear these terms
elsewhere.

We'll follow one real question the whole way through:

> **"why are billing service pods getting killed after a deploy?"**

---

## Stage 1 — Your question gets turned into "meaning numbers"

The moment you hit send, the system doesn't start searching for the words "billing,"
"pods," "killed," "deploy" right away. First, it feeds your entire question through
a small AI model whose only job is to read text and represent *what it means* as a
list of a few hundred numbers.

Why numbers instead of words? Because two sentences that mean the same thing but
use completely different words ("pods getting killed" vs. "containers crashing")
end up with very similar number-lists, even though they don't share a single word.
That's what lets the next stage find relevant answers even when you don't phrase
your question the same way the original document did.

> **This stage is called:** _Query Embedding_.

---

## Stage 2 — The knowledge base gets searched two different ways at once

Now the system goes looking through everything that's been ingested into the
knowledge base, using **two separate strategies at the same time**, because each
one catches things the other misses:

- **Strategy A — search by meaning.** The question's number-list from Stage 1 gets
  compared against the number-list of every stored chunk of knowledge, and the
  system pulls out the ones that are mathematically "closest" — i.e. the ones that
  mean something similar, regardless of exact wording.

- **Strategy B — search by keyword.** At the same time, a completely different,
  much older-school method just looks for chunks that literally contain matching
  words ("billing," "pods," "deploy," etc.). This catches sharp, exact-term matches
  that a "meaning" search can sometimes blur past.

> **This stage is called:** _Hybrid Retrieval_ — specifically, _Dense Vector Search_
> for Strategy A and _Lexical (BM25) Search_ for Strategy B.

---

## Stage 3 — The two search results get merged into one fair ranking

Strategy A and Strategy B each come back with their own ranked list of candidate
chunks. Rather than trusting one list over the other, the system combines them
using a formula that rewards a chunk for showing up near the top of *either* list —
so a chunk that only one method scored well still gets a fair shot, instead of
being drowned out.

> **This stage is called:** _Reciprocal Rank Fusion_ (a way of merging multiple
> ranked lists into a single consensus ranking).

---

## Stage 4 — Each match gets its surrounding context pulled back in

The chunks found so far are deliberately small (a paragraph or two), because small
chunks are easier to search precisely. But small chunks alone can lose context. So
for every matching small chunk, the system also fetches the *full section* of the
original document it came from — e.g. the entire "Root Cause" section, not just the
one sentence that matched — so nothing important gets lost right before the answer
gets written.

> **This stage is called:** _Parent Document Retrieval_.

---

## Stage 5 — A slower, smarter pass double-checks the best candidates

Steps 2-4 are fast, but "fast" search can be a little rough — it might rank a
so-so match slightly ahead of a genuinely better one. So the system takes the
merged shortlist (maybe 20-30 candidates) and runs a *second*, much more careful
pass: the AIaaS chat model reads your actual question **side-by-side** with each
candidate chunk in one batched prompt (not just comparing number-lists anymore) and
re-scores how well each one truly answers what you asked. Only the very best few
survive this pass.

> **This stage is called:** _LLM-Based Reranking_ (an AIaaS chat-completion call, not
> a separately-hosted model).

At the end of this stage, the system also quietly computes a rough number
representing "how strong does this evidence look overall?" — this becomes one
ingredient in the confidence score you'll see at the very end.

> **This stage is called:** _Retrieval Confidence Scoring_.

---

## Stage 6 — An AI writes an answer, but only from what was actually found

Now, and only now, does the system hand things off to a language model to actually
write a response. Crucially, it isn't given free rein — it's handed *only* the
handful of evidence chunks that survived Stage 5, along with a strict instruction:
**answer using only this evidence, and mark every single factual sentence with a
reference number pointing back to exactly which chunk it came from.** It's
explicitly told that if the evidence doesn't fully answer the question, it should
say so honestly rather than filling the gap with a guess.

For our example question, this stage is what produces something like: *"The
billing service pods are getting killed after a deploy because they exceed the
Postgres connection limit [2]. Each pod opens its own connection pool sized at 20
connections [1], and during a rollout with `maxSurge: 50%`, up to 6 pods can run at
once — 120 connections total [2] — which exceeds the configured limit of 100 [2]."*

> **This stage is called:** _Grounded Generation_ — "grounded" meaning the answer is
> tied down to real evidence rather than drawn from the model's general training
> knowledge.

---

## Stage 7 — Every reference number gets independently verified

The system does **not** simply trust that the reference numbers the model just
wrote are accurate. It goes back through the answer text, finds every `[1]`, `[2]`,
etc., and looks up — in its own records, not the model's word — exactly which
chunk and which source document each number is really pointing to. This is what
turns "the AI claims this came from source 2" into "here is the exact, verifiable
chunk and file that source 2 actually is."

> **This stage is called:** _Citation Mapping_ (or _Citation Extraction_).

---

## Stage 8 — The system decides how much to trust its own answer

All the signals gathered so far — how strong the evidence looked (Stage 5), and (in
a more advanced mode not yet switched on) how well the model's individual claims
held up when checked against the evidence — get combined into one single
confidence number between 0 and 1.

> **This stage is called:** _Confidence Scoring_.

---

## Stage 9 — If the system isn't confident, it says so instead of guessing

If that confidence number comes out low — for example, if you'd asked something the
knowledge base barely covers, like a topic no ingested document ever discusses —
the system doesn't quietly hand you a shaky answer as if it were certain. It
attaches a visible warning to the top of the response, telling you the evidence was
thin or unclear, so you know to double check rather than take the answer at face
value.

> **This stage is called:** _Low-Confidence Caveat Surfacing_.

---

## Stage 10 — Everything gets packaged up and shown to you

Finally, the written answer, the verified list of citations (each pointing to a
real document you can go check yourself), and the confidence score all get bundled
together and sent back to the chat window — which is exactly what renders as the
answer bubble, the small confidence badge, and the collapsible "Citations" section
you can expand.

> **This stage is called:** _Response Assembly_.

---

## The whole trip, start to finish

```
Type a question
   -> turn the question into meaning-numbers                 (Query Embedding)
   -> search by meaning AND by keyword, at the same time      (Hybrid Retrieval)
   -> merge both result lists fairly                          (Reciprocal Rank Fusion)
   -> pull back full context around each match                (Parent Document Retrieval)
   -> carefully re-rank the shortlist                         (LLM-Based Reranking)
   -> write an answer using ONLY that evidence, with citations (Grounded Generation)
   -> verify every citation points to a real chunk             (Citation Mapping)
   -> score how confident to be overall                        (Confidence Scoring)
   -> add an honest warning if unsure                          (Low-Confidence Caveat)
   -> package it all up and show it to you                     (Response Assembly)
```

All of this — every stage above — runs as one connected, automatic pipeline each
time you hit send. Nothing is manual, and nothing skips a step.
