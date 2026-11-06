# Implementation Status & Roadmap

Resume point for any new session: read this file, then `git log --oneline` and `git status`.
Milestones follow PRD §7 exactly. A milestone is complete only when its exit criteria are verified,
tests pass, docs are updated and the work is committed.

_Last updated: 2026-11-07_

## Current state

| Item | Value |
|---|---|
| Active milestone | **M1 – Data foundation: complete**. Next: M2 – Ingestion pipeline |
| Branch | `main` (M0 merged from `feat/m0-foundation`) |
| Last verified commit | `43ca513` fix(scripts), merged to `main` |

## Development machine profile (measured 2026-11-06)

| Resource | Value | Consequence |
|---|---|---|
| OS | Windows 11 Home 10.0.26300 | PowerShell scripts provided alongside Makefile |
| CPU | AMD Ryzen 5 7530U, 6 cores / 12 threads | CPU-only inference |
| RAM | 7.3 GB total (~0.8 GB free at audit time) | TRD **low-resource profile**: `qwen3:4b`; reranker off by default |
| GPU | AMD Radeon integrated (512 MB reported) | Not used for inference |
| Disk | A: 37.4 GB free, C: 34.9 GB free | Enough for qwen3:4b (~2.5 GB) + nomic-embed-text (~0.3 GB) |
| Python | 3.12.7 (Anaconda) | Meets TRD ≥3.12 |
| Node / npm | 22.13.0 / 11.6.3 | |
| Ollama | 0.17.1, running, **no models pulled** | Pull at M3 (approved by owner) |
| Docker | **Not installed** | Native PostgreSQL via conda (see ADR-008). The Compose file is validated in CI only |
| PostgreSQL | 16.15 + pgvector 0.8.6 via conda (PG 17 not solvable with pgvector on win-64) | ADR-008 |
| Git remote | None (owner chose local commits only for now) | Push deferred |

## Missing prerequisites

| Prerequisite | Needed by | Status | Setup |
|---|---|---|---|
| PostgreSQL 16 + pgvector | M0 | **Installed**: conda env `knowflow-pg`, PG 16.15 + pgvector 0.8.6, cluster in `data/postgres` | `scripts/db.ps1 install` / `init` / `start` |
| `qwen3:4b` | M4 | Not pulled | `ollama pull qwen3:4b` |
| `nomic-embed-text:v1.5` | M3 | Not pulled | `ollama pull nomic-embed-text:v1.5` |
| `BAAI/bge-reranker-v2-m3` (optional) | M5 | Not installed; ~2.3 GB weights + torch CPU — likely too heavy for 7.3 GB RAM alongside qwen3:4b; will be measured, not assumed | `pip install -e "apps/api[reranker]"` |
| Playwright browsers | M7 | Not installed | `npx playwright install chromium` |
| GitHub remote + credentials | M8 push | Not configured | owner to provide repo URL |

## Milestone checklist (PRD §7)

### M0 – Repository foundation
- [x] Read TRD, PRD, DRD in full; Markdown copies in `docs/`
- [x] Repository audit (no prior repo, no prior code)
- [x] Requirements traceability matrix
- [x] Implementation roadmap (this file)
- [x] `git init`, `.gitignore`, `.gitattributes`, `.env.example`, README, CHANGELOG
- [x] ADRs: ADR-000 (spec priority), ADR-007 (cost boundary), ADR-008 (native Postgres), ADR-001 draft (model runtime)
- [x] Branch strategy doc, issue/PR templates
- [x] Native PostgreSQL + pgvector scripts; `infra/docker-compose.yml` for Docker hosts / CI
- [x] FastAPI skeleton: config, JSON logging, request_id, error envelope, `/api/v1/health/live`, `/api/v1/health/ready`
- [x] Next.js skeleton: Tailwind + shadcn tokens per DRD, app shell, Overview readiness (real data)
- [x] Lint/format/typecheck configs (ruff, mypy strict, ESLint, TS strict, Prettier)
- [x] Tests: pytest (19, incl. real-DB integration), Vitest (39)
- [x] GitHub Actions CI written. **Not yet run**: there's no remote
- [x] Fresh-clone verification (clone → setup → start → health). It found and fixed two PowerShell bugs (`43ca513`)
- [x] **Exit:** clean clone starts web, API and DB; health checks pass; no secrets committed

#### M0 verification record (2026-11-06)

| Check | Result |
|---|---|
| `./scripts/dev.ps1 check` (ruff, ruff format, mypy --strict, eslint, prettier, tsc, pytest, vitest, next build) | Pass. pytest 19/19 (incl. real-DB integration), vitest 39/39, build OK |
| Fresh clone into scratch dir → `dev.ps1 setup` → `db.ps1 init` (new cluster, port 5433) → `dev.ps1 api` + `web` | Pass. Web 200; `/api/v1/health/live` via proxy OK; `/ready` = `degraded` (PG 16.15, pgvector 0.8.6, Ollama 0.17.1 ok; models not pulled) |
| `db.ps1 status/stop/start` with piped output | Pass (hung before `43ca513`) |
| Paid-API guard, incl. a negative test with a banned SDK | Pass / correctly fails |
| Secrets: `.env` ignored; DB password not present in the git index | Pass |
| Readiness probe latency (warm) | Postgres ~1–2 ms, Ollama ~2–3 ms (was 2,200 ms before using `127.0.0.1` and a reused client) |
| Visual check (headless Edge) at 390 / 820 / 1440 px | Pass. No horizontal overflow at a true 390 px viewport |
| GitHub Actions | **Not run.** There's no remote yet |
| Docker Compose `up` | **Not run.** Docker isn't installed (ADR-008); CI validates the config |

### M1 – Data foundation
- [x] SQLAlchemy models, Alembic migrations (workspaces, documents, ingestion_jobs)
- [x] Default workspace + rename
- [x] Filesystem storage service (generated keys, checksum, path-root verification)
- [x] Upload API with extension/MIME/signature/size validation; duplicate checksum handling
- [x] Knowledge Library UI (dropzone, table, delete confirmation, states)
- [x] **Exit:** upload PDF/DOCX/TXT/MD; metadata persists; duplicate handled; file stored safely

#### M1 verification record (2026-11-07)

| Check | Result |
|---|---|
| `dev.ps1 check` | Pass. pytest 137/137 (incl. workspace-isolation integration), vitest 49/49, build OK |
| Live API: upload `.md` → 202 queued; same file → 409 `duplicate_document`; fake PDF → 415 `signature_mismatch` | Pass |
| Library page in headless Edge with real data | Pass |
| `db.ps1 start` when already running | Pass (now idempotent) |

### M2 – Ingestion pipeline
- [ ] Extraction (PDF pages, DOCX headings, TXT/MD sections) with limits/timeouts
- [ ] Fixed + recursive chunking
- [ ] DB-backed job worker; retries; stale-job recovery
- [ ] Chunk inspection drawer
- [ ] **Exit:** uploaded file becomes searchable chunks; restart and failure states tested

### M3 – Local model integration
- [ ] Ollama health + model adapter interfaces
- [ ] Nomic embedding adapter, dimension probe, embedding_versions, batched pgvector storage
- [ ] Models & Settings page
- [ ] **Exit:** embeddings generated locally; missing model gives actionable instructions; no external API

### M4 – Basic RAG
- [ ] Dense retrieval, context packing, versioned prompts, Qwen generation, Pydantic response
- [ ] Citations + source drawer + abstention; conversations; feedback
- [ ] **Exit:** user asks question and receives grounded answer with clickable source citation

### M5 – Retrieval experiments
- [ ] Postgres FTS, RRF, top-k controls, reranker adapter/toggle
- [ ] Dataset import, retrieval metrics, run worker, comparison UI, per-case inspector, export
- [ ] **Exit:** four configurations (S1–S4) run on same gold set with reproducible metrics

### M6 – Text-to-SQL
- [ ] Demo schema + synthetic seed, read-only role, introspection, glossary
- [ ] Ambiguity detection + clarification, SQL generation, SQLGlot validation, read-only execution
- [ ] SQL Analyst UI
- [ ] **Exit:** ambiguous question asks clarification; unsafe SQL rejected; safe SELECT returns table

### M7 – Product polish and safety
- [ ] Prompt-injection tests, workspace filters, file limits, secret redaction, audit events
- [ ] Activity page; all empty/loading/error states; responsive + accessibility pass; Playwright
- [ ] **Exit:** security and UX acceptance tests pass; no dead-end screens

### M8 – Release and deployment
- [ ] Production build, migrations, seed demo, CI green, docs, evaluation report, screenshots, demo video, release tag
- [ ] **Exit:** a new machine can follow setup docs and run locally; CI green

## Benchmark status

No benchmarks have been run. All quality, latency and resource metrics are **NOT MEASURED**.
