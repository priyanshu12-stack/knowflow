# ADR-000: Specification priority rules and recorded specification gaps

- Status: Accepted (2026-11-06)
- Milestone: M0

## Context

All three specifications say: "If two documents appear to conflict, use the priority rules in the PRD
and record the resolution in docs/decisions/". A complete read of the PRD found **no section that
defines priority rules**. That is a specification gap, not a conflict.

## Decision

Pending an explicit rule from the project owner, the following precedence applies. It is derived from
the roles the owner assigned to each document:

1. **Safety, privacy and the zero-paid-API constraint** (TRD §1, §11; PRD §2, §9) override everything else.
2. **TRD** decides *how* the system works technically: stack, data model, API contract, security controls.
3. **PRD** decides *what* gets built and *when*: scope, P0/P1/P2 priority, milestone order, acceptance tests.
4. **DRD** decides *how it looks and behaves*: tokens, layout, states, accessibility.
5. When a lower-priority document is **more specific** and doesn't contradict a higher one, implement both.

Any change to a major architectural decision still requires asking the owner first.

## Recorded overlaps and how they're reconciled

| # | Topic | Documents | Resolution |
|---|---|---|---|
| G-1 | Document status vocabulary | PRD §5.2 lists `queued, extracting, chunking, embedding, ready, failed`; TRD §8 lists job states `queued/running/succeeded/failed` + "progress stage" | `documents.status` uses the PRD vocabulary (what the user sees). `ingestion_jobs.status` uses the TRD vocabulary, and `ingestion_jobs.stage` carries `extracting/chunking/embedding`. Both are kept consistent in one transaction. |
| G-2 | Embedding versioning | TRD §7 `chunks` has `embedding vector(D)` and `Unique(..., version)`; TRD §17 requires "persisted with an embedding version" but no table is defined | Add an `embedding_versions` table (model tag, digest, dimension) at M3; chunks reference it. Recorded in ADR-002. |
| G-3 | Feedback / query metrics storage | PRD §5.3 requires stored feedback; TRD §3 a "local metrics table"; neither appears in TRD §7 | `message_feedback` table (M4). Per-answer metrics (latency per stage, model, prompt version, candidate ranks, token counts) are stored in `messages.metadata` instead of a separate `query_metrics` table, because every answer is already a row and nothing queries the metrics independently yet. Revisit if the Activity page (M7) needs aggregates that are slow to compute. |
| G-4 | SQL secret storage | TRD §7 `encrypted_secret_ref`; no key-management design | Decide at M6 (ADR-006). The default proposal is that the secret stays in an environment variable and only its name is stored. |
| G-5 | Docker Compose vs this dev machine | TRD §3, §13 expect Docker Compose; the dev machine has no Docker and 7.3 GB RAM | Owner chose native PostgreSQL via conda for local dev; compose still ships (ADR-008). |
| G-6 | Makefile on Windows | TRD §14 lists a Makefile; `make` isn't installed on the dev machine | Ship a Makefile (POSIX/CI) **and** `scripts/*.ps1` with the same targets. |
| G-7 | Navigation to future pages | DRD §6.1 lists all nav items; DRD §15 says "no dead buttons" | Nav items for pages that aren't built yet render **disabled with an explanation** (DRD §13 "Disabled" state) until their milestone ships. |
| G-8 | RAG clarification (`POST /chat/clarify`) | TRD §6.2 says "classify query only when needed … clarification needed" and §8 lists `/chat/clarify`; PRD §5.3 and the DRD describe clarification only for SQL (PRD §5.5, DRD §7.4) | v1 RAG answers or abstains with a suggestion to narrow the question (PRD §6 Journey A). It doesn't run an extra classifier call, which would add tens of seconds of CPU per question on the reference machine. Structured clarification is built for SQL (M6), where the specs require it. `/chat/clarify` is not exposed. |
| G-9 | Evaluation labels vs chunk ids | TRD §7 `evaluation_cases.expected_chunk_ids`; chunk ids are regenerated on every re-index (ADR-005) | Cases store `expected_chunk_ids` **and** stable evidence matchers (document name + page and/or an exact quote). A retrieved chunk is relevant when it matches a matcher, so labels survive re-indexing and apply to both chunking strategies (M5, ADR-004). |
