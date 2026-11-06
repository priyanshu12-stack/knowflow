<!-- Generated from KnowFlow_TRD_Technical_Requirements.docx (authoritative source). Do not edit by hand. -->
KNOWFLOW
# Technical Requirements Document
Architecture, technology choices, data flows, model strategy, APIs, security and engineering constraints

| DOCUMENT CONTROL | VALUE |
|---|---|
| Document ID | TRD-001 |
| Version | 1.0 |
| Status | Baseline specification – update decisions in the repository |
| Product | KnowFlow – Local-first Enterprise Knowledge Intelligence |
| Owner | Solo developer / project maintainer |
| Date | 06 November 2026 |


## How to use this document
Give this document to the coding agent as an authoritative project specification. The agent must read all three documents (TRD, PRD and DRD) before changing code. If two documents appear to conflict, use the priority rules in the PRD and record the resolution in docs/decisions/ rather than silently inventing a design.
Important: this specification defines the intended product and acceptance criteria. It does not claim that implementation, benchmark results, security certification or deployment already exist.

## 1. Technical vision and non-negotiable constraints
KnowFlow is a local-first knowledge intelligence platform that ingests a user's documents, retrieves relevant evidence, generates cited answers, and safely answers questions over an explicitly connected relational dataset. The product must demonstrate engineering discipline: measurable retrieval quality, grounded generation, deterministic validation around risky operations, observability and reproducible tests.
- Zero paid inference APIs are required. All LLM generation, embedding and reranking must run locally by default.
- No API key, credit card, paid hosted inference endpoint or external model provider may be required for core functionality.
- Internet is needed only to download dependencies/models initially and optionally to deploy a public frontend. Runtime inference remains local.
- Do not claim that free model weights mean zero compute cost: CPU/GPU, RAM, disk, electricity and hosting remain user-provided resources.
- No quality claims or benchmark numbers may be invented. Model and retrieval choices must be verified against the project evaluation set.
- Build in vertical slices. Do not create empty placeholder modules for every future feature before the first working slice.

## 2. Product scope and system boundaries

| In scope (v1) | Out of scope (v1) |
|---|---|
| Local document workspace; PDF, DOCX, TXT, MD ingestion; extraction and metadata; chunking experiments; dense + lexical hybrid retrieval; reranking toggle; cited RAG answers; evaluation workbench; read-only Text-to-SQL against a sample/user-configured database; clarification before ambiguous SQL; local model settings; audit logs; Docker Compose; tests and documentation. | OCR for scanned PDFs; image/audio/video understanding; fine-tuning; autonomous database writes; arbitrary shell execution; public multi-tenant SaaS; paid API fallbacks; enterprise SSO; complex distributed task queues; automatic model downloads at runtime; user-uploaded code execution. |

Primary operating mode is a single-user/local installation. Keep workspace_id and ownership boundaries in the data model so the design can grow, but do not build complex organization billing or SaaS administration in v1.

## 3. Recommended technology stack

| Layer | Selected technology | Reason / implementation note |
|---|---|---|
| Web application | Next.js App Router + TypeScript | Strong full-stack UI foundation; use server/client components intentionally. Official docs: https://nextjs.org/docs/app |
| UI styling | Tailwind CSS + shadcn/ui + Lucide icons | Accessible primitives and consistent design tokens; customize heavily to avoid template appearance. |
| Backend API | Python 3.12+ + FastAPI | Typed request/response contracts, OpenAPI docs, async endpoints where useful. |
| Validation | Pydantic v2 | Validate API payloads, model output and configuration at boundaries. |
| Relational database | PostgreSQL 16+ | Users/workspaces, documents, chunks metadata, ingestion jobs, conversations, evaluation datasets and SQL connections. |
| Vector search | pgvector extension | Keep dense vectors beside metadata; exact search for baseline, HNSW only after measuring scale/latency. |
| Lexical search | PostgreSQL full-text search (tsvector/ts_rank_cd) | BM25-like lexical baseline without another search service; combine with dense results using application-side Reciprocal Rank Fusion. |
| Local LLM runtime | Ollama | Local model serving and REST API; no paid inference API. https://ollama.com/ |
| Generation model baseline | Qwen3 4B or 8B via Ollama | Start with qwen3:4b on constrained RAM; use qwen3:8b on a capable 16GB+ RAM machine. Pin tag and record model digest. Model sizes/context vary by tag. |
| Embedding baseline | nomic-embed-text via Ollama | Dedicated embedding model; pin version, record vector dimension and ensure DB schema matches actual returned dimension. |
| Reranker | BAAI/bge-reranker-v2-m3 via Sentence Transformers (optional) | Apache-2.0 model card; optional CPU-heavy second stage. Enable only after measuring quality/latency. |
| Chunking | Custom Python strategies | Fixed/recursive baseline, semantic-boundary experiment; same evaluation corpus for fair comparison. |
| SQL safety | SQLGlot + dedicated read-only PostgreSQL role | Parse and allow SELECT-only query AST; reject multiple statements, DDL/DML, dangerous functions and unapproved schemas. |
| Background jobs | PostgreSQL-backed job table + one worker process | Avoid Redis/Celery complexity for solo v1; idempotent job state and retries. Add queue only if measured need. |
| Testing | Pytest, HTTPX, Vitest/Playwright | Unit, integration, API contract, UI smoke and end-to-end tests. |
| Evaluation | Custom gold-set evaluator + optional Ragas | Own deterministic retrieval metrics; LLM-judge metrics are supplementary and must not be treated as ground truth. |
| Observability | Structured JSON logs + request_id + local metrics table | Record latency, token counts if available, model id, retrieval strategy, errors and user-visible feedback. No external telemetry by default. |
| Packaging | Docker Compose for Postgres; local Ollama service | One-command local startup; document native Ollama and Docker Ollama options. |
| CI | GitHub Actions | Lint, typecheck, tests, migrations check and build. CI must not download large LLMs. |


## 4. Model selection and zero-cost inference policy
The project must be provider-agnostic internally but ship with local Ollama adapters only. Define interfaces (ChatModel, EmbeddingModel, Reranker) so models can be swapped without changing business logic. No cloud provider adapter is needed for v1.

### 4.1 Generation model profiles

| Profile | Ollama model | Use when | Caveats |
|---|---|---|---|
| Low-resource | qwen3:4b | Approximately 8GB RAM class machine; prioritize responsiveness and smaller context. | May be weaker on complex SQL clarification and nuanced synthesis; benchmark before selecting. |
| Recommended | qwen3:8b | 16GB+ RAM and/or GPU; default quality/performance candidate. | Model artifact is about 5.2GB in the published Ollama listing; runtime memory is higher than file size. |
| High-resource experiment | qwen3:14b or another locally runnable open model | Machine has sufficient RAM/VRAM; compare on same gold set. | Do not make it the default or assume better end-to-end results without measured evidence. |

Ollama model listings are mutable. Before implementation, verify the selected tag, quantization, disk size, context window and license shown on the model page. Pin exact tags in .env.example and record model name/digest in evaluation output. Qwen3:8b is listed with Apache-2.0 in Ollama's model page at the time of research.

### 4.2 Embedding and reranking

| Component | Default | Fallback / policy |
|---|---|---|
| Dense embeddings | nomic-embed-text (Ollama) | Keep embedding model/version/dimension in database metadata. Changing embedding model requires full re-embedding; never mix dimensions or model spaces. |
| Lexical retrieval | PostgreSQL FTS | Always available; useful for exact names, IDs, clauses and rare terms. |
| Reranker | BAAI/bge-reranker-v2-m3 (local, optional) | Feature flag ENABLE_RERANKER=false by default on constrained CPU. Load lazily and cache. Measure before enabling. |
| Alternative embedding experiments | Compare a local Qwen3 embedding or multilingual embedding model only as a controlled experiment | Do not add multiple models to production path until a benchmark shows measurable benefit. |

Nomic's Ollama listing exposes an embedding-only model and supports local embedding calls. Its listing variants show different context metadata, so use the exact pinned tag and verify limits rather than hardcoding assumptions. Reranking is a second-stage relevance scorer, not an embedding replacement.

### 4.3 Model runtime contract
- At startup, health-check Ollama and confirm required models are available. Show a setup command if missing; do not silently switch to a paid endpoint.
- Use bounded timeouts, concurrency limits and cancellation. A local model may be slow or unavailable.
- Generation requests must include deterministic configuration where appropriate (temperature 0–0.2 for extraction/SQL; moderate temperature only for conversational prose).
- For structured outputs, request a JSON Schema through Ollama where supported, then independently validate with Pydantic. Invalid output is a recoverable model error, not trusted data.
- Keep separate system prompts for RAG answer synthesis, query classification, clarification, SQL generation and evaluation. Never reuse an unrestricted generic agent prompt.
- Record model tag, quantization if known, runtime version, temperature, context settings and machine profile with each benchmark run.

## 5. High-level architecture
```text
Browser (Next.js / TypeScript)
        | HTTPS / same-origin API proxy in production
        v
FastAPI application
  |-- Auth / workspace / document APIs
  |-- Ingestion orchestration --> extraction --> chunking --> embeddings
  |                                             |              |
  |                                             v              v
  |                                         PostgreSQL <---- pgvector
  |                                             |
  |-- Query orchestrator -----------------------+
  |      |-- query rewrite / intent routing
  |      |-- dense retrieval (pgvector)
  |      |-- lexical retrieval (Postgres FTS)
  |      |-- RRF fusion
  |      |-- optional local reranker
  |      |-- evidence filtering / context packing
  |      |-- Ollama generation --> Pydantic validation
  |      |-- citation/source mapping
  |
  |-- Text-to-SQL pipeline
  |      |-- schema introspection / allowlist
  |      |-- ambiguity detection --> clarification turn
  |      |-- SQL generation --> SQLGlot AST validation
  |      |-- read-only DB role + statement timeout
  |      |-- result summarization
  |
  |-- Evaluation / metrics / audit APIs
        |
        +--> Ollama local runtime (Qwen generation + Nomic embeddings)
        +--> optional local CrossEncoder reranker

PostgreSQL: application data, document/chunk metadata, pgvector, FTS,
            jobs, evaluation sets/results, audit events, SQL connection metadata
```
The diagram is logical, not a claim that every component must be a separate deployable service. For v1, keep one FastAPI codebase with clear modules and one worker process. PostgreSQL is the system of record. Store uploaded binaries on local filesystem under a configured data directory; store only safe relative paths and checksums in the database.

## 6. Main data flows

### 6.1 Document ingestion
- User uploads a supported file. Enforce size, extension, MIME and file signature checks; generate a UUID and SHA-256 checksum.
- Store file in a non-public local data directory using generated names, never the original filename as a filesystem path.
- Create document and ingestion_job records with status queued. Return 202 Accepted and job id.
- Worker extracts text and page/section metadata. Preserve page numbers and heading paths where possible. Reject empty/unsupported extraction with a useful error.
- Normalize text without destroying meaningful tables, code, headings or identifiers. Keep original extracted text for traceability.
- Run chunking strategy (fixed/recursive baseline; semantic as experiment). Each chunk stores document_id, chunk_index, page range, section path, character/token counts, strategy and content hash.
- Generate embeddings locally in batches. Validate vector dimension and finite values.
- Write chunks and vectors transactionally where possible; mark document ready only after all chunks are committed. On failure, clean partial chunks or mark failed with retry-safe semantics.
- Expose ingestion progress and per-document counts in UI. Re-uploading identical checksum should be idempotent or explicitly create a new version.

### 6.2 RAG query
- Validate request, workspace ownership and document filters.
- Classify query only when needed: normal knowledge question, unsupported/out-of-scope, or clarification needed. Keep classifier output structured.
- Embed query using the same embedding model used for indexed chunks.
- Retrieve top-N dense candidates using pgvector and top-N lexical candidates using Postgres FTS. Apply workspace/document filters before returning candidates.
- Fuse ranked lists with Reciprocal Rank Fusion (RRF). Store strategy, candidate IDs and ranks for evaluation.
- Optionally rerank top 20–50 candidates with local CrossEncoder. Apply context budget and deduplicate overlapping chunks.
- If evidence is below a calibrated threshold or no useful sources exist, abstain and ask for a narrower query. Do not fabricate an answer.
- Generate answer from only supplied evidence. Require citations to chunk ids; map citations to document title/page/section in backend.
- Validate response schema, ensure every citation refers to a retrieved chunk, and return answer + citations + retrieval metadata.
- Record latency, model, retrieval strategy, source ids, error state and feedback. Avoid storing secrets or raw sensitive prompts in logs.

### 6.3 Text-to-SQL
- User selects a configured database connection. V1 should include a seeded demo database and allow one local PostgreSQL connection.
- Introspect only allowlisted schemas/tables/columns. Never send database credentials to the LLM; send schema descriptions only.
- Parse the question for missing business definitions (e.g., 'best customer' could mean revenue, orders or retention). If multiple plausible metrics exist, return a clarification object and wait for user selection.
- Generate SQL with a strict Pydantic schema containing sql, assumptions, explanation and referenced tables.
- Parse generated SQL with SQLGlot. Require exactly one SELECT or safe read-only CTE ending in SELECT. Reject INSERT/UPDATE/DELETE/MERGE/DDL/COPY/transaction commands, multiple statements, unapproved schemas, system catalogs and dangerous functions.
- Execute through a separate database role with SELECT only, statement_timeout, row limit, lock timeout and no write permissions. Add query plan/resource limits where available.
- Return tabular result, generated SQL, explanation and clarification history. Never auto-execute after an ambiguous or failed generation.
- Summarize results only after successful execution. Clearly distinguish database facts from model interpretation.

## 7. Database design (initial logical schema)

| Table | Important fields / constraints |
|---|---|
| workspaces | id UUID PK, name, created_at. Single-user local default; workspace_id scopes all content. |
| documents | id UUID PK, workspace_id FK, original_name, storage_key, mime_type, size_bytes, sha256, status, page_count, created_at, updated_at. Unique checksum per workspace/version policy. |
| ingestion_jobs | id UUID PK, document_id FK, status, attempts, error_code, error_message_safe, started_at, completed_at, retry_after. |
| chunks | id UUID PK, document_id FK, workspace_id FK, chunk_index, text, page_start, page_end, section_path, token_count, strategy, content_hash, embedding vector(D), search_tsv tsvector. Unique(document_id, chunk_index, strategy, version). |
| conversations | id UUID PK, workspace_id FK, title, created_at, updated_at. |
| messages | id UUID PK, conversation_id FK, role, content, citations JSONB, metadata JSONB, created_at. Validate role and size. |
| evaluation_datasets | id UUID PK, workspace_id FK, name, task_type, version, created_at. |
| evaluation_cases | id UUID PK, dataset_id FK, question, reference_answer, expected_chunk_ids JSONB, expected_sql, tags JSONB. |
| evaluation_runs | id UUID PK, dataset_id FK, config JSONB, model_id, strategy, status, aggregate_metrics JSONB, created_at. |
| evaluation_results | id UUID PK, run_id FK, case_id FK, retrieved_ids JSONB, answer, metrics JSONB, latency_ms, error. |
| sql_connections | id UUID PK, workspace_id FK, display_name, encrypted_secret_ref, db_type, host, port, database_name, allowed_schemas JSONB. Never expose secret in API. |
| audit_events | id UUID PK, workspace_id, actor, action, resource_type, resource_id, request_id, metadata_safe JSONB, created_at. |

Vector dimension D must be set from the selected embedding model. Do not assume the dimension based on a marketing page; verify with a startup model probe and migration. If changing D, create a new embedding version/column or rebuild the index safely.

## 8. API contract (v1)
All endpoints are versioned under /api/v1. JSON responses use a consistent envelope or documented resource schema. Errors use stable error codes, human-readable detail and request_id. Do not return stack traces.

| Method + endpoint | Purpose / request | Response / behaviour |
|---|---|---|
| GET /health/live | Process liveness | 200 {status: 'ok'} |
| GET /health/ready | DB + Ollama readiness | 200/503 with dependency status; do not leak secrets. |
| POST /documents | multipart file upload | 202 {document_id, job_id, status} |
| GET /documents | List workspace documents | Paginated metadata and ingestion status. |
| GET /documents/{id} | Document details | Status, pages, chunk count, safe error. |
| DELETE /documents/{id} | Delete document and chunks | Idempotent; delete binaries only after ownership check. |
| GET /jobs/{id} | Ingestion progress | Queued/running/succeeded/failed, progress stage. |
| POST /chat/query | {conversation_id?, question, document_ids?, retrieval_config?} | Answer, citations, abstained, retrieval trace summary, request_id; stream only after stable non-streaming version. |
| POST /chat/clarify | {conversation_id, clarification_id, selected_option} | Resume a pending ambiguous query. |
| GET /conversations | List conversations | Paginated list. |
| GET /conversations/{id} | Conversation messages | Messages and source references. |
| POST /sql/connections/test | Connection config (secret write-only) | Connection metadata; never return credentials. |
| GET /sql/schema/{connection_id} | Get allowlisted schema summary | Tables/columns/types/descriptions only. |
| POST /sql/query | {connection_id, question, clarification_context?} | Either clarification_required or validated query + result table. |
| POST /evaluations/datasets | Create dataset | Dataset metadata. |
| POST /evaluations/datasets/{id}/cases/import | CSV/JSONL cases | Validated import summary with row-level errors. |
| POST /evaluations/runs | {dataset_id, config} | 202 {run_id}; execute evaluation in worker. |
| GET /evaluations/runs/{id} | Run progress and results | Per-case metrics and aggregate results. |
| GET /settings/models | Local runtime models and profiles | Available models and health; no paid providers. |
| POST /settings/models/validate | {generation_model, embedding_model} | Probe runtime, schema output and vector dimension. |


## 9. RAG retrieval and evaluation design

| Strategy ID | Retrieval method | Purpose |
|---|---|---|
| S1 | Fixed-size chunking + dense top-k | Simple baseline. |
| S2 | Recursive/structure-aware chunking + dense top-k | Preserve headings and semantic boundaries. |
| S3 | S2 chunks + dense and lexical retrieval + RRF | Hybrid candidate recall. |
| S4 | S3 + local reranker | Measure whether reranking improves ranking enough to justify latency. |

Evaluation dataset: begin with 50 hand-verified questions; target 100–150 before publishing results. Include factual lookups, exact identifiers, multi-hop questions, table questions, unanswerable questions, conflicting/dated documents and prompt-injection documents. Store reference answers and relevant chunk ids. Split development and held-out test cases; never tune on the held-out set.

| Metric | Definition / use |
|---|---|
| Recall@K | Fraction of expected relevant chunks present in top K; primary retrieval recall. |
| Precision@K | Fraction of retrieved top-K chunks that are relevant. |
| MRR | Ranking quality based on reciprocal rank of first relevant result. |
| nDCG@K | Ranking quality when relevance has graded labels. |
| Faithfulness | Whether generated claims are supported by retrieved context; use judge carefully and manually audit sample. |
| Answer correctness | Compare answer to reference using rubric/manual adjudication; judge metrics are not ground truth. |
| Citation precision | Fraction of cited sources that actually support the associated claims. |
| Abstention accuracy | Correctly refuses unanswerable questions while answering answerable ones. |
| Latency | p50/p95 end-to-end and per-stage latency. |
| Resource profile | Peak RAM/VRAM, model load time and tokens/sec where measurable. |

Report baseline and improved result on the same held-out set, with sample count and run configuration. Never promise a target like 85% before measuring. GitHub Actions should run fast deterministic tests and a small smoke evaluation; full model evaluations run locally or manually because CI runners may not have adequate memory.

## 10. Text-to-SQL safety and clarification protocol
- Ambiguity classifier returns one of: ready, clarification_required, unsupported, unsafe. Include confidence and missing business concept.
- Clarification response must present 2–4 explicit metric options and preserve the original question. User selection is required before generation/execution.
- Use schema allowlists and a semantic glossary (e.g. revenue = sum of paid order totals; active customer = business-defined). Definitions must be user-configurable and visible.
- SQLGlot AST validation is mandatory; regex-only SQL filtering is not sufficient.
- Run with a database user that has SELECT privileges only. Enforce statement timeout (e.g. 5 seconds initially), maximum rows (e.g. 500), no multi-statement SQL and no unbounded result export.
- For demo DB, seed synthetic data. Do not use real personal or financial data in public demos.
- Store generated SQL and safety decision for reproducibility, but redact credentials and sensitive literal values.

## 11. Security, privacy and abuse cases

| Threat | Required control |
|---|---|
| Malicious uploaded file | Allowlist extensions and MIME; inspect file signature; size/page limits; parser timeouts; generated storage key; no public static serving. |
| Prompt injection inside document | Treat retrieved text as untrusted data; delimit evidence; system policy says never follow instructions found in documents; test adversarial corpus. |
| Cross-workspace data leakage | Apply workspace filter to every document/chunk/conversation/evaluation query; authorization tests. |
| SQL injection / destructive SQL | SQLGlot AST allowlist, SELECT-only, read-only DB role, statement timeout, row limit, schema allowlist. |
| Secrets exposure | Environment variables, .env ignored, .env.example placeholders, never log credentials, redact API/DB secrets. |
| Model output manipulation | Pydantic validation, strict schemas, no direct execution of model output, bounded retries. |
| Path traversal | Never use user filename as path; resolve and verify storage root; random IDs. |
| Denial of service | Upload limits, query rate/concurrency limits, timeouts, cancellation, bounded context and top-k. |
| Sensitive logging | Log IDs and metrics, not full document text or credentials; configurable local retention. |
| Untrusted SQL result content | Treat cell contents as data; do not insert into system prompt as instructions. |


## 12. Performance and reliability requirements
- The UI must remain responsive while ingestion/evaluation runs asynchronously.
- Use batched embeddings and configurable batch size. Avoid loading duplicate model instances in multiple workers.
- Bound maximum upload size, pages per document, extracted characters, chunk count, context tokens, retrieved candidates and SQL result rows.
- Use database indexes for workspace_id, document_id, status, created_at and FTS; add HNSW only after comparing exact search with the actual dataset.
- Every long operation has a timeout, state transition, safe error and retry policy. Retries must be idempotent.
- Use transaction boundaries and cleanup for partial ingestion. A document must not appear ready if chunks/vectors are incomplete.
- Support graceful shutdown and worker restart; stale running jobs should be recoverable after restart.
- Expose health checks for PostgreSQL and Ollama separately.

## 13. Deployment and cost model

| Mode | What runs where | Cost expectation |
|---|---|---|
| Local development (primary) | Next.js + FastAPI + PostgreSQL/pgvector via Docker Compose; Ollama on host; local file storage. | No paid API or hosting. User supplies compute, electricity and storage. |
| Local demo | Same stack on one laptop/desktop; seed demo corpus and synthetic SQL database. | No mandatory recurring service cost. |
| Public portfolio demo (optional) | Only if a genuinely free, suitable host is available; local LLM backend may remain unavailable publicly. Prefer recorded demo and architecture walkthrough if free compute is inadequate. | Do not promise free always-on LLM hosting. Public cloud free tiers have limits and may require payment details. |
| CI | GitHub Actions lint/test/build; no model weights. | Use included free quota where available; keep jobs small. |

A Next.js static/frontend deployment does not make the local FastAPI + Ollama inference stack publicly accessible. Do not expose a developer laptop or Ollama port directly to the public internet. If public access is later needed, design authenticated API gateway, TLS, network isolation, rate limits and an explicit hosting budget.

## 14. Repository structure
```text
knowflow/
  apps/
    web/                    # Next.js App Router frontend
    api/
      app/
        api/v1/             # routers
        core/               # config, logging, errors
        db/                 # SQLAlchemy models, migrations
        modules/
          documents/        # upload, extraction, chunking, jobs
          retrieval/        # dense, lexical, RRF, rerank
          rag/               # orchestration, prompts, citations
          sql_assistant/    # schema, clarify, generate, validate, execute
          evaluation/       # datasets, metrics, runs
          models/           # Ollama adapters, embedding, reranker
        schemas/             # Pydantic API contracts
        workers/             # DB-backed job worker
      tests/
  packages/
    shared-types/            # generated/shared API types if useful
  infra/
    docker-compose.yml
    postgres/
  data/                      # gitignored uploads and local state
  docs/
    TRD.md PRD.md DRD.md
    architecture/
    decisions/
    evaluation/
  scripts/
  .github/workflows/
  .env.example
  README.md
  Makefile
```

## 15. Engineering conventions
- Use SQLAlchemy 2.x and Alembic migrations; never rely on create_all in production startup.
- Use typed Python functions, explicit dependency injection and module boundaries. Avoid a giant service.py or routes.py.
- Use ruff for lint/format and mypy or pyright for static checks where practical. Use ESLint and TypeScript strict mode in web.
- All external boundaries have Pydantic schemas. Avoid untyped dicts for core domain objects.
- Use UTC timestamps in storage and convert to local time in UI.
- Use UUID identifiers. Use structured error codes and request correlation IDs.
- Keep prompts versioned under source control and attach prompt_version to evaluations.
- No secrets, model binaries, uploaded documents, database volumes or local benchmark dumps in Git.
- Use feature flags for semantic chunking, reranker, streaming and SQL assistant. A disabled optional feature must not break core RAG.

## 16. Technical decision records to create

| ADR | Decision to document | Questions to answer |
|---|---|---|
| ADR-001 | Local-first model runtime | Why Ollama; chosen Qwen tag; RAM/latency; license and model digest. |
| ADR-002 | Embedding model/version | Dimension, language coverage, token limit, retrieval benchmark, migration strategy. |
| ADR-003 | PostgreSQL + pgvector + FTS | Why one primary data store; exact vs HNSW; FTS ranking; operational simplicity. |
| ADR-004 | RRF and reranking | Candidate counts, fusion constant, quality gain and latency cost. |
| ADR-005 | Chunking strategy | Fixed vs recursive vs semantic; page/heading preservation; overlap trade-off. |
| ADR-006 | Text-to-SQL safety | SQLGlot policy, database role, schema allowlist, timeouts and rejected syntax. |
| ADR-007 | Local-only cost boundary | What is truly free, what depends on machine/hosting, and no paid API dependency. |


## 17. Acceptance criteria for technical readiness
- A clean clone can start Postgres and the app using documented commands; Ollama model setup is explicit.
- The system can upload, ingest, retrieve and cite at least one supported document end-to-end.
- The selected embedding model dimension is checked at startup and persisted with an embedding version.
- Dense, lexical, hybrid and reranked retrieval can be benchmarked on the same dataset.
- The RAG response contains only valid citations or explicitly abstains.
- Ambiguous SQL returns clarification without executing a query.
- SQL execution rejects destructive/multiple/unapproved statements and uses a read-only role.
- Unit, integration, API and UI smoke tests pass; migrations work from an empty database.
- No paid API credentials are needed for any v1 core workflow.
- A benchmark report records model, hardware, dataset version, retrieval settings and measured metrics.

## 18. Technical references
- Ollama Qwen3 model library: https://ollama.com/library/qwen3
- Ollama Qwen3:8b tag and Apache-2.0 listing: https://ollama.com/library/qwen3:8b
- Ollama nomic-embed-text: https://ollama.com/library/nomic-embed-text
- Ollama structured outputs: https://ollama.com/blog/structured-outputs
- Qdrant hybrid retrieval concepts (reference design only): https://qdrant.tech/documentation/hybrid-queries/
- pgvector: https://github.com/pgvector/pgvector
- Sentence Transformers retrieve & rerank: https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html
- BAAI bge-reranker-v2-m3 model card and license: https://huggingface.co/BAAI/bge-reranker-v2-m3
- Ragas metrics reference: https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/
- Next.js App Router documentation: https://nextjs.org/docs/app
- FastAPI documentation: https://fastapi.tiangolo.com/
- SQLGlot: https://sqlglot.com/
Research note: model libraries and documentation can change. Re-check licenses, tags, model sizes, context windows and runtime compatibility at implementation time. The selected baseline is a practical starting point, not a claim that one model is universally best.
