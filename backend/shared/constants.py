"""Single home for magic numbers/strings shared across the ingestion and query pipelines.

Values that are genuinely local to one algorithm (e.g. a regex used by exactly one parser)
stay next to that code. Anything that multiple modules need to agree on, or that a reader
would otherwise have to hunt for across files, lives here instead.
"""

# --- Filesystem conventions -------------------------------------------------

KNOWLEDGE_SOURCE_DIR_NAME = "knowledge_source"  # default folder the API/UI ingest from
DEFAULT_DB_PATH = "data/rag.db"  # default local SQLite + sqlite-vec database file
EMBEDDING_CACHE_SUFFIX = "_embedding_cache"  # appended to the db filename for the embedding cache's own SQLite file
README_FILENAME = "readme.md"  # excluded from ingestion - folder instructions, not knowledge-base content

# --- Query: citations / responses ------------------------------------------

CITATION_SNIPPET_MAX_CHARS = 240  # length of the end-user-facing text preview shown per citation

LOW_CONFIDENCE_PREFIX = "⚠️ Low confidence answer - supporting evidence was incomplete or unclear.\n\n"

GENERIC_INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I couldn't find enough relevant information in the knowledge base to answer this "
    "question confidently. Try rephrasing your question, or make sure a document covering "
    "this topic has been ingested into the knowledge base."
)

# QueryCleanupAgent safety net: if the "cleaned" query is this dissimilar (difflib
# SequenceMatcher ratio, case-insensitive) from the original, the correction is rejected
# and the original is used instead - a typo/grammar fix should never drift this far from
# what was actually asked. 0.55 tolerates full spelling fixes on short questions while
# still catching a rewrite that changes substance.
QUERY_CORRECTION_MIN_SIMILARITY = 0.55
