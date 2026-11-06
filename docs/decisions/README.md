# Architecture Decision Records

Format: Context → Decision → Consequences → Status. ADRs are written when the decision is actually
made (with evidence), not as empty placeholders.

| ADR | Title | Status | Milestone |
|---|---|---|---|
| [ADR-000](ADR-000-specification-priority.md) | Specification priority rules & recorded spec gaps | Accepted | M0 |
| [ADR-001](ADR-001-local-model-runtime.md) | Local-first model runtime (Ollama, qwen3:4b) | Accepted; digests recorded at M3 | M0/M4 |
| [ADR-002](ADR-002-embedding-model.md) | Embedding model, versions, vector storage | Accepted | M3 |
| ADR-003 | PostgreSQL + pgvector + FTS | Planned | M3/M5 |
| ADR-004 | RRF and reranking | Planned – needs measured results | M5 |
| [ADR-005](ADR-005-chunking-strategy.md) | Chunking strategy (fixed + recursive) | Accepted; default revisited at M5 | M2 |
| ADR-006 | Text-to-SQL safety | Planned | M6 |
| [ADR-007](ADR-007-local-only-cost-boundary.md) | Local-only cost boundary | Accepted | M0 |
| [ADR-008](ADR-008-native-postgres-dev-runtime.md) | Native PostgreSQL via conda on the dev machine | Accepted | M0 |
