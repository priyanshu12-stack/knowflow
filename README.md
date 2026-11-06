# KnowFlow

**Answers grounded in your knowledge.** KnowFlow is a local-first knowledge intelligence workspace:
it ingests your documents, retrieves evidence with hybrid search, answers with verifiable citations,
asks for clarification before running ambiguous SQL, and ships an evaluation lab that measures whether
a change actually improved retrieval quality.

All inference runs locally through [Ollama](https://ollama.com). **No paid API, API key or hosted
model endpoint is required** ([ADR-007](docs/decisions/ADR-007-local-only-cost-boundary.md)).
Free model weights still cost your CPU/GPU time, RAM, disk and electricity.

> **Status: early development.** Milestone M0 (repository foundation) is complete. M1 (document upload) is next.
> What works today: API health/readiness, and a web shell that reports real database and model
> readiness. Progress lives in [docs/implementation-status.md](docs/implementation-status.md).
> No benchmark has been run yet, so all quality metrics are **NOT MEASURED**.

## Architecture

```text
Browser ──► Next.js (App Router, TS) ── /api/v1/* same-origin rewrite ──► FastAPI (Python 3.12)
                                                                          │
                                       PostgreSQL 16 + pgvector + FTS ◄───┤
                                       Ollama (qwen3:4b, nomic-embed-text) ◄┘
```

The full design is in [docs/TRD.md](docs/TRD.md) §5, and what's implemented so far is in [docs/architecture/overview.md](docs/architecture/overview.md).

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | API |
| Node.js | 22+ | Web |
| Ollama | recent | Runs on the host. The app never downloads models by itself |
| PostgreSQL 16 + pgvector | 0.8.x | **Either** Docker **or** a native conda env (Windows without Docker, [ADR-008](docs/decisions/ADR-008-native-postgres-dev-runtime.md)) |

Model profiles (TRD §4.1): `qwen3:4b` for machines around 8 GB RAM (the default), and `qwen3:8b` for 16 GB+ machines.

## Quick start (Windows, PowerShell)

```powershell
./scripts/dev.ps1 setup             # API venv + web deps; creates .env from .env.example
notepad .env                         # set POSTGRES_PASSWORD

# Database: native (no Docker) ...
./scripts/db.ps1 install             # one time: conda env with PostgreSQL 16 + pgvector
./scripts/db.ps1 init                # one time: cluster in data/postgres, database, extension
./scripts/db.ps1 start               # each session (stop with: ./scripts/db.ps1 stop)
# ... or with Docker:  docker compose -f infra/docker-compose.yml --env-file .env up -d
#     (the Compose file is validated in CI but hasn't been run on the Windows reference machine)

ollama pull qwen3:4b                 # ~2.5 GB
ollama pull nomic-embed-text:v1.5    # ~0.3 GB

./scripts/dev.ps1 api                # terminal 1: http://127.0.0.1:8000/api/docs
./scripts/dev.ps1 web                # terminal 2: http://localhost:3000
```

On macOS/Linux, the same targets exist in the `Makefile` (`make setup`, `make db-up`, `make api`, `make web`).

Open http://localhost:3000. The Overview page checks PostgreSQL, pgvector, Ollama and both models,
and shows the exact command to fix anything that's missing.

## Checks

```powershell
./scripts/dev.ps1 check    # ruff, mypy, eslint, tsc, prettier, pytest (incl. DB integration), vitest, build
```

CI (GitHub Actions) runs the same checks against a `pgvector/pgvector:pg16` service. It never downloads LLM weights.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health/live` | Process liveness |
| `GET /api/v1/health/ready` | PostgreSQL, pgvector and Ollama status (503 if a required dependency is down), plus model availability with setup commands |

Errors always use `{ "error": { "code", "message", "request_id" } }`. Stack traces are never returned.
Interactive docs are at `/api/docs`.

## Repository layout

```text
apps/api      FastAPI backend (app/core, app/api/v1, app/db, tests/)
apps/web      Next.js frontend (src/app, src/components, src/lib)
infra         docker-compose.yml, shared Postgres init SQL
scripts       db.ps1, dev.ps1, check_no_paid_apis.py, specs_to_md.py
docs          TRD/PRD/DRD, traceability, status, ADRs, architecture, evaluation, design system
```

## Documentation

- Specifications: [TRD](docs/TRD.md) · [PRD](docs/PRD.md) · [DRD](docs/DRD.md). The `.docx` files in the repo root are authoritative.
- [Requirements traceability](docs/requirements-traceability.md) · [Implementation status](docs/implementation-status.md)
- [Decisions (ADRs)](docs/decisions/README.md) · [Design system](docs/design-system.md) · [Branching & commits](docs/branch-strategy.md)

## Known limitations

- Scanned-PDF OCR, image/audio/video, fine-tuning, SaaS multi-tenancy and paid API fallbacks are out of scope for v1 (TRD §2).
- On machines with little RAM, local generation will be slow. Latency figures will be published only after they're measured.
