# Architecture Overview

Source of truth: [TRD §5](../TRD.md). This page documents what is **implemented** (v1.0.0-rc.1);
the TRD documents the target. Decisions and their evidence are in the [ADRs](../decisions/README.md).

## Logical architecture (target, TRD §5)

```text
Browser (Next.js App Router, TypeScript)
   │  same-origin: Next.js rewrites /api/v1/* → FastAPI (no CORS in prod)
   ▼
FastAPI (apps/api) ── one codebase, clear modules ── one DB-backed worker process
   ├─ api/v1 routers ── schemas (Pydantic v2) ── core (config, logging, errors)
   ├─ modules/documents  → extraction → chunking → embeddings
   ├─ modules/retrieval  → dense (pgvector) + lexical (FTS) → RRF → optional rerank
   ├─ modules/rag        → context packing → Qwen3 via Ollama → validation → citations
   ├─ modules/sql_assistant → allowlisted schema → clarify → generate → SQLGlot → read-only exec
   └─ modules/evaluation → datasets → runs → metrics
   │
   ├──► PostgreSQL 16 + pgvector (system of record, vectors, FTS, jobs, eval, audit)
   └──► Ollama on host (qwen3:4b generation, nomic-embed-text embeddings)
```

## Implemented (M1–M7)

| Concern | Implementation |
|---|---|
| Processes | `uvicorn app.main:app` (API) and `python -m app.workers.ingestion` (one worker: ingestion jobs first, then evaluation runs, both claimed with `FOR UPDATE SKIP LOCKED`) |
| Data | 7 Alembic migrations: workspaces, documents, ingestion_jobs, document_sections, chunks (generated `tsvector` + GIN), worker_heartbeats, embedding_versions, chunk_embeddings (untyped `vector`), model_settings, conversations, messages, message_feedback, evaluation_{datasets,cases,runs,results}, sql_connections, sql_glossary_terms, sql_queries, audit_events |
| Ingestion | validation → streamed SHA-256 + size cap → generated storage key → worker: extraction in a killable child process → fixed + recursive chunks → batched nomic embeddings (task prefixes, heading context) → one transaction writes sections, chunks and vectors and marks the document ready. Retries back off; stale jobs are recovered |
| Retrieval | dense: exact cosine in the active embedding version · lexical: OR-of-terms FTS + `ts_rank_cd` · hybrid: RRF (k=60) · optional CrossEncoder rerank |
| RAG | pack (dedupe + char budget) → abstain early (no / weak evidence) → JSON-schema generation (`rag-answer-v2`, evidence delimited as untrusted) → Pydantic → citation verification (invalid markers dropped, uncited answers become abstentions) |
| SQL Analyst | separate `knowflow_demo` database + SELECT-only role · glossary clarification before any model call · `sql-v3` generation with schema comments and FK hints · SQLGlot AST validation · READ ONLY transaction with timeouts and a row cap (ADR-006) |
| Evaluation | evidence matchers (document + quote/page) so labels survive re-indexing · deterministic metrics · resumable runs with full config + machine profile |
| Concurrency | one shared generation gate (`modules/models/gate.py`) for RAG and SQL; readiness reports a busy Ollama as busy rather than down |
| Safety | workspace filter in every query; log redaction by key and by value; audit events with request ids (ids/counts/statuses only); write-only, Fernet-encrypted connection secrets |
| Web | Next.js App Router pages: Overview, Library, Ask, SQL Analyst, Evaluation Lab, Models & Settings, Activity, Help; same-origin proxy with a 600 s timeout for CPU generation |

## M0 foundation

### M0 – foundation

| Concern | Implementation |
|---|---|
| Configuration | `apps/api/app/core/config.py` – `pydantic-settings`, env-driven, validated at startup |
| Logging | `apps/api/app/core/logging.py` – one JSON object per line, `request_id` bound via contextvar, secret-key redaction |
| Request correlation | `apps/api/app/core/middleware.py` – accepts a safe inbound `X-Request-ID` or generates a UUID; echoed in response header and error body |
| Errors | `apps/api/app/core/errors.py` – envelope `{error: {code, message, request_id}}`; unhandled exceptions → `internal_error` with no stack trace |
| Health | `GET /api/v1/health/live` (process) and `GET /api/v1/health/ready` (PostgreSQL and Ollama checked **separately**, each with its own timeout; 503 if any required dependency is down) |
| Web shell | Next.js App Router; DRD tokens in `globals.css`; sidebar + top bar; Overview reads `/api/v1/health/ready` |
| Database runtime | Native conda PostgreSQL (dev) or `pgvector/pgvector:pg16` (Docker/CI); shared init SQL in `infra/postgres/init/` |
| Database access | `apps/api/app/db/session.py` – one shared **sync** SQLAlchemy 2 engine (psycopg 3). Endpoints are `def`, so FastAPI runs them in its threadpool. Reason: psycopg's async mode doesn't support Windows' default Proactor event loop, and a single-user local app gains nothing from async DB I/O. |
| HTTP to Ollama | One reused `httpx.Client` per base URL. Building a client loads the CA bundle (~200 ms on Windows), which measurably slowed every readiness probe (2,200 ms → 2 ms after switching to `127.0.0.1` and reusing the client). |
| Paid-API guard | `scripts/check_no_paid_apis.py` (CI `policy` job) fails on paid inference SDKs in manifests or hosted endpoints in source |
