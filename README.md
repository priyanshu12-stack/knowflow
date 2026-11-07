# KnowFlow

**Answers grounded in your knowledge.** KnowFlow is a local-first knowledge workspace. It indexes your documents,
answers questions with citations you can open, asks before guessing what an ambiguous business term means in SQL, and
includes an evaluation lab that measures whether a retrieval change actually helped.

All inference runs locally through [Ollama](https://ollama.com). **No paid API, API key or hosted model endpoint is
needed** ([ADR-007](docs/decisions/ADR-007-local-only-cost-boundary.md)). Free model weights still cost CPU/GPU time,
RAM, disk and electricity.

| Ask with citations | SQL with clarification |
|---|---|
| ![Ask KnowFlow: answer with a numbered citation and the source drawer open](docs/screenshots/ask-citation.png) | ![SQL Analyst: validated read-only SQL and its result table](docs/screenshots/sql-result.png) |
| **Evaluation Lab** | **Knowledge Library** |
| ![Evaluation Lab comparing S1-S3 on the same gold set](docs/screenshots/evaluation-lab.png) | ![Knowledge Library with indexed documents](docs/screenshots/library.png) |

More: [Overview](docs/screenshots/overview.png) · [SQL clarification](docs/screenshots/sql-clarification.png) ·
[per-case inspector](docs/screenshots/evaluation-case.png) · [Activity](docs/screenshots/activity.png) ·
[Models & Settings](docs/screenshots/settings.png). All screenshots show the real app with real data, running on the
reference machine.

## What it does

- **Knowledge Library.** Upload PDF (text-based), DOCX, TXT and Markdown. Files are validated by extension, MIME type, signature and
  size, stored under generated names, extracted in a sandboxed child process with page and heading metadata, chunked
  two ways (fixed and recursive), and embedded locally. Duplicates get skip / re-index / new-version choices. Failures
  are shown in plain language and can be retried.
- **Ask KnowFlow.** Semantic, keyword or hybrid (RRF) retrieval. Answers come back as JSON-schema output from the local model,
  and every `[n]` citation is checked against the passages that were actually retrieved. An answer with no valid
  citation isn't shown; KnowFlow says *No supporting source found* instead. Citations open the exact passage. Text
  inside documents is treated as data, so injected instructions are ignored (tested with the real model).
- **SQL Analyst.** Runs against a synthetic sales database or your own PostgreSQL. Ambiguous terms such as "best customer"
  trigger a clarification *before* any SQL is written. Generated SQL is validated with SQLGlot's AST (one SELECT, an
  allow-listed schema, no writes, DDL, locks, catalogs or dangerous functions) and executed by a SELECT-only role, in a read-only
  transaction, with a time limit and a row cap.
- **Evaluation Lab.** Gold-set import (CSV/JSONL), strategies S1–S4, deterministic Recall@K / Precision@K / MRR / nDCG@K,
  abstention, citation precision and latency. Every run records its full configuration, models, digests and machine.
  It also has a per-case inspector and JSON/CSV export.
- **Models & Settings, Activity, Help.** Local runtime status, model validation with real probes, embedding-version
  safety, an audit trail with request ids, and troubleshooting.

## Measured results (sample set, reference machine)

From [docs/evaluation/README.md](docs/evaluation/README.md). That page covers the dataset, configuration and caveats:
50 synthetic questions labelled by the coding agent, **not yet reviewed by a person**, over a 5-document corpus.

| Strategy (top-K 5) | Recall@5 | MRR | nDCG@5 | Retrieval p50 |
|---|---|---|---|---|
| S1 fixed + dense | 0.989 | 0.837 | 0.873 | 40 ms |
| S2 recursive + dense | 0.947 | 0.879 | 0.891 | 40 ms |
| S3 recursive + hybrid (RRF) | 0.968 | 0.891 | 0.905 | 42 ms |
| S4 + reranker | NOT MEASURED | NOT MEASURED | NOT MEASURED | reranker not installed |

Answers (qwen3:4b, held-out split, 12 cases): abstention correct 12/12, citation precision 0.955, answer latency
p50 57 s on CPU. Prompt injection resisted 1/1 in the safety probes.

## Architecture

```text
Browser ──► Next.js 16 (App Router, TS) ── same-origin /api/v1/* proxy ──► FastAPI (Python 3.12)
                                                                             │
                     PostgreSQL 16: app data · pgvector (exact cosine) · FTS ◄┤
                     knowflow_demo DB (synthetic, SELECT-only role) ◄─────────┤ SQL Analyst
                     Ollama: qwen3:4b (answers, SQL) · nomic-embed-text ◄─────┤
                                                                             │
                     Worker process (same codebase): ingestion jobs + evaluation runs
```

Details are in [docs/architecture/overview.md](docs/architecture/overview.md) and the [ADRs](docs/decisions/README.md).

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | API and worker |
| Node.js | 22+ | Web |
| Ollama | recent | Runs on the host. KnowFlow never downloads models itself |
| PostgreSQL 16 + pgvector 0.8 | | **Either** Docker **or** a native conda env (Windows without Docker, [ADR-008](docs/decisions/ADR-008-native-postgres-dev-runtime.md)) |

Model profiles (TRD §4.1): `qwen3:4b` for ~8 GB RAM machines (the default), `qwen3:8b` for 16 GB+ machines (set
`OLLAMA_GENERATION_MODEL`).

## Quick start (Windows, PowerShell)

```powershell
./scripts/dev.ps1 setup              # API venv + web deps; creates .env from .env.example
notepad .env                          # set POSTGRES_PASSWORD and DEMO_DB_READER_PASSWORD

./scripts/db.ps1 install              # one time: conda env with PostgreSQL 16 + pgvector
./scripts/db.ps1 init                 # one time: cluster in data/postgres
./scripts/db.ps1 start                # each session
#   or with Docker:  docker compose -f infra/docker-compose.yml --env-file .env up -d
./scripts/dev.ps1 migrate             # create / upgrade the schema
./scripts/dev.ps1 seed-demo           # synthetic SQL demo database + read-only role

ollama pull qwen3:4b                  # ~2.5 GB
ollama pull nomic-embed-text:v1.5     # ~0.3 GB

./scripts/dev.ps1 api                 # terminal 1: http://127.0.0.1:8000/api/docs
./scripts/dev.ps1 worker              # terminal 2: ingestion + evaluation worker
./scripts/dev.ps1 web                 # terminal 3: http://localhost:3000
```

macOS/Linux: the same targets exist in the `Makefile` (`make setup`, `make db-up`, `make migrate`, `make seed-demo`,
`make api`, `make worker`, `make web`).

Then open http://localhost:3000. The Overview page checks every dependency and shows the exact command for anything
that's missing. To try it with content, open **Knowledge Library → Load sample documents**, wait until they're Ready,
then ask *"How much can I spend on a hotel per night?"*, or in the SQL Analyst *"Show me our best customers last
month."*

## Configuration

Everything lives in `.env` (see `.env.example`, which documents every variable). The main groups are:

- **Database:** `POSTGRES_*`.
- **Models:** `OLLAMA_*`, `EMBEDDING_BATCH_SIZE`, `GENERATION_TIMEOUT_SECONDS`, `GENERATION_NUM_CTX`, `ENABLE_RERANKER`.
- **Ingestion limits:** `UPLOAD_MAX_BYTES`, `MAX_PDF_PAGES`, `EXTRACTION_TIMEOUT_SECONDS`, `CHUNK_SIZE_CHARS`, `CHUNK_OVERLAP_CHARS`.
- **SQL Analyst:** `DEMO_DB_READER_PASSWORD`, `SQL_STATEMENT_TIMEOUT_MS`, `SQL_MAX_ROWS`, `SECRET_KEY` (encrypts stored
  connection passwords; auto-generated into `data/secret.key` if empty).

## Checks

```powershell
./scripts/dev.ps1 check        # ruff, mypy --strict, eslint, prettier, tsc, pytest (with DB), vitest, next build
cd apps/web; $env:PW_CHANNEL="msedge"; npm run e2e      # Playwright: 8 pages × 390/820/1440 px, journeys
$env:KNOWFLOW_RUN_OLLAMA="1"; ./scripts/dev.ps1 test     # also run the real-model smoke tests
```

At the time of release: pytest 282 passed (plus 3 real-model tests, which pass when enabled), Vitest 80/80, Playwright 28/28. CI
(GitHub Actions) runs the same checks against `pgvector/pgvector:pg16` and never downloads model weights. **CI hasn't
run yet**, because the repository has no remote.

## API

Interactive docs are at `/api/docs`. Errors always use `{ "error": { "code", "message", "request_id" } }`, and stack traces are never returned.

| Area | Endpoints |
|---|---|
| Health | `GET /api/v1/health/live`, `GET /api/v1/health/ready` |
| Documents | `POST/GET /documents`, `GET/DELETE /documents/{id}`, `POST /documents/{id}/retry`, `GET /documents/{id}/chunks`, `GET /documents/{id}/extraction`, `GET /jobs/{id}`, `GET /search` |
| Ask | `POST /chat/query`, `GET /conversations`, `GET/PATCH/DELETE /conversations/{id}`, `PUT /messages/{id}/feedback` |
| SQL | `GET /sql/connections`, `POST /sql/connections/test`, `GET /sql/schema/{id}`, `PUT /sql/connections/{id}/glossary`, `POST /sql/query` |
| Evaluation | `POST/GET /evaluations/datasets`, `POST /evaluations/datasets/{id}/cases/import`, `POST /evaluations/sample`, `POST/GET /evaluations/runs`, `GET /evaluations/runs/{id}[/export]` |
| Settings | `GET/PUT /settings/models`, `POST /settings/models/validate`, `POST /settings/reindex` |
| Activity | `GET /activity/events`, `GET /activity/jobs`, `GET /activity/summary` |

## Repository layout

```text
apps/api      FastAPI app (core, api/v1, db, modules/{documents,retrieval,rag,models,evaluation,sql_assistant}, workers), Alembic, tests
apps/web      Next.js app (src/app pages, src/components, src/lib/api), Vitest, Playwright (e2e/)
samples       synthetic demo documents and the evaluation gold set
infra         docker-compose.yml, shared Postgres init SQL
scripts       dev.ps1, db.ps1, build_gold_set.py, check_no_paid_apis.py, specs_to_md.py
docs          TRD/PRD/DRD, traceability matrix, status, ADRs, architecture, evaluation, design system, screenshots
```

## Documentation

- Specifications: [TRD](docs/TRD.md) · [PRD](docs/PRD.md) · [DRD](docs/DRD.md). The `.docx` files in the repo root are authoritative.
- [Requirements traceability](docs/requirements-traceability.md) (every spec requirement → module → test → status) ·
  [Implementation status](docs/implementation-status.md)
- [Decisions (ADR-000 … ADR-008)](docs/decisions/README.md) · [Evaluation report](docs/evaluation/README.md) ·
  [Building a gold set](docs/evaluation/dataset-guide.md) · [Demo data sources](docs/demo-data-sources.md) ·
  [Design system](docs/design-system.md)

## Known limitations

- **Speed.** Answers and SQL are generated on the CPU. On the 7.3 GB reference machine that takes 30–90 s per answer, and longer
  when the model has to be reloaded. Close memory-heavy apps, or use a bigger machine with `qwen3:8b`.
- **SQL quality.** `qwen3:4b` sometimes writes invalid SQL (misspelled identifiers). It always fails safely, and the user
  can ask for one repair. No SQL accuracy benchmark has been run.
- **Not measured.** S4 (the reranker isn't installed), LLM-judged answer correctness and faithfulness, peak RAM, and tokens/s.
- **Not built (recorded deviations).** RAG query classification and `/chat/clarify` (ADR-000 G-8), the semantic chunking experiment,
  streaming answers (P2), scanned-PDF OCR, image/audio/video, fine-tuning, multi-tenant SaaS, paid API fallbacks.
- **Evaluation labels.** These were written by the coding agent and checked mechanically, but haven't been reviewed by a person. Dated-conflict cases list only
  one acceptable passage.
- **Release.** CI hasn't run (there's no remote) and no demo video has been recorded. The local tag is a release candidate.
