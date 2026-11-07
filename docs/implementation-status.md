# Implementation Status & Roadmap

Resume point for any new session: read this file, then `git log --oneline` and `git status`.
Milestones follow PRD §7 exactly. A milestone is complete only when its exit criteria are verified,
tests pass, docs are updated and the work is committed.

_Last updated: 2026-11-07_

## Current state

| Item | Value |
|---|---|
| Active milestone | **M7 – Product polish and safety: complete**. Next: M8 – Release |
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
| `qwen3:4b` | M4 | **Pulled** 2026-11-07 (2.5 GB, id 359d7dd4bcda) | `ollama pull qwen3:4b` |
| `nomic-embed-text:v1.5` | M3 | **Pulled** 2026-11-07 (274 MB, id 0a109f422b47) | `ollama pull nomic-embed-text:v1.5` |
| `BAAI/bge-reranker-v2-m3` (optional) | M5 | Not installed; ~2.3 GB weights + torch CPU — likely too heavy for 7.3 GB RAM alongside qwen3:4b; will be measured, not assumed | `pip install -e "apps/api[reranker]"` |
| Playwright browsers | M7 | Not needed locally: `PW_CHANNEL=msedge` uses the installed Edge. CI installs Chromium | `npx playwright install chromium` |
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
- [x] Extraction (PDF pages, DOCX headings, TXT/MD sections) with limits/timeouts (child process, killed on timeout)
- [x] Fixed + recursive chunking (ADR-005); both stored; FTS `search_tsv` generated column + GIN index
- [x] DB-backed job worker (`dev.ps1 worker`): SKIP LOCKED claim, heartbeat, exponential retry, stale-job recovery, graceful shutdown
- [x] Chunk inspection drawer (extraction preview, chunks per strategy), retry action, live progress polling, worker-missing banner
- [x] **Exit:** uploaded file becomes searchable chunks; restart and failure states tested

#### M2 verification record (2026-11-07)

| Check | Result |
|---|---|
| `dev.ps1 check` | Pass. pytest 164/164 (11 worker integration tests: success, bad input, backoff, retry_after, stale recovery, re-index idempotence, delete mid-job, missing file, workspace-scoped search, heartbeat), vitest 53/53, build OK |
| Live: worker on real PDF (3 pages), DOCX (headings + table), MD, TXT | Pass. All `ready`; ~1.7 s per document (dominated by spawning the extraction child process) |
| Live: `GET /search?q=hotel cap` | Pass. Top hit is travel-policy.pdf, page 2 |

### M3 – Local model integration
- [x] Ollama health + model adapter interfaces (`EmbeddingModel`, `ChatModel`; bounded timeouts, one retry on 5xx)
- [x] Nomic embedding adapter (task prefixes), dimension probe, `embedding_versions`, batched pgvector storage (ADR-002)
- [x] Models & Settings page: runtime, installed models, selection, validate (real probes), embedding-change warning, re-index all
- [x] **Exit:** embeddings generated locally; missing model gives actionable instructions; no external API

#### M3 verification record (2026-11-07)

| Check | Result |
|---|---|
| `dev.ps1 check` | Pass. pytest 182 passed + 2 opt-in real-model tests skipped; vitest 59/59; build OK |
| `KNOWFLOW_RUN_OLLAMA=1` real-model tests | Pass. nomic dimension 768; qwen3:4b returns schema-valid JSON |
| Live re-index of 4 documents with the real embedding model | Pass. All ready, 0 needing re-index, active version 768-d |
| Live dense search on paraphrases ("accommodation per night") | Finds travel-policy.pdf p.2 (cosine 0.745); lexical finds nothing. Not a quality claim; M5 measures it |

### M4 – Basic RAG
- [x] Dense retrieval, context packing (dedupe + char budget), versioned prompts (`rag-answer-v2`), Qwen generation with JSON Schema, Pydantic validation
- [x] Citation verification (invalid markers dropped, renumbered; uncited answers become abstentions), source drawer, abstention (no sources / weak evidence / model / unsupported); conversations (rename/delete); feedback with reason
- [x] Generation concurrency cap (429 `generation_busy`); Next proxy timeout raised to 600 s (the 30 s default dropped CPU-generated answers)
- [x] **Exit:** user asks question and receives grounded answer with clickable source citation

#### M4 verification record (2026-11-07)

| Check | Result |
|---|---|
| `dev.ps1 check` | Pass. pytest 202 passed + 2 opt-in skipped, vitest 66/66, build OK |
| Live API, qwen3:4b on CPU | "hotel per night": 150 EUR [1], page 2 (88 s incl. model load); "approve 3000 EUR trip": director [1], page 3 (56 s); "parental leave": abstained (30 s) |
| Live UI via Playwright (Edge), prompt v2 | Answer with citation chip, source drawer with exact excerpt, retrieval details, 29 s; no console errors; no horizontal overflow at 390 px |
| Bug found and fixed | Next's rewrite proxy cut long requests at 30 s ("socket hang up"), so the UI showed an error although the API saved the answer. `experimental.proxyTimeout` is now 600 s |

Not done (recorded in ADR-000 G-8): RAG `/chat/clarify` is not exposed. Conversation history is shown but not sent to retrieval (each question is retrieved independently).

### M5 – Retrieval experiments
- [x] Postgres FTS (OR-of-terms; AND matched nothing on natural questions), RRF (k=60), top-k controls, reranker adapter + toggle (optional install)
- [x] Dataset create / CSV+JSONL import with row errors, bundled synthetic corpus + 50-case gold set (sample loader), deterministic metrics, worker-executed resumable runs, comparison table, per-case inspector, JSON/CSV export
- [~] **Exit:** S1–S3 (+ lexical reference) run on the same gold set with reproducible metrics (S2 rerun gave identical numbers in tests). **S4 not measured**: the reranker isn't installed on this machine (ADR-004)

#### M5 verification record (2026-11-07)

| Check | Result |
|---|---|
| Tests | pytest 220 passed + 2 opt-in skipped (evaluation integration: S1–S3 same set, reproducibility, S4 refusal, S4 with a fake reranker, answers, export, dataset lock, resume after crash); vitest 71/71 |
| Real benchmark (nomic, qwen3:4b, CPU) | See docs/evaluation/README.md. S3 hybrid MRR 0.891 vs S2 dense 0.879; answers on the held-out split: abstention 12/12, citation precision 0.955, p50 57 s |
| Not done | S4 (reranker not installed). Gold labels not yet human-reviewed |

### M6 – Text-to-SQL
- [x] Demo database `knowflow_demo` (synthetic: 120 customers, 16 products, 900 orders, 2,168 items, 864 payments incl. refunds, duplicate names, NULLs), `dev.ps1 seed-demo`; SELECT-only role verified by attack attempts (ADR-006)
- [x] Introspection with comments + FK join hints; editable glossary (ambiguous terms with 2-4 options, definitions)
- [x] Deterministic glossary clarification (no model call) + model clarification; SQL prompt `sql-v3`; SQLGlot AST validation; read-only execution with timeouts and row cap; one user-triggered repair turn
- [x] Write-only encrypted connection secrets; read-only check refuses superusers / writable roles; history with redacted literals
- [x] SQL Analyst UI: schema browser + glossary, clarification panel, highlighted read-only SQL with copy, model interpretation labelled, sortable results with sticky header
- [x] **Exit:** ambiguous question asks clarification; unsafe SQL rejected; safe SELECT returns table

#### M6 verification record (2026-11-07)

| Check | Result |
|---|---|
| Tests | pytest 275 passed + 2 opt-in skipped; vitest 76/76. Includes 45 validator unit tests (35 unsafe statements rejected) and 9 SQL integration tests on a throwaway seeded database (Journey C, rejections never execute, timeout, row cap, model clarification, unsupported, repair, connection refusal, redaction, glossary) |
| Live, qwen3:4b | "Show me our best customers last month." returns the glossary clarification instantly; after "Highest paid revenue" the SQL runs read-only (69 s generation, 41 ms execution) and its top 5 match a hand-written query exactly. "Orders per status": correct in 19 s |
| Live model weaknesses (recorded, ADR-006) | With prompt v1/v2 the model misspelled identifiers; one repair output came back truncated. All failed safely. v3 fixed the Journey C query |
| Not measured | SQL accuracy benchmark (no SQL gold set yet) |

### M7 – Product polish and safety
- [x] Prompt injection: evidence delimited + policy (unit), injection sample in the gold set (real model: resisted 1/1), gated real-model test passes (no "PWNED", answers from the legitimate text)
- [x] Workspace isolation sweep over every resource endpoint (documents, chunks, extraction, search, conversations, feedback, activity); file limits (size, pages, chars, parser timeout) from M1/M2
- [x] Secret redaction in logs: by key and by value (connection URLs, `password=`, bearer tokens, Fernet tokens), including tracebacks
- [x] Audit events (migration 0007): every user action + worker ingestion outcomes, with request ids; ids/counts/statuses only (tested: question text never stored)
- [x] Activity page (events by category, ingestion jobs with errors and durations), Help page, Overview metrics + recent activity + quick actions, workspace name in the sidebar; no disabled nav items remain
- [x] Playwright suite (`npm run e2e`, mocked API): 8 pages × 390/820/1440 px without console errors or horizontal overflow, 404 escape, skip link, Journey A source drawer, sidebar navigation; added to CI
- [x] **Exit:** security and UX acceptance tests pass; no dead-end screens

#### M7 verification record (2026-11-07)

| Check | Result |
|---|---|
| pytest | 282 passed + 3 opt-in real-model tests (all 3 pass when run with `KNOWFLOW_RUN_OLLAMA=1`) |
| vitest | 80/80 |
| Playwright (Edge, production build) | 28/28 |
| Not done | Automated contrast audit (tokens were checked by hand in M0, `tokens.test.ts`); screen-reader pass with a real assistive technology |

### M8 – Release and deployment
- [ ] Production build, migrations, seed demo, CI green, docs, evaluation report, screenshots, demo video, release tag
- [ ] **Exit:** a new machine can follow setup docs and run locally; CI green

## Benchmark status

No benchmarks have been run. All quality, latency and resource metrics are **NOT MEASURED**.
