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
| CON-01 | Zero paid inference APIs; LLM, embedding, reranking run locally by default | TRD §1, §4; PRD §2.1 | M3 | `apps/api/app/modules/models/` (Ollama only); `scripts/check_no_paid_apis.py` | CI `policy` job; `tests/unit/test_ollama_adapter.py` | Done |
| CON-02 | No API key / credit card / hosted endpoint required for core functionality | TRD §1; PRD §9 Privacy | M0–M8 | `.env.example` contains no provider keys | `scripts/check_no_paid_apis.py`; `.env.example` has no key variables | Done |
| CON-03 | Do not claim free weights = zero compute cost; document real resource cost | TRD §1, §13 | M0 | `docs/decisions/ADR-007-local-only-cost-boundary.md` | doc review | Done |
| CON-04 | No invented quality claims or benchmark numbers; unmeasured = NOT MEASURED | TRD §1, §9; PRD §2.2 | M5 | `docs/evaluation/README.md` (measured or NOT MEASURED) | doc review | Done |
| CON-05 | Build in vertical slices; no empty placeholder modules | TRD §1; PRD §7 | all | repo-wide; modules added per milestone | code review | Done |
| CON-06 | Provider-agnostic interfaces `ChatModel`, `EmbeddingModel`, `Reranker`; ship Ollama adapters only | TRD §4 | M3 | `apps/api/app/modules/models/interfaces.py`, `ollama.py`, `registry.py`, `reranker.py` | `apps/api/tests/unit/test_ollama_adapter.py` | Done |
| CON-07 | Missing model → show setup command; never silently switch to paid endpoint | TRD §4.3; PRD §5.6 | M3 | `apps/api/app/modules/models/ollama.py` (model_missing → pull command), readiness, Settings | `apps/api/tests/unit/test_ollama_adapter.py`, `apps/api/tests/integration/test_local_models.py` | Done |
| CON-08 | Single-user local mode; keep `workspace_id` ownership boundaries in data model | TRD §2 | M1 | `apps/api/app/db/models.py` (workspace_id on all content) | `apps/api/tests/integration/test_workspace_isolation.py`, `test_activity_and_security.py` | Done |
| CON-09 | Feature flags: semantic chunking, reranker, streaming, SQL assistant; disabled feature never breaks core RAG | TRD §15 | M2–M6 | `ENABLE_RERANKER` flag + per-request `rerank`; semantic chunking and streaming not built (no flag needed yet); SQL Analyst is separate from RAG | `apps/api/tests/integration/test_evaluation.py` (S4 refused without reranker) | Partial |
| CON-10 | No automatic model downloads at runtime | TRD §2 out-of-scope | M3 | models are only probed (`/api/tags`, `/api/embed`), never pulled | code review; `grep pull` shows only user-facing commands | Done |

## 2. Technology stack

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| STK-01 | Next.js App Router + TypeScript (strict) | TRD §3, §15 | M0 | `apps/web/` (Next.js 16.4.5, `strict: true`) | `npm run typecheck` | Done |
| STK-02 | Tailwind CSS + customised shadcn/ui + lucide-react; no second UI library | TRD §3; DRD §12 | M0 | `apps/web/src/components/ui/` (shadcn radix-nova, customised tokens) | code review | Done |
| STK-03 | Python 3.12+ FastAPI backend | TRD §3 | M0 | `apps/api/app/main.py` | `tests/api/test_health.py` | Done |
| STK-04 | Pydantic v2 at all boundaries (API, model output, config) | TRD §3, §15 | M0+ | Pydantic schemas for every API contract, model output (`ModelAnswer`, `ModelSqlOutput`) and settings | API + unit tests | Done |
| STK-05 | PostgreSQL 16+ as system of record | TRD §3, §5 | M0 | native: `scripts/db.ps1` (PG 16.15); Docker/CI: `pgvector/pgvector:pg16` | `tests/integration/test_postgres_ready.py` | Done |
| STK-06 | pgvector extension; exact search baseline, HNSW only after measurement | TRD §3, §12 | M3 | `apps/api/app/db/models.py` `ChunkEmbedding` (untyped vector), exact cosine `apps/api/app/modules/retrieval/dense.py` | `apps/api/tests/integration/test_local_models.py` | Done |
| STK-07 | Postgres FTS (`tsvector`, `ts_rank_cd`) lexical retrieval | TRD §3 | M5 | `apps/api/app/modules/retrieval/lexical.py` (generated `search_tsv`, GIN, OR-of-terms) | `apps/api/tests/integration/test_ingestion_worker.py` | Done |
| STK-08 | Ollama local runtime | TRD §3 | M3 | `apps/api/app/modules/models/ollama.py` | `apps/api/tests/unit/test_ollama_adapter.py`, `integration/test_real_ollama.py` (opt-in) | Done |
| STK-09 | Generation: `qwen3:4b` (low-resource) / `qwen3:8b` (recommended); pinned tag + recorded digest | TRD §4.1 | M4 | `.env.example` pins `qwen3:4b`; digest in ADR-001 and every evaluation run config | evaluation run `config.generation` | Done |
| STK-10 | Embedding: `nomic-embed-text` pinned; dimension probed at startup and persisted | TRD §4.2, §7, §17 | M3 | `apps/api/app/modules/models/registry.py` (probe), `embedding_versions` table | `apps/api/tests/integration/test_local_models.py` | Done |
| STK-11 | Optional reranker `BAAI/bge-reranker-v2-m3` via Sentence Transformers, lazy loaded, `ENABLE_RERANKER=false` default | TRD §3, §4.2 | M5 | `apps/api/app/modules/models/reranker.py` (lazy CrossEncoder, optional extra) | `apps/api/tests/unit/test_evaluation_metrics.py`, `integration/test_evaluation.py` | Partial (not installed / not measured, ADR-004) |
| STK-12 | Custom chunking strategies (fixed, recursive, semantic experiment) | TRD §3 | M2 | `apps/api/app/modules/documents/chunking.py` (fixed, recursive) | `apps/api/tests/unit/documents/test_chunking.py` | Partial (semantic experiment not built, ADR-005) |
| STK-13 | SQLGlot AST validation + dedicated read-only Postgres role | TRD §3, §10 | M6 | `apps/api/app/modules/sql_assistant/validation.py`, `demo.py` (read-only role) | `apps/api/tests/unit/test_sql_validation.py`, `integration/test_sql_analyst.py` | Done |
| STK-14 | Postgres-backed job table + one worker process (no Redis/Celery) | TRD §3 | M2 | `apps/api/app/workers/ingestion.py` (+ evaluation runs) | `apps/api/tests/integration/test_ingestion_worker.py` | Done |
| STK-15 | Pytest + HTTPX; Vitest; Playwright | TRD §3 | M0/M7 | pytest + HTTPX TestClient, Vitest, Playwright (`apps/web/e2e/`) | `dev.ps1 check`, `npm run e2e` | Done |
| STK-16 | Custom gold-set evaluator; Ragas optional and supplementary only | TRD §3 | M5 | `apps/api/app/modules/evaluation/` (deterministic metrics; no Ragas) | `apps/api/tests/unit/test_evaluation_metrics.py` | Done |
| STK-17 | Structured JSON logs + request_id + local metrics table; no external telemetry | TRD §3 | M0 | JSON logs + request_id; per-answer metrics in `messages.metadata` (G-3); `audit_events` | `apps/api/tests/unit/test_logging.py`, `test_log_redaction.py` | Done |
| STK-18 | Docker Compose for Postgres; native + Docker Ollama options documented | TRD §3, §13 | M0 | `infra/docker-compose.yml` (validated in CI, not run locally — ADR-008) | CI `compose` job | Partial |
| STK-19 | GitHub Actions: lint, typecheck, tests, migration check, build; never download LLMs | TRD §3, §9 | M0 | `.github/workflows/ci.yml` (lint, types, migrations + `alembic check`, tests, build, Playwright) | CI | Partial (never run: no GitHub remote) |
| STK-20 | SQLAlchemy 2.x + Alembic; never `create_all` at startup | TRD §15 | M1 | `apps/api/app/db/`, `apps/api/alembic/` (7 migrations) | `apps/api/tests/integration/test_migrations.py` | Done |
| STK-21 | ruff + mypy (Python); ESLint + TS strict (web) | TRD §15 | M0 | `pyproject.toml`, `eslint.config.mjs` | `ruff`, `mypy --strict`, `eslint`, `tsc` | Done |

## 3. Model runtime contract (TRD §4.3)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| MOD-01 | Startup health-check of Ollama and required models | TRD §4.3 | M0/M3 | `apps/api/app/core/readiness.py` (runtime, models, schema, worker; busy-aware) | `apps/api/tests/unit/test_readiness.py` | Done |
| MOD-02 | Bounded timeouts, concurrency limits, cancellation for model calls | TRD §4.3, §12 | M3 | `apps/api/app/modules/models/ollama.py` (timeouts, 5xx retry), `gate.py` (concurrency cap) | `apps/api/tests/unit/test_ollama_adapter.py`, `integration/test_chat.py` | Done |
| MOD-03 | Temperature 0–0.2 for extraction/SQL; moderate only for prose | TRD §4.3 | M4/M6 | RAG temperature 0.1, SQL 0.0, probe 0 | `apps/api/tests/unit/test_ollama_adapter.py`, `integration/test_chat.py` | Done |
| MOD-04 | Structured output: Ollama JSON schema + independent Pydantic validation; invalid = recoverable error | TRD §4.3, §11 | M4 | JSON Schema `format` + Pydantic (`apps/api/app/modules/rag/answer.py`, `sql_assistant/assistant.py`) | `apps/api/tests/unit/test_rag_answer.py` | Done |
| MOD-05 | Separate versioned system prompts per task (RAG, classify, clarify, SQL, eval) | TRD §4.3, §15 | M4 | `apps/api/app/modules/rag/prompts.py` (`rag-answer-v2`), `sql_assistant/assistant.py` (`sql-v3`) | prompt_version asserted in chat/SQL tests | Done |
| MOD-06 | Record model tag, quantization, runtime version, temperature, context, machine profile per benchmark run | TRD §4.3, §9 | M5 | `apps/api/app/modules/evaluation/runner.py` (`config` incl. machine profile) | `apps/api/tests/integration/test_evaluation.py` | Done |

## 4. Document ingestion (TRD §6.1, PRD §5.2)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| ING-01 | Support PDF (text), DOCX, TXT, MD; reject others | TRD §2; PRD §5.2 | M1 | `apps/api/app/modules/documents/validation.py` | `apps/api/tests/unit/documents/test_validation.py` | Done |
| ING-02 | Enforce size, extension, MIME and file-signature checks | TRD §6.1, §11 | M1 | `apps/api/app/modules/documents/validation.py`, `core/upload_limit.py` | `apps/api/tests/unit/documents/test_validation.py`, `api/test_documents_upload.py` | Done |
| ING-03 | UUID + SHA-256 checksum per upload | TRD §6.1 | M1 | `apps/api/app/modules/documents/storage.py` | `apps/api/tests/unit/documents/test_storage.py` | Done |
| ING-04 | Store under non-public data dir with generated names; verify resolved path stays in storage root | TRD §6.1, §11 | M1 | `apps/api/app/modules/documents/storage.py` | `apps/api/tests/unit/documents/test_storage.py` | Done |
| ING-05 | Create document + ingestion_job (queued); return 202 with job id | TRD §6.1, §8 | M1 | `apps/api/app/api/v1/documents.py` | `apps/api/tests/api/test_documents_upload.py` | Done |
| ING-06 | Extract text with page numbers and heading paths; reject empty extraction with useful error | TRD §6.1; PRD §5.2 | M2 | `apps/api/app/modules/documents/extraction.py` | `apps/api/tests/unit/documents/test_extraction.py` | Done |
| ING-07 | Normalise text without destroying tables/code/headings/IDs; keep original extracted text | TRD §6.1 | M2 | `extraction.normalize`; sections kept in `document_sections` | `apps/api/tests/unit/documents/test_extraction.py` | Done |
| ING-08 | Chunk metadata: document_id, chunk_index, page range, section path, char/token counts, strategy, content hash | TRD §6.1, §7 | M2 | `apps/api/app/modules/documents/chunking.py`, `chunks` table | `apps/api/tests/unit/documents/test_chunking.py` | Done |
| ING-09 | Batched local embeddings; validate dimension and finite values | TRD §6.1, §12 | M3 | `apps/api/app/modules/models/embedding_stage.py` (batches, validation) | `apps/api/tests/integration/test_local_models.py` | Done |
| ING-10 | Transactional chunk+vector write; ready only after all committed; cleanup/fail with retry-safe semantics | TRD §6.1, §12 | M2/M3 | `apps/api/app/workers/ingestion.py` `_complete` (one transaction) | `apps/api/tests/integration/test_ingestion_worker.py`, `test_local_models.py` | Done |
| ING-11 | Expose progress and per-document counts; states queued/extracting/chunking/embedding/ready/failed | TRD §6.1; PRD §5.2 | M2 | `apps/api/app/api/v1/documents.py`, `jobs.py`; Library polling | `apps/api/tests/integration/test_ingestion_worker.py`; `library-view.test.tsx` | Done |
| ING-12 | Duplicate SHA-256 detection with skip / re-index / new-version choices | TRD §6.1; PRD §5.2 | M1 | `apps/api/app/modules/documents/service.py`, upload queue UI | `apps/api/tests/api/test_duplicate_upload.py` | Done |
| ING-13 | Retry failed ingestion; delete with confirmation (idempotent, ownership check) | PRD §5.2; TRD §8 | M1/M2 | `POST /documents/{id}/retry`, delete dialog | `apps/api/tests/api/test_documents_delete.py`, `integration/test_ingestion_worker.py` | Done |
| ING-14 | Library shows name, type, size, upload date, pages, chunks, plain-language last error | PRD §5.2 | M1 | `apps/web/src/components/library/` | `library-view.test.tsx`, Playwright smoke | Done |
| ING-15 | If page extraction unavailable, state citation granularity is section/document level | PRD §5.2 | M2 | `documents.citation_granularity`; drawer explains it | `test_ingestion_worker.py`, `library-view.test.tsx` | Done |
| ING-16 | Parser timeouts; page and extracted-character limits | TRD §11, §12 | M2 | child-process extraction with timeout; page/char limits | `apps/api/tests/unit/documents/test_extraction.py` | Done |
| ING-17 | Stale running jobs recoverable after worker restart; idempotent retries | TRD §12; PRD §9 | M2 | `apps/api/app/workers/ingestion.py` (heartbeat, stale recovery) | `apps/api/tests/integration/test_ingestion_worker.py` | Done |
| ING-18 | Chunk inspection (detail drawer: extraction preview, checksum, chunk sample) | PRD §7 M2; DRD §7.2 | M2 | `GET /documents/{id}/chunks`, `/extraction`; document drawer | `test_ingestion_worker.py`, `library-view.test.tsx` | Done |

## 5. RAG query & chat (TRD §6.2, PRD §5.3)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| RAG-01 | Validate request, workspace ownership, document filters | TRD §6.2 | M4 | `apps/api/app/modules/rag/service.py` | `apps/api/tests/integration/test_chat.py` | Done |
| RAG-02 | Structured query classification only when needed (normal / out-of-scope / clarification) | TRD §6.2 | M4 | not built: RAG answers or abstains (ADR-000 G-8) | — | Deferred (G-8) |
| RAG-03 | Embed query with same model as indexed chunks | TRD §6.2 | M4 | `query_embedder` uses the active `embedding_versions` row | `apps/api/tests/integration/test_local_models.py` | Done |
| RAG-04 | Dense top-N via pgvector with filters applied before return | TRD §6.2 | M4 | `apps/api/app/modules/retrieval/dense.py` | `apps/api/tests/integration/test_local_models.py`, `test_activity_and_security.py` | Done |
| RAG-05 | Lexical top-N via Postgres FTS | TRD §6.2 | M5 | `apps/api/app/modules/retrieval/lexical.py` | `apps/api/tests/integration/test_ingestion_worker.py` | Done |
| RAG-06 | Reciprocal Rank Fusion; store strategy, candidate IDs and ranks | TRD §6.2, §9 | M5 | `apps/api/app/modules/retrieval/fusion.py`; ranks in traces | `apps/api/tests/unit/test_evaluation_metrics.py` | Done |
| RAG-07 | Optional rerank top 20–50; context budget; dedupe overlapping chunks | TRD §6.2 | M5 | `reranker.py` (optional); `rag/answer.py` `pack_context` (dedupe + budget) | `apps/api/tests/unit/test_rag_answer.py` | Partial (reranker not measured) |
| RAG-08 | Abstain below calibrated threshold / no useful sources ("No supporting source found") | TRD §6.2; PRD §5.3; DRD §11 | M4 | `answer_question`: no sources / weak evidence (0.45 cosine) / model / unsupported | `apps/api/tests/unit/test_rag_answer.py` | Partial (threshold not calibrated on a human-verified set) |
| RAG-09 | Answer only from supplied evidence; citations reference chunk ids; backend maps to title/page/section | TRD §6.2 | M4 | `rag/answer.py` `verify_citations` + `service.citation_out` | `apps/api/tests/unit/test_rag_answer.py`, `integration/test_chat.py` | Done |
| RAG-10 | Validate response schema; every citation refers to a retrieved chunk | TRD §6.2, §17 | M4 | uncited answers become abstentions | `apps/api/tests/unit/test_rag_answer.py` | Done |
| RAG-11 | Return answer + citations + abstained + retrieval trace + request_id | TRD §8 | M4 | `apps/api/app/schemas/chat.py` `AnswerOut` | `apps/api/tests/integration/test_chat.py` | Done |
| RAG-12 | Record latency, model, strategy, source ids, error, feedback; no secrets/raw prompts in logs | TRD §6.2 | M4 | `messages.metadata` (G-3), `chat.answered` audit event; logs carry ids/counts only | `apps/api/tests/integration/test_chat.py`, `test_activity_and_security.py` | Done |
| RAG-13 | Ask across all ready docs or a selected subset | PRD §5.3 | M4 | `document_ids` scope; scope picker in Ask | `apps/api/tests/integration/test_chat.py` | Done |
| RAG-14 | Inline numbered citations; click opens source drawer with doc name, page/section, exact excerpt | PRD §5.3; DRD §7.3 | M4 | `apps/web/src/components/ask/answer-text.tsx`, `source-drawer.tsx` | `ask-view.test.tsx`, Playwright Journey A | Done |
| RAG-15 | "Sources used" area + optional "How this was found" panel | PRD §5.3 | M4/M5 | Sources used + How this was found | `ask-view.test.tsx` | Done |
| RAG-16 | Conflicting sources: present the conflict and cite both | PRD §5.3 | M4 | prompt rule 3; measured on q24 (both handbooks cited) | `docs/evaluation/README.md` | Done |
| RAG-17 | Conversation history; rename/delete conversations | PRD §5.3; TRD §8 | M4 | `/conversations` list/detail/rename/delete | `apps/api/tests/integration/test_chat.py` | Done |
| RAG-18 | Helpful / not helpful feedback with optional reason, stored | PRD §5.3 | M4 | `message_feedback`, `PUT /messages/{id}/feedback` | `apps/api/tests/integration/test_chat.py`, `ask-view.test.tsx` | Done |
| RAG-19 | Disclose limited passage retrieval; never claim it "read all documents" | PRD §5.3; DRD §11 | M4 | Ask page disclosure copy | content review | Done |
| RAG-20 | `POST /chat/clarify` resumes a pending ambiguous query | TRD §8 | M4 | not exposed (ADR-000 G-8); SQL has its own clarification | — | Deferred (G-8) |
| RAG-21 | Non-streaming first; streaming only after stable (P2) | TRD §8; PRD §8 | P2 | — | — | Deferred (P2) |

## 6. Evaluation Lab (TRD §9, PRD §5.4)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| EVL-01 | Strategies S1 fixed+dense, S2 recursive+dense, S3 S2+lexical+RRF, S4 S3+reranker | TRD §9 | M5 | `runner.PRESETS` S1–S4 | `apps/api/tests/integration/test_evaluation.py` | Partial (S4 not measured: reranker not installed) |
| EVL-02 | Create dataset; import CSV/JSONL with row-level error report | TRD §8; PRD §5.4 | M5 | `/evaluations/datasets`, `/cases/import` | `apps/api/tests/unit/test_evaluation_metrics.py`, `integration/test_evaluation.py` | Done |
| EVL-03 | Ship small synthetic/public sample dataset + guide for a verified 50–150 question set | PRD §5.4; TRD §9 | M5 | `samples/` + `docs/evaluation/dataset-guide.md` | `apps/api/tests/integration/test_evaluation.py` | Done |
| EVL-04 | Dataset covers factual, exact-ID, multi-hop, table, unanswerable, conflicting, prompt-injection cases | TRD §9; PRD §10 | M5/M7 | gold set tags: factual, exact-term, multi-hop, dated-conflict, unanswerable, injection | `scripts/build_gold_set.py` quote check | Partial (no table questions) |
| EVL-05 | Dev / held-out split; never tune on held-out | TRD §9 | M5 | `evaluation_cases.split`; every 4th case held out | `test_evaluation.py` | Done |
| EVL-06 | Config: chunking, retrieval, top-k, RRF k, reranker, model, prompt version | PRD §5.4; DRD §7.5 | M5 | `RunConfigIn` + Evaluation Lab configuration | `test_evaluation.py`, `evaluation-view.test.tsx` | Done |
| EVL-07 | Async run via worker with progress; safe navigation away | TRD §8; PRD §5.4; DRD §7.5 | M5 | worker executes runs, resumable; UI polls | `test_evaluation.py` | Done |
| EVL-08 | Metrics: Recall@K, Precision@K, MRR, nDCG@K | TRD §9 | M5 | `apps/api/app/modules/evaluation/metrics.py` | `apps/api/tests/unit/test_evaluation_metrics.py` (hand-computed) | Done |
| EVL-09 | Answer correctness, faithfulness, citation precision — judge-based labelled as estimates + manual review | TRD §9; PRD §5.4 | M5 | citation precision computed mechanically; no LLM judge; answer correctness/faithfulness NOT MEASURED | — | Partial |
| EVL-10 | Abstention accuracy | TRD §9 | M5 | `abstention_correct` | `test_evaluation.py` | Done |
| EVL-11 | Latency p50/p95 end-to-end and per stage; resource profile where measurable | TRD §9 | M5 | p50/p95 retrieval + total latency, per-stage timings; RAM at start only | `test_evaluation_metrics.py` | Partial (no peak RAM / tokens/s) |
| EVL-12 | Side-by-side run comparison (table primary, charts secondary) | PRD §5.4; DRD §7.5 | M5 | Evaluation Lab runs table (no charts) | `evaluation-view.test.tsx` | Done |
| EVL-13 | Per-case inspection split view (expected vs retrieved, answer, failure category) | PRD §5.4; DRD §7.5 | M5 | `apps/web/src/components/evaluation/case-inspector.tsx` | `evaluation-view.test.tsx` | Done |
| EVL-14 | Export CSV/JSON report with config + dataset version | PRD §5.4 | M5 | `GET /evaluations/runs/{id}/export` | `test_evaluation.py` | Done |
| EVL-15 | CI runs deterministic tests + small smoke evaluation only | TRD §9 | M5/M8 | CI runs `test_evaluation.py` with fake models | CI | Done |
| EVL-16 | Benchmark report: model, hardware, dataset version, settings, measured metrics, sample count | TRD §9, §17; PRD §11 | M8 | `docs/evaluation/README.md` | doc review | Done |

## 7. Text-to-SQL (TRD §6.3, §10; PRD §5.5)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| SQL-01 | Synthetic demo DB: customers, orders, order_items, payments, products + visible glossary; edge cases (refunds, duplicate names, nulls, dates) | PRD §5.5, §10; TRD §10 | M6 | `apps/api/app/modules/sql_assistant/demo.py` | `apps/api/tests/integration/test_sql_analyst.py` | Done |
| SQL-02 | One user-configured local Postgres connection; secret write-only, never returned | PRD §5.5; TRD §7, §8 | M6 | `POST /sql/connections/test` (Fernet, write-only) | `apps/api/tests/integration/test_sql_analyst.py` | Done |
| SQL-03 | Introspect only allowlisted schemas/tables/columns; never send credentials to LLM | TRD §6.3 | M6 | `database.introspect` (allow-listed schemas) | `apps/api/tests/integration/test_sql_analyst.py` | Done |
| SQL-04 | Ambiguity classifier: ready / clarification_required / unsupported / unsafe + confidence + missing concept | TRD §10 | M6 | deterministic glossary check + model `status` (ready / clarification_required / unsupported) | `apps/api/tests/unit/test_sql_validation.py` | Partial (no confidence; unsafe requests come back as unsupported or are rejected by the validator) |
| SQL-05 | Clarification: 2–4 options, preserves original question, requires explicit selection | TRD §10; PRD §5.5 | M6 | `ClarificationOut` (2–4 options), clarification panel | `test_sql_analyst.py`, `sql-view.test.tsx` | Done |
| SQL-06 | User-configurable, visible semantic glossary | TRD §10 | M6 | `sql_glossary_terms`, `PUT .../glossary`, schema browser | `test_sql_analyst.py` | Done |
| SQL-07 | Strict Pydantic SQL output: sql, assumptions, explanation, referenced tables | TRD §6.3 | M6 | `ModelSqlOutput` | `test_sql_analyst.py` | Done |
| SQL-08 | SQLGlot AST: exactly one SELECT / read-only CTE; reject DML/DDL/COPY/txn, multi-stmt, unapproved schemas, system catalogs, dangerous functions | TRD §6.3, §10 | M6 | `apps/api/app/modules/sql_assistant/validation.py` | `apps/api/tests/unit/test_sql_validation.py` (35 unsafe statements) | Done |
| SQL-09 | Execute via SELECT-only role; statement_timeout 5s, lock_timeout, row cap 500 | TRD §6.3, §10 | M6 | `database.execute` + reader role (ADR-006) | `test_sql_analyst.py` | Done |
| SQL-10 | Never auto-execute after ambiguous/failed generation | TRD §6.3, §17 | M6 | clarification and rejection paths return before execution | `test_sql_analyst.py` | Done |
| SQL-11 | Summarise only after success; distinguish DB facts from model interpretation | TRD §6.3 | M6 | rows shown as database facts; model explanation labelled as interpretation | `sql-view.test.tsx` | Done |
| SQL-12 | Store generated SQL + safety decision; redact credentials and sensitive literals | TRD §10 | M6 | `sql_queries` (redacted literals, decision) | `test_sql_analyst.py` | Done |
| SQL-13 | UI: schema browser, clarification panel, read-only SQL code panel with copy, explicit run control with read-only badge + DB name, sortable results table, duration + row count | PRD §5.5; DRD §7.4 | M6 | `apps/web/src/components/sql/` (executes after validation, as PRD §5.5 allows for v1) | `sql-view.test.tsx`, Playwright smoke | Done |
| SQL-14 | Safe failure messages for rejected/timeout queries; allow revised question | PRD §5.5, Journey C | M6 | rejected / failed / timeout messages; repair turn | `test_sql_analyst.py` | Done |

## 8. Models & Settings (PRD §5.6, DRD §7.6)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| SET-01 | Show Ollama status and installed local models | PRD §5.6; TRD §8 | M3 | `GET /settings/models` | `apps/api/tests/integration/test_local_models.py` | Done |
| SET-02 | Select generation + embedding model from installed compatible models | PRD §5.6 | M3 | `apps/web/src/components/settings/settings-view.tsx` | `settings-view.test.tsx` | Done |
| SET-03 | Validate availability, schema output and embedding dimension before saving | PRD §5.6; TRD §8 | M3 | `POST /settings/models/validate` | `test_local_models.py` | Done |
| SET-04 | Strong warning that changing embedding model requires full re-embedding; never mix dimensions | PRD §5.6; TRD §4.2; DRD §7.6 | M3 | warning + new embedding version + re-index all | `test_local_models.py`, `settings-view.test.tsx` | Done |
| SET-05 | Reranker optional toggle with resource warning | PRD §5.6 | M5 | reranker toggle (disabled with reason when not installed) | `settings-view.test.tsx` | Done |
| SET-06 | Copyable setup commands (`ollama pull qwen3:4b`, `ollama pull nomic-embed-text`, reranker install) | PRD §5.6; DRD §7.6 | M3 | copyable setup commands | `settings-view.test.tsx` | Done |
| SET-07 | Model size/resource notes only when verified from runtime metadata | DRD §7.6; PRD §5.1 | M3 | sizes/quantization from `/api/tags` only | `settings-view.test.tsx` | Done |
| SET-08 | No cloud provider cards, pricing or API-key fields | DRD §7.6 | M3 | no provider or key fields | `settings-view.test.tsx` (asserts no API-key input) | Done |

## 9. Workspace, onboarding, activity (PRD §4, §5.1)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| WSP-01 | First-launch setup checklist: DB connected, Ollama reachable, generation model, embedding model | PRD §5.1, Journey A | M0/M3 | `components/system-status/readiness-panel.tsx` | `readiness-panel.test.tsx` | Done |
| WSP-02 | Default local workspace auto-created; rename; no forced registration | PRD §5.1 | M1 | migration 0001 seed + `PATCH /workspaces/{id}`; sidebar shows the name | `apps/api/tests/api/test_workspaces.py` | Done |
| WSP-03 | Guided, clearly labelled sample dataset (public-domain/synthetic); sources tracked in `docs/demo-data-sources.md` | PRD §5.1, §10 | M5/M8 | `POST /evaluations/sample`, Library "Load sample documents", `docs/demo-data-sources.md` | `test_evaluation.py` | Done |
| WSP-04 | Never imply optional reranker is required | PRD §5.1 | M3 | Settings / Evaluation copy: "Basic and hybrid search work without it" | content review | Done |
| WSP-05 | Overview: readiness row, real metrics only, recent activity, working quick actions | PRD §4; DRD §7.1 | M0→M5 | `apps/web/src/components/overview/overview-dashboard.tsx` | `activity-view.test.tsx`, Playwright | Done |
| WSP-06 | Activity/Logs: ingestion jobs, failures, request ids, safe logs, latency | PRD §4 | M7 | `apps/web/src/components/activity/activity-view.tsx`, `/activity/*` | `test_activity_and_security.py`, `activity-view.test.tsx` | Done |

## 10. API contract (TRD §8)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| API-01 | All endpoints under `/api/v1` | TRD §8 | M0 | `apps/api/app/api/v1/__init__.py` | `tests/api/` | Done |
| API-02 | Stable error codes + human detail + request_id; never stack traces | TRD §8, §11; DRD §11 | M0 | `core/errors.py` | `tests/api/test_errors.py` | Done |
| API-03 | `GET /health/live` → 200 `{status:'ok'}` | TRD §8 | M0 | `api/v1/health.py` | `tests/api/test_health.py` | Done |
| API-04 | `GET /health/ready` → 200/503 with separate DB & Ollama status, no secrets | TRD §8, §12 | M0 | `api/v1/health.py`, `core/readiness.py` | `tests/api/test_health.py` | Done |
| API-05 | Paginated list endpoints (documents, conversations) | TRD §8 | M1/M4 | `apps/api/app/schemas/common.py` `Page` | documents / conversations API tests | Done |

## 11. Security & privacy (TRD §11)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| SEC-01 | Malicious upload controls (allowlist, signature, size/page limits, parser timeouts, no static serving) | TRD §11 | M1/M2/M7 | validation + upload limit middleware + parser timeout; files never served | `test_validation.py`, `test_extraction.py` | Done |
| SEC-02 | Prompt-injection: evidence delimited, policy to ignore document instructions, adversarial corpus tests | TRD §11; PRD §10 | M4/M7 | delimited evidence + policy; injection document in the gold set | `apps/api/tests/unit/test_rag_answer.py`, `integration/test_real_ollama.py` (opt-in, passes) | Done |
| SEC-03 | Workspace filter on every document/chunk/conversation/eval query + authorization tests | TRD §11 | M1→M7 | every query takes `workspace_id` | `apps/api/tests/integration/test_workspace_isolation.py`, `test_activity_and_security.py` | Done |
| SEC-04 | Secrets via env, `.env` ignored, `.env.example` placeholders, never logged, redacted | TRD §11, §15 | M0 | `.gitignore`, `.env.example`, `core/logging.py` redaction, CI `policy` job | `tests/unit/test_logging.py` | Done |
| SEC-05 | No direct execution of model output; bounded retries | TRD §11 | M4/M6 | model output parsed and validated; SQL validated before execution; one user-triggered repair | `test_rag_answer.py`, `test_sql_analyst.py` | Done |
| SEC-06 | Path traversal protection | TRD §11 | M1 | `storage.py` key regex + resolved-path check | `test_storage.py` | Done |
| SEC-07 | DoS: upload limits, rate/concurrency limits, timeouts, bounded context/top-k | TRD §11, §12 | M1→M7 | upload/page/char limits, generation concurrency gate (429), timeouts, bounded top-k/context/rows | `test_chat.py`, `test_sql_analyst.py` | Partial (no per-client request rate limit; single-user local) |
| SEC-08 | Log IDs and metrics, not document text or credentials; configurable retention | TRD §11 | M0/M7 | logs: ids/metrics; value-based redaction | `test_log_redaction.py` | Partial (log retention not configurable) |
| SEC-09 | SQL result cells treated as data, never as instructions | TRD §11 | M6 | SQL result rows are never sent to the model | code review | Done |
| SEC-10 | Audit events for significant actions | TRD §7; PRD §7 M7 | M7 | `apps/api/app/modules/audit.py`, `audit_events` | `test_activity_and_security.py` | Done |

## 12. Reliability & performance (TRD §12)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| REL-01 | UI responsive during async ingestion/evaluation | TRD §12; PRD §9 | M2/M5 | worker + polling UIs | Playwright smoke | Done |
| REL-02 | Bounded upload size, pages, chars, chunk count, context tokens, candidates, SQL rows | TRD §12 | M1→M6 | `core/config.py` limits | unit + integration tests | Done |
| REL-03 | Indexes on workspace_id, document_id, status, created_at, FTS | TRD §12 | M1/M5 | indexes in migrations 0001–0007 | `test_migrations.py` | Done |
| REL-04 | Every long op: timeout, state transition, safe error, idempotent retry | TRD §12 | M2 | worker retries/backoff, eval resume, timeouts everywhere | `test_ingestion_worker.py`, `test_evaluation.py` | Done |
| REL-05 | Graceful shutdown; stale job recovery | TRD §12 | M2 | SIGINT/SIGTERM handling, stale recovery | `test_ingestion_worker.py` | Done |
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
| DES-09 | Component library variants (Button, Status badge, Data table, Citation chip, Source drawer, Metric card, Code block, Dropzone, Clarification panel, Toast, Skeleton, Dialog) | DRD §8 | M0→M6 | Button, StatusBadge, tables, CitationChip, SourceDrawer, metric cards, SqlCodeBlock, dropzone, ClarificationPanel, toasts, skeletons, dialogs | Vitest per view | Done |
| DES-10 | Motion 120–180ms / 180–240ms; no decorative motion; respect prefers-reduced-motion | DRD §9 | M0 | `globals.css` | CSS review | Done |
| DES-11 | No optimistic completion of ingestion/evaluation; destructive actions confirmed | DRD §9 | M1+ | status only from the API; delete/rename confirmations | Vitest | Done |
| DES-12 | Keyboard: tab order, Enter/Space, Escape, focus trap, visible focus ring | DRD §9; PRD §9 | M0→M7 | skip link, focus rings, Radix focus traps, Escape closes | Playwright (skip link, Escape) | Done |
| DES-13 | Responsive behaviour at 1440+/1024/768/<768 per DRD §10 | DRD §10 | M0→M7 | responsive layouts | Playwright 390/820/1440 px, no overflow | Done |
| DES-14 | WCAG 2.2 AA contrast, visible labels, icon-only names, status not by colour alone, semantic tables, chart summaries | DRD §11; PRD §9 | M0→M7 | token contrast checked; labels; status text + icon | `tokens.test.ts` | Partial (no automated per-page contrast or screen-reader audit) |
| DES-15 | Plain language, no anthropomorphic claims, errors explain recovery | DRD §11 | all | plain-language errors with recovery commands | content review | Done |
| DES-16 | Every screen: loading, empty, success, error, disabled, partial, offline/model-unavailable states | DRD §13; Phase 6 brief | all | loading / empty / error / disabled / offline states on every page | Vitest per view | Done |
| DES-17 | `docs/design-system.md` (tokens, type, spacing, icons, states) | DRD §14 | M0 | `docs/design-system.md` | — | Done |
| DES-18 | README screenshots: Overview, Library, Ask w/ citations, Eval Lab, SQL Analyst | DRD §14; PRD §11 | M8 | README screenshots (`docs/screenshots/`) | — | Done |
| DES-19 | Recharts only where comparison benefits; neutral palette, direct labels, not red/green-only | DRD §7.5, §12 | M5 | no charts: the comparison table is the primary artifact | visual review | Done |
| DES-20 | No dead buttons or fake data cards | DRD §15 | all | all nav items are working pages | `sidebar-nav.test.tsx`, Playwright | Done |

## 14. Delivery, repository & release (PRD §7, §11, §12; TRD §14, §16, §17)

| ID | Requirement | Source | MS | Implementation module | Test case | Status |
|---|---|---|---|---|---|---|
| REP-01 | Repo structure per TRD §14 | TRD §14 | M0 | repo layout per TRD §14 (no `packages/shared-types`: not needed) | — | Done |
| REP-02 | README, docs, issue/PR templates, .gitignore, .env.example, branch strategy, lint/format configs | PRD §7 M0 | M0 | README, `.github/` templates, `.env.example`, `docs/branch-strategy.md`, ruff/eslint/prettier configs | — | Done |
| REP-03 | TRD/PRD/DRD stored in docs/ and matching implemented product | PRD §11; TRD §14 | M0/M8 | `docs/TRD.md`, `PRD.md`, `DRD.md` via `scripts/specs_to_md.py` | — | Done |
| REP-04 | ADR-001 … ADR-007 | TRD §16; PRD §11 | M0→M6 | ADR-000 … ADR-008 | — | Done |
| REP-05 | Feature branch per milestone; conventional commits; no force-push/history rewrite | PRD §12 | all | `feat/mN-*` branches, `--no-ff` merges, conventional commits | git log | Done |
| REP-06 | Clean clone starts with documented commands; Ollama setup explicit | TRD §17; PRD §13 | M0/M8 | README + scripts; fresh-clone check repeated at M8 | see implementation-status | Done |
| REP-07 | Migrations run from empty DB and upgrade from previous release | PRD §11; TRD §17 | M1/M8 | Alembic 0001–0007; downgrade/upgrade round trip | `test_migrations.py`; CI `alembic check` | Done |
| REP-08 | Reproducible, clearly synthetic/public demo seed | PRD §11 | M8 | `seed-demo` + sample loader (deterministic) | `test_sql_analyst.py`, `test_evaluation.py` | Done |
| REP-09 | Demo video, release tag only after acceptance checks | PRD §7 M8, §11 | M8 | local tag `v1.0.0-rc.1`; no demo video | — | Partial (demo video not recorded; CI not run) |
| REP-10 | Makefile (TRD §14) — plus PowerShell equivalents for Windows | TRD §14 | M0 | `Makefile`, `scripts/dev.ps1`, `scripts/db.ps1` | — | Done |
