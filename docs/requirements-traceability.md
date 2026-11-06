# Requirements Traceability Matrix

Every requirement extracted from the three authoritative specifications, mapped to
milestone → implementation module → test → status.

- Sources: `TRD` = [docs/TRD.md](TRD.md), `PRD` = [docs/PRD.md](PRD.md), `DRD` = [docs/DRD.md](DRD.md).
  Section numbers refer to those documents (generated from the `.docx` originals by `scripts/specs_to_md.py`).
- Status values: `Not started` · `In progress` · `Done` (implemented **and** tested) · `Partial` · `Deferred` (P2 / out of scope, with reason) · `Blocked`.
- Module paths are relative to the repo root. Test IDs reference real test files once they exist; `—` means not yet written.
- Rule: a row only moves to `Done` when its test exists and passes. Update this file in the same commit as the implementation.

## 1. Platform constraints (cross-cutting)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| CON-01 | Zero paid inference APIs; LLM, embedding, reranking run locally by default | TRD §1, §4; PRD §2.1 | M3 | `scripts/check_no_paid_apis.py` (manifests + source); models module lands M3 | `check_no_paid_apis.py` negative test run manually; CI `policy` job | Partial |
| CON-02 | No API key / credit card / hosted endpoint required for core functionality | TRD §1; PRD §9 Privacy | M0–M8 | `.env.example` contains no provider keys | `scripts/check_no_paid_apis.py`; `.env.example` has no key variables | Done |
| CON-03 | Do not claim free weights = zero compute cost; document real resource cost | TRD §1, §13 | M0 | `docs/decisions/ADR-007-local-only-cost-boundary.md` | doc review | Done |
| CON-04 | No invented quality claims or benchmark numbers; unmeasured = NOT MEASURED | TRD §1, §9; PRD §2.2 | M5 | `docs/evaluation/` | doc review | In progress |
| CON-05 | Build in vertical slices; no empty placeholder modules | TRD §1; PRD §7 | all | repo-wide | code review | In progress |
| CON-06 | Provider-agnostic interfaces `ChatModel`, `EmbeddingModel`, `Reranker`; ship Ollama adapters only | TRD §4 | M3 | `apps/api/app/modules/models/base.py` | `tests/unit/models/test_interfaces.py` | Not started |
| CON-07 | Missing model → show setup command; never silently switch to paid endpoint | TRD §4.3; PRD §5.6 | M3 | `modules/models/health.py`, Settings UI | `tests/unit/models/test_missing_model.py` | Not started |
| CON-08 | Single-user local mode; keep `workspace_id` ownership boundaries in data model | TRD §2 | M1 | `apps/api/app/db/models.py` | `tests/integration/test_workspace_isolation.py` | Not started |
| CON-09 | Feature flags: semantic chunking, reranker, streaming, SQL assistant; disabled feature never breaks core RAG | TRD §15 | M2–M6 | `apps/api/app/core/config.py` | `tests/unit/test_feature_flags.py` | Not started |
| CON-10 | No automatic model downloads at runtime | TRD §2 out-of-scope | M3 | models module only probes, never pulls | `tests/unit/models/test_no_pull.py` | Not started |

## 2. Technology stack

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| STK-01 | Next.js App Router + TypeScript (strict) | TRD §3, §15 | M0 | `apps/web/` (Next.js 16.4.5, `strict: true`) | `npm run typecheck` | Done |
| STK-02 | Tailwind CSS + customised shadcn/ui + lucide-react; no second UI library | TRD §3; DRD §12 | M0 | `apps/web/src/components/ui/` (shadcn radix-nova, customised tokens) | code review | Done |
| STK-03 | Python 3.12+ FastAPI backend | TRD §3 | M0 | `apps/api/app/main.py` | `tests/api/test_health.py` | Done |
| STK-04 | Pydantic v2 at all boundaries (API, model output, config) | TRD §3, §15 | M0+ | `core/config.py` (pydantic-settings), response models in `api/v1/health.py` | contract tests | Partial |
| STK-05 | PostgreSQL 16+ as system of record | TRD §3, §5 | M0 | native: `scripts/db.ps1` (PG 16.15); Docker/CI: `pgvector/pgvector:pg16` | `tests/integration/test_postgres_ready.py` | Done |
| STK-06 | pgvector extension; exact search baseline, HNSW only after measurement | TRD §3, §12 | M3 | Alembic migration | `tests/integration/test_vector_search.py` | Not started |
| STK-07 | Postgres FTS (`tsvector`, `ts_rank_cd`) lexical retrieval | TRD §3 | M5 | `modules/retrieval/lexical.py` | `tests/integration/test_lexical.py` | Not started |
| STK-08 | Ollama local runtime | TRD §3 | M3 | `modules/models/ollama.py` | `tests/unit/models/test_ollama_adapter.py` | Not started |
| STK-09 | Generation: `qwen3:4b` (low-resource) / `qwen3:8b` (recommended); pinned tag + recorded digest | TRD §4.1 | M4 | `.env.example`, ADR-001 | eval run metadata | Not started |
| STK-10 | Embedding: `nomic-embed-text` pinned; dimension probed at startup and persisted | TRD §4.2, §7, §17 | M3 | `modules/models/embedding.py`, `embedding_versions` table | `tests/integration/test_dimension_probe.py` | Not started |
| STK-11 | Optional reranker `BAAI/bge-reranker-v2-m3` via Sentence Transformers, lazy loaded, `ENABLE_RERANKER=false` default | TRD §3, §4.2 | M5 | `modules/models/reranker.py` | `tests/unit/models/test_reranker_flag.py` | Not started |
| STK-12 | Custom chunking strategies (fixed, recursive, semantic experiment) | TRD §3 | M2 | `modules/documents/chunking/` | `tests/unit/chunking/` | Not started |
| STK-13 | SQLGlot AST validation + dedicated read-only Postgres role | TRD §3, §10 | M6 | `modules/sql_assistant/validate.py` | `tests/unit/sql/test_validator.py` | Not started |
| STK-14 | Postgres-backed job table + one worker process (no Redis/Celery) | TRD §3 | M2 | `apps/api/app/workers/` | `tests/integration/test_worker.py` | Not started |
| STK-15 | Pytest + HTTPX; Vitest; Playwright | TRD §3 | M0/M7 | pytest + Vitest in place; Playwright at M7 | CI | Partial |
| STK-16 | Custom gold-set evaluator; Ragas optional and supplementary only | TRD §3 | M5 | `modules/evaluation/` | `tests/unit/eval/test_metrics.py` | Not started |
| STK-17 | Structured JSON logs + request_id + local metrics table; no external telemetry | TRD §3 | M0 | `core/logging.py`, `core/middleware.py`; metrics table at M4 | `tests/unit/test_logging.py`, `tests/api/test_request_id.py` | Partial |
| STK-18 | Docker Compose for Postgres; native + Docker Ollama options documented | TRD §3, §13 | M0 | `infra/docker-compose.yml` (validated in CI, not run locally — ADR-008) | CI `compose` job | Partial |
| STK-19 | GitHub Actions: lint, typecheck, tests, migration check, build; never download LLMs | TRD §3, §9 | M0 | `.github/workflows/ci.yml` written; **not yet run** (no GitHub remote) | CI | Partial |
| STK-20 | SQLAlchemy 2.x + Alembic; never `create_all` at startup | TRD §15 | M1 | `apps/api/app/db/`, `apps/api/alembic/` | `tests/integration/test_migrations.py` | Not started |
| STK-21 | ruff + mypy (Python); ESLint + TS strict (web) | TRD §15 | M0 | `pyproject.toml`, `eslint.config.mjs` | `ruff`, `mypy --strict`, `eslint`, `tsc` | Done |

## 3. Model runtime contract (TRD §4.3)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| MOD-01 | Startup health-check of Ollama and required models | TRD §4.3 | M0/M3 | `core/readiness.py` (runtime + model presence); adapters at M3 | `tests/unit/test_readiness.py` | Partial |
| MOD-02 | Bounded timeouts, concurrency limits, cancellation for model calls | TRD §4.3, §12 | M3 | `modules/models/ollama.py` | `tests/unit/models/test_timeouts.py` | Not started |
| MOD-03 | Temperature 0–0.2 for extraction/SQL; moderate only for prose | TRD §4.3 | M4/M6 | prompt configs | unit test on request payload | Not started |
| MOD-04 | Structured output: Ollama JSON schema + independent Pydantic validation; invalid = recoverable error | TRD §4.3, §11 | M4 | `modules/models/structured.py` | `tests/unit/models/test_structured_output.py` | Not started |
| MOD-05 | Separate versioned system prompts per task (RAG, classify, clarify, SQL, eval) | TRD §4.3, §15 | M4 | `modules/rag/prompts/`, `modules/sql_assistant/prompts/` | prompt_version assertion tests | Not started |
| MOD-06 | Record model tag, quantization, runtime version, temperature, context, machine profile per benchmark run | TRD §4.3, §9 | M5 | `evaluation_runs.config` | `tests/unit/eval/test_run_metadata.py` | Not started |

## 4. Document ingestion (TRD §6.1, PRD §5.2)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| ING-01 | Support PDF (text), DOCX, TXT, MD; reject others | TRD §2; PRD §5.2 | M1 | `modules/documents/validation.py` | `tests/unit/documents/test_validation.py` | Not started |
| ING-02 | Enforce size, extension, MIME and file-signature checks | TRD §6.1, §11 | M1 | `modules/documents/validation.py` | same | Not started |
| ING-03 | UUID + SHA-256 checksum per upload | TRD §6.1 | M1 | `modules/documents/storage.py` | `tests/unit/documents/test_storage.py` | Not started |
| ING-04 | Store under non-public data dir with generated names; verify resolved path stays in storage root | TRD §6.1, §11 | M1 | `modules/documents/storage.py` | path-traversal test | Not started |
| ING-05 | Create document + ingestion_job (queued); return 202 with job id | TRD §6.1, §8 | M1 | `api/v1/documents.py` | `tests/api/test_documents_upload.py` | Not started |
| ING-06 | Extract text with page numbers and heading paths; reject empty extraction with useful error | TRD §6.1; PRD §5.2 | M2 | `modules/documents/extraction/` | `tests/unit/extraction/` | Not started |
| ING-07 | Normalise text without destroying tables/code/headings/IDs; keep original extracted text | TRD §6.1 | M2 | `modules/documents/normalize.py` | unit tests | Not started |
| ING-08 | Chunk metadata: document_id, chunk_index, page range, section path, char/token counts, strategy, content hash | TRD §6.1, §7 | M2 | `modules/documents/chunking/` | unit tests | Not started |
| ING-09 | Batched local embeddings; validate dimension and finite values | TRD §6.1, §12 | M3 | `modules/models/embedding.py` | `tests/unit/models/test_embedding_validation.py` | Not started |
| ING-10 | Transactional chunk+vector write; ready only after all committed; cleanup/fail with retry-safe semantics | TRD §6.1, §12 | M2/M3 | `workers/ingestion.py` | `tests/integration/test_ingestion_atomicity.py` | Not started |
| ING-11 | Expose progress and per-document counts; states queued/extracting/chunking/embedding/ready/failed | TRD §6.1; PRD §5.2 | M2 | `api/v1/jobs.py`, Library UI | `tests/api/test_jobs.py` | Not started |
| ING-12 | Duplicate SHA-256 detection with skip / re-index / new-version choices | TRD §6.1; PRD §5.2 | M1 | `modules/documents/service.py`, upload UI | `tests/api/test_duplicate_upload.py` | Not started |
| ING-13 | Retry failed ingestion; delete with confirmation (idempotent, ownership check) | PRD §5.2; TRD §8 | M1/M2 | `api/v1/documents.py` | `tests/api/test_documents_delete.py` | Not started |
| ING-14 | Library shows name, type, size, upload date, pages, chunks, plain-language last error | PRD §5.2 | M1 | `apps/web/src/app/library/` | Vitest + Playwright | Not started |
| ING-15 | If page extraction unavailable, state citation granularity is section/document level | PRD §5.2 | M2 | extraction metadata + UI | unit test | Not started |
| ING-16 | Parser timeouts; page and extracted-character limits | TRD §11, §12 | M2 | extraction module | unit test | Not started |
| ING-17 | Stale running jobs recoverable after worker restart; idempotent retries | TRD §12; PRD §9 | M2 | `workers/` | `tests/integration/test_worker_restart.py` | Not started |
| ING-18 | Chunk inspection (detail drawer: extraction preview, checksum, chunk sample) | PRD §7 M2; DRD §7.2 | M2 | `GET /documents/{id}/chunks`, Library drawer | API + UI test | Not started |

## 5. RAG query & chat (TRD §6.2, PRD §5.3)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| RAG-01 | Validate request, workspace ownership, document filters | TRD §6.2 | M4 | `api/v1/chat.py` | `tests/api/test_chat_query.py` | Not started |
| RAG-02 | Structured query classification only when needed (normal / out-of-scope / clarification) | TRD §6.2 | M4 | `modules/rag/classify.py` | unit test | Not started |
| RAG-03 | Embed query with same model as indexed chunks | TRD §6.2 | M4 | `modules/retrieval/dense.py` | unit test asserting embedding_version match | Not started |
| RAG-04 | Dense top-N via pgvector with filters applied before return | TRD §6.2 | M4 | `modules/retrieval/dense.py` | `tests/integration/test_dense.py` | Not started |
| RAG-05 | Lexical top-N via Postgres FTS | TRD §6.2 | M5 | `modules/retrieval/lexical.py` | `tests/integration/test_lexical.py` | Not started |
| RAG-06 | Reciprocal Rank Fusion; store strategy, candidate IDs and ranks | TRD §6.2, §9 | M5 | `modules/retrieval/fusion.py` | `tests/unit/retrieval/test_rrf.py` | Not started |
| RAG-07 | Optional rerank top 20–50; context budget; dedupe overlapping chunks | TRD §6.2 | M5 | `modules/retrieval/rerank.py`, `modules/rag/context.py` | unit tests | Not started |
| RAG-08 | Abstain below calibrated threshold / no useful sources ("No supporting source found") | TRD §6.2; PRD §5.3; DRD §11 | M4 | `modules/rag/abstain.py` | `tests/unit/rag/test_abstention.py` | Not started |
| RAG-09 | Answer only from supplied evidence; citations reference chunk ids; backend maps to title/page/section | TRD §6.2 | M4 | `modules/rag/citations.py` | `tests/unit/rag/test_citation_mapping.py` | Not started |
| RAG-10 | Validate response schema; every citation refers to a retrieved chunk | TRD §6.2, §17 | M4 | `modules/rag/citations.py` | same | Not started |
| RAG-11 | Return answer + citations + abstained + retrieval trace + request_id | TRD §8 | M4 | `schemas/chat.py` | contract test | Not started |
| RAG-12 | Record latency, model, strategy, source ids, error, feedback; no secrets/raw prompts in logs | TRD §6.2 | M4 | `query_metrics` table | unit test | Not started |
| RAG-13 | Ask across all ready docs or a selected subset | PRD §5.3 | M4 | chat UI scope control | Playwright | Not started |
| RAG-14 | Inline numbered citations; click opens source drawer with doc name, page/section, exact excerpt | PRD §5.3; DRD §7.3 | M4 | `apps/web/src/components/citations/` | Vitest + Playwright | Not started |
| RAG-15 | "Sources used" area + optional "How this was found" panel | PRD §5.3 | M4/M5 | chat UI | Vitest | Not started |
| RAG-16 | Conflicting sources: present the conflict and cite both | PRD §5.3 | M4 | RAG prompt + eval case | eval case `conflict-*` | Not started |
| RAG-17 | Conversation history; rename/delete conversations | PRD §5.3; TRD §8 | M4 | `api/v1/conversations.py` | API tests | Not started |
| RAG-18 | Helpful / not helpful feedback with optional reason, stored | PRD §5.3 | M4 | `message_feedback` table | API test | Not started |
| RAG-19 | Disclose limited passage retrieval; never claim it "read all documents" | PRD §5.3; DRD §11 | M4 | UI copy | content review | Not started |
| RAG-20 | `POST /chat/clarify` resumes a pending ambiguous query | TRD §8 | M4 | `api/v1/chat.py` | API test | Not started |
| RAG-21 | Non-streaming first; streaming only after stable (P2) | TRD §8; PRD §8 | P2 | — | — | Deferred (P2) |

## 6. Evaluation Lab (TRD §9, PRD §5.4)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| EVL-01 | Strategies S1 fixed+dense, S2 recursive+dense, S3 S2+lexical+RRF, S4 S3+reranker | TRD §9 | M5 | `modules/evaluation/strategies.py` | `tests/unit/eval/test_strategies.py` | Not started |
| EVL-02 | Create dataset; import CSV/JSONL with row-level error report | TRD §8; PRD §5.4 | M5 | `api/v1/evaluations.py` | `tests/api/test_eval_import.py` | Not started |
| EVL-03 | Ship small synthetic/public sample dataset + guide for a verified 50–150 question set | PRD §5.4; TRD §9 | M5 | `data-seed/eval/`, `docs/evaluation/dataset-guide.md` | — | Not started |
| EVL-04 | Dataset covers factual, exact-ID, multi-hop, table, unanswerable, conflicting, prompt-injection cases | TRD §9; PRD §10 | M5/M7 | sample dataset | dataset lint test | Not started |
| EVL-05 | Dev / held-out split; never tune on held-out | TRD §9 | M5 | `evaluation_cases.tags` | dataset lint test | Not started |
| EVL-06 | Config: chunking, retrieval, top-k, RRF k, reranker, model, prompt version | PRD §5.4; DRD §7.5 | M5 | Eval config schema + UI | contract test | Not started |
| EVL-07 | Async run via worker with progress; safe navigation away | TRD §8; PRD §5.4; DRD §7.5 | M5 | `workers/evaluation.py` | integration test | Not started |
| EVL-08 | Metrics: Recall@K, Precision@K, MRR, nDCG@K | TRD §9 | M5 | `modules/evaluation/metrics.py` | `tests/unit/eval/test_metrics.py` (hand-computed fixtures) | Not started |
| EVL-09 | Answer correctness, faithfulness, citation precision — judge-based labelled as estimates + manual review | TRD §9; PRD §5.4 | M5 | `modules/evaluation/judge.py` | unit test | Not started |
| EVL-10 | Abstention accuracy | TRD §9 | M5 | metrics module | unit test | Not started |
| EVL-11 | Latency p50/p95 end-to-end and per stage; resource profile where measurable | TRD §9 | M5 | metrics module | unit test | Not started |
| EVL-12 | Side-by-side run comparison (table primary, charts secondary) | PRD §5.4; DRD §7.5 | M5 | Eval Lab UI | Playwright | Not started |
| EVL-13 | Per-case inspection split view (expected vs retrieved, answer, failure category) | PRD §5.4; DRD §7.5 | M5 | Eval Lab UI | Playwright | Not started |
| EVL-14 | Export CSV/JSON report with config + dataset version | PRD §5.4 | M5 | `GET /evaluations/runs/{id}/export` | API test | Not started |
| EVL-15 | CI runs deterministic tests + small smoke evaluation only | TRD §9 | M5/M8 | CI workflow | CI | Not started |
| EVL-16 | Benchmark report: model, hardware, dataset version, settings, measured metrics, sample count | TRD §9, §17; PRD §11 | M8 | `docs/evaluation/report.md` | doc review | Not started |

## 7. Text-to-SQL (TRD §6.3, §10; PRD §5.5)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| SQL-01 | Synthetic demo DB: customers, orders, order_items, payments, products + visible glossary; edge cases (refunds, duplicate names, nulls, dates) | PRD §5.5, §10; TRD §10 | M6 | `infra/postgres/demo_seed/` | seed test | Not started |
| SQL-02 | One user-configured local Postgres connection; secret write-only, never returned | PRD §5.5; TRD §7, §8 | M6 | `api/v1/sql.py` | `tests/api/test_sql_connections.py` | Not started |
| SQL-03 | Introspect only allowlisted schemas/tables/columns; never send credentials to LLM | TRD §6.3 | M6 | `modules/sql_assistant/schema.py` | unit test | Not started |
| SQL-04 | Ambiguity classifier: ready / clarification_required / unsupported / unsafe + confidence + missing concept | TRD §10 | M6 | `modules/sql_assistant/clarify.py` | unit test | Not started |
| SQL-05 | Clarification: 2–4 options, preserves original question, requires explicit selection | TRD §10; PRD §5.5 | M6 | same + UI panel | Playwright Journey C | Not started |
| SQL-06 | User-configurable, visible semantic glossary | TRD §10 | M6 | `sql_glossary` table + UI | API test | Not started |
| SQL-07 | Strict Pydantic SQL output: sql, assumptions, explanation, referenced tables | TRD §6.3 | M6 | `schemas/sql.py` | unit test | Not started |
| SQL-08 | SQLGlot AST: exactly one SELECT / read-only CTE; reject DML/DDL/COPY/txn, multi-stmt, unapproved schemas, system catalogs, dangerous functions | TRD §6.3, §10 | M6 | `modules/sql_assistant/validate.py` | `tests/unit/sql/test_validator.py` (attack corpus) | Not started |
| SQL-09 | Execute via SELECT-only role; statement_timeout 5s, lock_timeout, row cap 500 | TRD §6.3, §10 | M6 | `modules/sql_assistant/execute.py` | `tests/integration/test_readonly_role.py` | Not started |
| SQL-10 | Never auto-execute after ambiguous/failed generation | TRD §6.3, §17 | M6 | orchestrator | unit test | Not started |
| SQL-11 | Summarise only after success; distinguish DB facts from model interpretation | TRD §6.3 | M6 | `modules/sql_assistant/summarize.py` | unit test | Not started |
| SQL-12 | Store generated SQL + safety decision; redact credentials and sensitive literals | TRD §10 | M6 | `sql_query_log` table | unit test | Not started |
| SQL-13 | UI: schema browser, clarification panel, read-only SQL code panel with copy, explicit run control with read-only badge + DB name, sortable results table, duration + row count | PRD §5.5; DRD §7.4 | M6 | `apps/web/src/app/sql/` | Playwright | Not started |
| SQL-14 | Safe failure messages for rejected/timeout queries; allow revised question | PRD §5.5, Journey C | M6 | API errors + UI | API test | Not started |

## 8. Models & Settings (PRD §5.6, DRD §7.6)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| SET-01 | Show Ollama status and installed local models | PRD §5.6; TRD §8 | M3 | `GET /settings/models`, Settings page | API test | Not started |
| SET-02 | Select generation + embedding model from installed compatible models | PRD §5.6 | M3 | Settings page | Playwright | Not started |
| SET-03 | Validate availability, schema output and embedding dimension before saving | PRD §5.6; TRD §8 | M3 | `POST /settings/models/validate` | API test | Not started |
| SET-04 | Strong warning that changing embedding model requires full re-embedding; never mix dimensions | PRD §5.6; TRD §4.2; DRD §7.6 | M3 | Settings page + embedding_versions | unit test | Not started |
| SET-05 | Reranker optional toggle with resource warning | PRD §5.6 | M5 | Settings page | Vitest | Not started |
| SET-06 | Copyable setup commands (`ollama pull qwen3:4b`, `ollama pull nomic-embed-text`, reranker install) | PRD §5.6; DRD §7.6 | M3 | Settings page | Vitest | Not started |
| SET-07 | Model size/resource notes only when verified from runtime metadata | DRD §7.6; PRD §5.1 | M3 | Settings page | unit test | Not started |
| SET-08 | No cloud provider cards, pricing or API-key fields | DRD §7.6 | M3 | Settings page | content review | Not started |

## 9. Workspace, onboarding, activity (PRD §4, §5.1)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| WSP-01 | First-launch setup checklist: DB connected, Ollama reachable, generation model, embedding model | PRD §5.1, Journey A | M0/M3 | `components/system-status/readiness-panel.tsx` | `readiness-panel.test.tsx` | Done |
| WSP-02 | Default local workspace auto-created; rename; no forced registration | PRD §5.1 | M1 | migration seed + `PATCH /workspaces/{id}` | API test | Not started |
| WSP-03 | Guided, clearly labelled sample dataset (public-domain/synthetic); sources tracked in `docs/demo-data-sources.md` | PRD §5.1, §10 | M5/M8 | `data-seed/`, docs | — | Not started |
| WSP-04 | Never imply optional reranker is required | PRD §5.1 | M3 | UI copy | content review | Not started |
| WSP-05 | Overview: readiness row, real metrics only, recent activity, working quick actions | PRD §4; DRD §7.1 | M0→M5 | `apps/web/src/app/page.tsx` (readiness only; metrics/activity/actions arrive with M1+) | Vitest + Playwright | Partial |
| WSP-06 | Activity/Logs: ingestion jobs, failures, request ids, safe logs, latency | PRD §4 | M7 | Activity page + `audit_events` | Playwright | Not started |

## 10. API contract (TRD §8)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| API-01 | All endpoints under `/api/v1` | TRD §8 | M0 | `apps/api/app/api/v1/__init__.py` | `tests/api/` | Done |
| API-02 | Stable error codes + human detail + request_id; never stack traces | TRD §8, §11; DRD §11 | M0 | `core/errors.py` | `tests/api/test_errors.py` | Done |
| API-03 | `GET /health/live` → 200 `{status:'ok'}` | TRD §8 | M0 | `api/v1/health.py` | `tests/api/test_health.py` | Done |
| API-04 | `GET /health/ready` → 200/503 with separate DB & Ollama status, no secrets | TRD §8, §12 | M0 | `api/v1/health.py`, `core/readiness.py` | `tests/api/test_health.py` | Done |
| API-05 | Paginated list endpoints (documents, conversations) | TRD §8 | M1/M4 | `schemas/common.py` | API tests | Not started |

## 11. Security & privacy (TRD §11)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| SEC-01 | Malicious upload controls (allowlist, signature, size/page limits, parser timeouts, no static serving) | TRD §11 | M1/M2/M7 | documents module | `tests/security/test_uploads.py` | Not started |
| SEC-02 | Prompt-injection: evidence delimited, policy to ignore document instructions, adversarial corpus tests | TRD §11; PRD §10 | M4/M7 | RAG prompts | `tests/security/test_prompt_injection.py` + eval cases | Not started |
| SEC-03 | Workspace filter on every document/chunk/conversation/eval query + authorization tests | TRD §11 | M1→M7 | repositories | `tests/integration/test_workspace_isolation.py` | Not started |
| SEC-04 | Secrets via env, `.env` ignored, `.env.example` placeholders, never logged, redacted | TRD §11, §15 | M0 | `.gitignore`, `.env.example`, `core/logging.py` redaction, CI `policy` job | `tests/unit/test_logging.py` | Done |
| SEC-05 | No direct execution of model output; bounded retries | TRD §11 | M4/M6 | structured output module | unit test | Not started |
| SEC-06 | Path traversal protection | TRD §11 | M1 | storage service | `tests/unit/documents/test_storage.py` | Not started |
| SEC-07 | DoS: upload limits, rate/concurrency limits, timeouts, bounded context/top-k | TRD §11, §12 | M1→M7 | config + middleware | unit tests | Not started |
| SEC-08 | Log IDs and metrics, not document text or credentials; configurable retention | TRD §11 | M0/M7 | `core/logging.py` (IDs/metrics only, redaction); retention at M7 | unit test | Partial |
| SEC-09 | SQL result cells treated as data, never as instructions | TRD §11 | M6 | summarize prompt | unit test | Not started |
| SEC-10 | Audit events for significant actions | TRD §7; PRD §7 M7 | M7 | `audit_events` | integration test | Not started |

## 12. Reliability & performance (TRD §12)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| REL-01 | UI responsive during async ingestion/evaluation | TRD §12; PRD §9 | M2/M5 | worker + polling UI | Playwright | Not started |
| REL-02 | Bounded upload size, pages, chars, chunk count, context tokens, candidates, SQL rows | TRD §12 | M1→M6 | `core/config.py` limits | unit tests | Not started |
| REL-03 | Indexes on workspace_id, document_id, status, created_at, FTS | TRD §12 | M1/M5 | migrations | migration test | Not started |
| REL-04 | Every long op: timeout, state transition, safe error, idempotent retry | TRD §12 | M2 | workers | integration tests | Not started |
| REL-05 | Graceful shutdown; stale job recovery | TRD §12 | M2 | workers | `tests/integration/test_worker_restart.py` | Not started |
| REL-06 | Separate health checks for PostgreSQL and Ollama | TRD §12 | M0 | `core/readiness.py` | `tests/api/test_health.py` | Done |

## 13. Design system & UX (DRD)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| DES-01 | Colour tokens exactly as DRD §2 table, central CSS variables mapped to Tailwind/shadcn | DRD §2, §14 | M0 | `apps/web/src/app/globals.css` | `src/lib/tokens.test.ts` | Done |
| DES-02 | Light theme primary; dark only after light is complete; no gradients; no pure black; accent ≈5–10% | DRD §2 | M0 | `globals.css` (no `.dark`, no gradients) | `src/lib/tokens.test.ts` | Done |
| DES-03 | Typography: one sans family (Inter/Geist via next/font), mono for technical values, tabular numerals, DRD scale | DRD §3 | M0 | `layout.tsx` (geist package, self-hosted), `globals.css` | visual check (headless Edge screenshots) | Done |
| DES-04 | Layout: sidebar 232–248px, top bar 56–64px, max width ~1440px, 4px spacing, radius 10–12 cards / 8 controls, 1px low-contrast borders, shadows only on overlays | DRD §4 | M0 | `components/shell/app-shell.tsx` | visual check at 390/820/1440px | Done |
| DES-05 | Lucide icons only, 16–20px nav, stroke 1.75–2px, DRD icon mapping, no emoji | DRD §5 | M0 | `components/shell/nav-items.ts` | code review | Done |
| DES-06 | SVG wordmark + app icon (page/evidence-node motif, no gradients) | DRD §2, §14 | M0 | `components/brand/logo.tsx`, `app/icon.svg` | visual check | Done |
| DES-07 | Sidebar: wordmark, workspace name, primary + secondary nav, teal-tint active state, mobile drawer | DRD §6.1 | M0 | `components/shell/sidebar-nav.tsx`, `app-shell.tsx` | `sidebar-nav.test.tsx` | Done |
| DES-08 | Top bar: page title, real system status indicator, help link; no decorative search | DRD §6.2 | M0 | `components/shell/app-shell.tsx` | Vitest | Done |
| DES-09 | Component library variants (Button, Status badge, Data table, Citation chip, Source drawer, Metric card, Code block, Dropzone, Clarification panel, Toast, Skeleton, Dialog) | DRD §8 | M0→M6 | Button, StatusBadge, Skeleton, Sheet, Tooltip done; rest per milestone | Vitest per component | Partial |
| DES-10 | Motion 120–180ms / 180–240ms; no decorative motion; respect prefers-reduced-motion | DRD §9 | M0 | `globals.css` | CSS review | Done |
| DES-11 | No optimistic completion of ingestion/evaluation; destructive actions confirmed | DRD §9 | M1+ | UI | Playwright | Not started |
| DES-12 | Keyboard: tab order, Enter/Space, Escape, focus trap, visible focus ring | DRD §9; PRD §9 | M0→M7 | skip link, focus ring, Radix primitives; Playwright a11y at M7 | Playwright a11y | Partial |
| DES-13 | Responsive behaviour at 1440+/1024/768/<768 per DRD §10 | DRD §10 | M0→M7 | manual 390/820/1440px screenshots; Playwright at M7 | Playwright multi-viewport screenshots | Partial |
| DES-14 | WCAG 2.2 AA contrast, visible labels, icon-only names, status not by colour alone, semantic tables, chart summaries | DRD §11; PRD §9 | M0→M7 | contrast measured + rules in design-system.md | `src/lib/tokens.test.ts` | Partial |
| DES-15 | Plain language, no anthropomorphic claims, errors explain recovery | DRD §11 | all | UI copy | content review | Not started |
| DES-16 | Every screen: loading, empty, success, error, disabled, partial, offline/model-unavailable states | DRD §13; Phase 6 brief | all | Overview readiness implements loading/error/degraded/ready/disabled | Vitest/Playwright per page | Partial |
| DES-17 | `docs/design-system.md` (tokens, type, spacing, icons, states) | DRD §14 | M0 | `docs/design-system.md` | — | Done |
| DES-18 | README screenshots: Overview, Library, Ask w/ citations, Eval Lab, SQL Analyst | DRD §14; PRD §11 | M8 | README | — | Not started |
| DES-19 | Recharts only where comparison benefits; neutral palette, direct labels, not red/green-only | DRD §7.5, §12 | M5 | Eval Lab | visual review | Not started |
| DES-20 | No dead buttons or fake data cards | DRD §15 | all | unbuilt nav items disabled with explanation (ADR-000 G-7) | Playwright | In progress |

## 14. Delivery, repository & release (PRD §7, §11, §12; TRD §14, §16, §17)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| REP-01 | Repo structure per TRD §14 | TRD §14 | M0 | repo layout | — | Partial |
| REP-02 | README, docs, issue/PR templates, .gitignore, .env.example, branch strategy, lint/format configs | PRD §7 M0 | M0 | README, `.github/` templates, `.env.example`, `docs/branch-strategy.md`, ruff/eslint/prettier configs | — | Done |
| REP-03 | TRD/PRD/DRD stored in docs/ and matching implemented product | PRD §11; TRD §14 | M0/M8 | `docs/TRD.md`, `PRD.md`, `DRD.md` via `scripts/specs_to_md.py` | — | Done |
| REP-04 | ADR-001 … ADR-007 | TRD §16; PRD §11 | M0→M6 | ADR-000, -001 (proposed), -007, -008 | — | Partial |
| REP-05 | Feature branch per milestone; conventional commits; no force-push/history rewrite | PRD §12 | all | git | — | In progress |
| REP-06 | Clean clone starts with documented commands; Ollama setup explicit | TRD §17; PRD §13 | M0/M8 | README + `scripts/dev.ps1`, `scripts/db.ps1` | fresh-clone check 2026-11-06 (see implementation-status) | Done |
| REP-07 | Migrations run from empty DB and upgrade from previous release | PRD §11; TRD §17 | M1/M8 | Alembic | CI migration job | Not started |
| REP-08 | Reproducible, clearly synthetic/public demo seed | PRD §11 | M8 | `scripts/seed_demo.py` | seed test | Not started |
| REP-09 | Demo video, release tag only after acceptance checks | PRD §7 M8, §11 | M8 | — | — | Not started |
| REP-10 | Makefile (TRD §14) — plus PowerShell equivalents for Windows | TRD §14 | M0 | `Makefile`, `scripts/dev.ps1`, `scripts/db.ps1` | — | Done |
