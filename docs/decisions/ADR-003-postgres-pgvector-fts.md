# ADR-003: One PostgreSQL store for metadata, vectors and full-text search

- Status: Accepted (M2/M3/M5)
- Milestone: M2–M5

## Context

TRD §3 picks PostgreSQL 16 + pgvector + PostgreSQL FTS so that a solo, local install has one
system of record and no extra search service. The reference machine has 7.3 GB of RAM, so every
extra resident service competes with the local LLM.

## Decision

- **Vectors**: `chunk_embeddings.embedding` is an untyped pgvector `vector`, filtered by the
  active `embedding_version_id` (ADR-002). Search is exact cosine distance (`<=>`) with no ANN
  index. That's the TRD baseline, and at the measured scale (5–10 documents, under 100 chunks
  per strategy) dense retrieval takes about 40 ms p50, almost all of it embedding the question.
  HNSW gets added only when a benchmark shows exact search is too slow; it needs a typed
  `vector(D)` column per embedding version.
- **Lexical**: `chunks.search_tsv` is a stored generated column
  `to_tsvector('english', section_path || ' ' || text)` with a GIN index. Queries OR the stemmed
  terms from `plainto_tsquery` and rank with `ts_rank_cd(…, 32)`.
  - Measured reason for OR: `websearch_to_tsquery` / `plainto_tsquery` AND every term, and
    "How much can I spend on a hotel per night?" matched **0** chunks. With OR it matched 6.
- **Scoping**: every retrieval query filters by `workspace_id` on both the chunk and its
  document, and only `ready` documents are searchable (integration-tested).

## Consequences

- One backup and one migration history cover all data.
- English stemming only. Other languages need a different text-search configuration.
- `ts_rank_cd` isn't BM25. On the small sample corpus lexical retrieval still scored very well
  (see docs/evaluation/README.md); larger corpora may need tuning.
