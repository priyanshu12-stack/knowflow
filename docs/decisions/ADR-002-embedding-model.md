# ADR-002: Embedding model, versions and vector storage

- Status: Accepted (M3). Quality comparison against alternatives is deferred to the M5 gold set.
- Milestone: M3

## Context

TRD §4.2 / §7: the embedding dimension must be measured, never assumed; changing the model needs
full re-embedding; vectors from different model spaces must never be mixed.

## Decision

- Default model `nomic-embed-text:v1.5` via Ollama (`/api/embed`, `truncate: true`). Its measured
  dimension on this machine is **768** and its context is 2048 tokens. Chunks are about 300
  tokens (ADR-005), well inside that.
- Nomic task prefixes are applied: `search_document: ` for chunks and `search_query: ` for
  queries. The section path is prepended to the chunk text so headings contribute to meaning.
- `embedding_versions` records (model, digest, measured dimension, prefixes). Exactly one is
  active, enforced by a partial unique index. The first embedding run, or saving a new model in
  Settings, probes the model and activates a version.
- Vectors live in `chunk_embeddings(chunk_id, embedding_version_id, workspace_id, embedding vector)`
  with an **untyped** `vector` column. That lets a new dimension coexist with the old one
  until re-indexing finishes, without a schema migration. Retrieval always filters on the active
  version.
- Search is exact cosine (`<=>`). No HNSW index: it would need a fixed-dimension column, and exact
  search is the TRD baseline until latency is measured at real scale.
- Changing the embedding model in Settings shows a warning, activates the new version, and reports how many
  documents need re-indexing. `POST /settings/reindex` queues them.

## Consequences

- Each document is embedded twice (fixed + recursive chunks). On this CPU that's about 1–2 s for
  a small document, and it's measured in the M5 evaluation report.
- Old-version vectors stay until their documents are re-indexed (the chunks are replaced, which cascades).
- An HNSW index can be added later with a typed column, per version, if latency requires it.
