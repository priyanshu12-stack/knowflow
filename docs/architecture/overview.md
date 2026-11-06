# Architecture Overview

Source of truth: [TRD §5](../TRD.md). This page documents what is **implemented**; the TRD
documents the target. Sections are added as milestones land.

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

## Implemented so far

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
