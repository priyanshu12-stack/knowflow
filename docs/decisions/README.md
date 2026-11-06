# Architecture Decision Records

Format: Context → Decision → Consequences → Status. ADRs are written when the decision is actually
made (with evidence), not as empty placeholders.

| ADR | Title | Status | Milestone |
|---|---|---|---|
| [ADR-000](ADR-000-specification-priority.md) | Specification priority rules & recorded spec gaps | Accepted | M0 |
| [ADR-001](ADR-001-local-model-runtime.md) | Local-first model runtime (Ollama, qwen3:4b) | Accepted; digests recorded at M3 | M0/M4 |
| [ADR-002](ADR-002-embedding-model.md) | Embedding model, versions, vector storage | Accepted | M3 |
| [ADR-003](ADR-003-postgres-pgvector-fts.md) | PostgreSQL + pgvector + FTS (OR-of-terms) | Accepted | M2–M5 |
| [ADR-004](ADR-004-rrf-and-reranking.md) | RRF hybrid; reranker optional, not measured | Accepted (small-sample evidence) | M5 |
| [ADR-005](ADR-005-chunking-strategy.md) | Chunking strategy (fixed + recursive) | Accepted; default revisited at M5 | M2 |
| [ADR-006](ADR-006-text-to-sql-safety.md) | Text-to-SQL safety, clarification, secrets | Accepted | M6 |
| [ADR-007](ADR-007-local-only-cost-boundary.md) | Local-only cost boundary | Accepted | M0 |
| [ADR-008](ADR-008-native-postgres-dev-runtime.md) | Native PostgreSQL via conda on the dev machine | Accepted | M0 |
