# KnowFlow Interview Question Bank

> Technical (162 questions, 27 topics, Beginner → Expert), managerial/HR (17) and stress (16)
> questions. Every "KnowFlow" line points at real code or recorded results (commit `65af69c`).
> Format: **Short** = what you say first (≤ 2 sentences) · **Detailed** = if they want depth ·
> **KnowFlow** = where it lives · **Follow-up** → answer.
>
> Companion: [Master guide](KNOWFLOW_ENGINEERING_AND_INTERVIEW_MASTER_GUIDE.md) ·
> [Quick revision](KNOWFLOW_QUICK_REVISION.md) · [API reference](KNOWFLOW_API_REFERENCE.md)

## Contents
1. Project architecture · 2. Python · 3. FastAPI · 4. REST APIs · 5. Next.js and TypeScript ·
6. PostgreSQL · 7. Database indexing · 8. Vector databases · 9. Embeddings · 10. RAG · 11. Chunking ·
12. Hybrid search · 13. RRF · 14. Reranking · 15. LLM fundamentals · 16. Transformers and attention ·
17. Ollama and open-source models · 18. Prompt engineering · 19. Structured outputs · 20. Text-to-SQL ·
21. SQLGlot · 22. AI safety · 23. Evaluation · 24. Docker · 25. Git and CI/CD · 26. Deployment ·
27. Performance optimisation · [Managerial and HR](#part-q--managerial-and-hr-preparation) ·
[Stress interview](#part-r--stress-interview)

---

## 1. Project architecture

**1.1 [Beginner] Describe KnowFlow's architecture in one breath.**
- *Short:* A Next.js UI that proxies to a FastAPI API; a separate worker process; PostgreSQL with pgvector as the only store; Ollama for local models.
- *Detailed:* The browser calls same-origin `/api/v1/*`; Next.js rewrites to FastAPI on 127.0.0.1:8000. Uploads create a job row; the worker claims jobs with `FOR UPDATE SKIP LOCKED`, extracts, chunks, embeds and commits. Queries go API → retrieval (SQL over pgvector/FTS) → Ollama → validated JSON → verified citations.
- *KnowFlow:* `apps/web/next.config.ts`, `app/main.py`, `workers/ingestion.py`, `infra/docker-compose.yml`.
- *Follow-up:* Why not put the worker in the API process? → *Answer:* CPU-heavy work would starve request threads, and a crash would take the API down; a separate process restarts independently and the queue state is durable in Postgres.

**1.2 [Beginner] Why does the browser never call FastAPI directly?**
- *Short:* Next.js rewrites `/api/v1/*` to FastAPI, so it's same-origin: no CORS, and the API port stays private.
- *Detailed:* The rewrite is resolved at build/start from `API_INTERNAL_URL`; `proxyTimeout` is raised to 600 s because CPU generation can take minutes.
- *KnowFlow:* `next.config.ts::rewrites`, `experimental.proxyTimeout`.
- *Follow-up:* Downsides? → *Answer:* One more hop and a second timeout to tune; the proxy's keep-alive pool caused a real ECONNRESET race with Uvicorn's 5 s keep-alive, fixed with `--timeout-keep-alive 75`.

**1.3 [Intermediate] Why PostgreSQL as the job queue instead of Redis/Celery?**
- *Short:* One datastore, and job state commits in the same transaction as document state.
- *Detailed:* `claim_next_job` uses `SELECT … FOR UPDATE SKIP LOCKED` so multiple workers never take the same job; `heartbeat_at` + `recover_stale_jobs` handle crashed workers; `retry_after` implements backoff. Throughput needs are tiny (a handful of documents), so a broker adds ops cost without benefit.
- *KnowFlow:* `workers/ingestion.py::claim_next_job`, `recover_stale_jobs`, `_fail`.
- *Follow-up:* When would you switch? → *Answer:* High job rates, fan-out, or cross-service events; Postgres queues get contention and vacuum pressure at large volumes.

**1.4 [Intermediate] How do layers depend on each other in the backend?**
- *Short:* Routers → services/modules → ORM; modules depend on protocols, not on Ollama.
- *Detailed:* `ChatModel` and `EmbeddingModel` are `typing.Protocol`s; the Ollama adapters implement them; tests inject fakes. Routers are thin: validate, call one service, audit, return.
- *KnowFlow:* `modules/models/interfaces.py`, `registry.py::OllamaChat`, `api/v1/chat.py`.
- *Follow-up:* How would you add a hosted model? → *Answer:* Implement `ChatModel.complete` for that provider and select it in `registry.chat_model`; nothing else changes (forbidden here by ADR-007, but the seam exists).

**1.5 [Advanced] Where are the consistency boundaries?**
- *Short:* Upload (row + job + file move), ingestion completion (sections + chunks + vectors + `ready` in one transaction), and audit events (committed with the change).
- *Detailed:* If the upload commit fails, the stored file is deleted; `_complete` deletes and rewrites chunks under row locks so retries are idempotent; `audit.record` adds to the caller's session.
- *KnowFlow:* `documents/service.py::upload_document`, `workers/ingestion.py::_complete`, `modules/audit.py`.
- *Follow-up:* What isn't transactional? → *Answer:* The file system: deleting a document commits the row first, then deletes the file; a failed file delete is logged by id for cleanup.

**1.6 [Expert] If you had to split KnowFlow into services, where would you cut?**
- *Short:* Ingestion (workers + extraction sandbox), retrieval/query API, model serving, and evaluation as a batch job.
- *Detailed:* The seams already exist: the job table, `retrieve()` shared by RAG and evaluation, the `ChatModel`/`EmbeddingModel` protocols. Model serving becomes a GPU service; retrieval stays close to the database.
- *KnowFlow:* `retrieval/service.py::retrieve` used by `rag/service.py` and `evaluation/runner.py::score_case`.
- *Follow-up:* What gets harder? → *Answer:* Transactions across services (ready + vectors), so you'd keep ingestion and the index in one service or use an outbox.

## 2. Python

**2.1 [Beginner] What's a dataclass and where do you use one instead of Pydantic?**
- *Short:* A lightweight class with generated `__init__`/`__eq__`; used for internal value objects that don't need validation.
- *Detailed:* Pydantic validates untrusted input (requests, model output); dataclasses carry already-trusted data between functions cheaply. `frozen=True` makes them immutable.
- *KnowFlow:* `retrieval/types.py::Candidate`, `documents/chunking.py::Chunk` (frozen), `extraction.py::Unit`.
- *Follow-up:* Why is `Candidate` not frozen? → *Answer:* Fusion and reranking update `score` and `ranks` in place.

**2.2 [Beginner] What does `@lru_cache` on `get_settings` do?**
- *Short:* Memoises it, so settings are parsed and validated once per process.
- *Detailed:* Same trick for the DB engine (`get_engine`) and Ollama clients (`ollama_client(base_url, timeout)`), giving one connection pool per process.
- *KnowFlow:* `core/config.py`, `db/session.py`, `models/registry.py`.
- *Follow-up:* Testing downside? → *Answer:* Cached values leak between tests; you call `cache_clear()` or pass settings explicitly (`create_app(settings)`).

**2.3 [Intermediate] Why use `typing.Protocol` for model interfaces?**
- *Short:* Structural typing: anything with the right methods qualifies, no inheritance needed.
- *Detailed:* Fakes in tests just implement `complete(...)`; mypy checks conformance statically.
- *KnowFlow:* `models/interfaces.py::ChatModel`, `EmbeddingModel`; `models/reranker.py::Reranker`.
- *Follow-up:* Protocol vs ABC? → *Answer:* ABCs enforce at runtime via inheritance; Protocols are checked by the type checker and keep adapters decoupled.

**2.4 [Intermediate] How do you run untrusted parsing safely in Python?**
- *Short:* In a separate process with a timeout that kills it.
- *Detailed:* `multiprocessing` "spawn" context, a pool of 1 with `maxtasksperchild=1`, `apply_async(...).get(timeout)`, `pool.terminate()` on timeout. Custom exceptions need `__reduce__` to pickle cleanly.
- *KnowFlow:* `extraction.py::extract_with_timeout`, `ExtractionError.__reduce__`.
- *Follow-up:* Why not threads? → *Answer:* A thread can't be killed, and a C-extension crash or infinite loop would take the worker down.

**2.5 [Advanced] What is a ContextVar and why is the request id one?**
- *Short:* A context-local variable that's correct per request even under concurrency.
- *Detailed:* Set in middleware, read by the log formatter and the error envelope, reset in `finally`. Works across threadpool execution because Starlette copies the context into the thread.
- *KnowFlow:* `core/logging.py::request_id_var`, `core/middleware.py`.
- *Follow-up:* Why not a global? → *Answer:* Concurrent requests would overwrite each other's ids.

**2.6 [Expert] How does `mypy --strict` change how you write this code?**
- *Short:* No implicit `Any`, every function annotated, Optional handled explicitly.
- *Detailed:* Forces explicit narrowing (`isinstance` checks on parsed JSON), typed ORM `Mapped[...]` columns, and `cast` only where the framework guarantees the type (exception handlers).
- *KnowFlow:* `mypy` over 80 files; e.g. `core/errors.py::_app_error` uses `cast(AppError, exc)`.
- *Follow-up:* Where is `type: ignore` used? → *Answer:* Rarely; e.g. `runner.py` reading `rrf_k` from a JSONB config dict.

## 3. FastAPI

**3.1 [Beginner] How does FastAPI validate a request?**
- *Short:* From type hints: Pydantic models for bodies, typed params for path/query; failures → 422.
- *Detailed:* KnowFlow overrides the default 422 body to its own envelope with `fields: [{loc, msg, type}]` and no input values.
- *KnowFlow:* `core/errors.py::_validation_error`.
- *Follow-up:* Why hide input values? → *Answer:* They can contain user data or secrets (e.g. a connection password).

**3.2 [Beginner] What does `Depends` give you?**
- *Short:* Dependency injection: sessions, settings, storage and the workspace are provided per request and overridable in tests.
- *Detailed:* `Annotated` aliases (`SessionDep`, …) keep signatures short; `get_session` is a generator dependency so the session closes after the response.
- *KnowFlow:* `api/deps.py`, `db/session.py::get_session`.
- *Follow-up:* How do tests use it? → *Answer:* `app.dependency_overrides[get_session] = …` to point at a test database or temp storage.

**3.3 [Intermediate] `def` or `async def` endpoints — what does KnowFlow do and why?**
- *Short:* Plain `def`, run in FastAPI's threadpool.
- *Detailed:* The DB driver is sync psycopg 3 (async mode doesn't support Windows' Proactor loop), model calls are blocking httpx; `async def` with blocking calls would freeze the event loop.
- *KnowFlow:* `db/session.py` docstring.
- *Follow-up:* Cost? → *Answer:* Concurrency bounded by the threadpool (~40 threads by default); irrelevant here since generation is capped at 1.

**3.4 [Intermediate] How are middleware ordered, and why does it matter here?**
- *Short:* Last added runs first; the request-id middleware wraps the upload limiter so even 413s carry a request id.
- *Detailed:* `UploadSizeLimitMiddleware` is raw ASGI and must run before multipart parsing because Starlette spools bodies to disk before the endpoint.
- *KnowFlow:* `app/main.py`, `core/upload_limit.py`.
- *Follow-up:* Why also check size while streaming? → *Answer:* `Content-Length` can lie or include multipart overhead; `FileStorage.receive` counts real bytes.

**3.5 [Advanced] How do you return different status codes from one endpoint?**
- *Short:* Inject `Response` and set `status_code`, or raise `AppError`.
- *Detailed:* `upload_document` returns 202 for created/reindexed, sets 200 for `skipped`; `/health/ready` sets 503 but still returns the body so the UI can show what's down.
- *KnowFlow:* `api/v1/documents.py::upload_document`, `api/v1/health.py::ready`.
- *Follow-up:* How does the client cope with 503 bodies? → *Answer:* `requestJson(..., acceptStatuses=[503])` treats it as data.

**3.6 [Expert] How would you add streaming answers to this API?**
- *Short:* A `StreamingResponse` (or SSE) that forwards Ollama's streamed tokens.
- *Detailed:* The hard part is citation verification: markers can only be verified once complete, so stream text but finalise citations at the end (or buffer per sentence). Persistence happens after the stream; the generation gate must be held for the whole stream.
- *KnowFlow:* NOT IMPLEMENTED; `OllamaClient.chat` sends `stream: false`.
- *Follow-up:* What about the Next.js proxy? → *Answer:* Rewrites can stream, but timeouts and buffering need checking end to end (Caddy too).

## 4. REST APIs

**4.1 [Beginner] Why does upload return 202 instead of 201?**
- *Short:* The resource exists, but processing continues asynchronously.
- *Detailed:* The body includes `job_id` and `status: queued`; clients poll `GET /documents` or `GET /jobs/{id}`.
- *KnowFlow:* `POST /api/v1/documents`.
- *Follow-up:* Alternatives to polling? → *Answer:* SSE/WebSockets or webhooks; polling every 2 s is simplest for a single user.

**4.2 [Beginner] How are errors shaped?**
- *Short:* One envelope: `{"error": {"code", "message", "request_id", "fields"?, "details"?}}`.
- *Detailed:* Stable machine codes (`duplicate_document`, `generation_busy`) plus user-safe messages; never stack traces.
- *KnowFlow:* `core/errors.py`.
- *Follow-up:* Why both code and message? → *Answer:* Code for program logic (the UI branches on `duplicate_document`), message for people.

**4.3 [Intermediate] Explain the duplicate-upload contract.**
- *Short:* Same bytes → 409 with the existing document and `choices: [skip, reindex, new_version]`; re-send with `?on_duplicate=`.
- *Detailed:* Duplicates are detected by SHA-256 per workspace; `new_version` increments `version` (unique `(workspace_id, sha256, version)`).
- *KnowFlow:* `documents/service.py::_duplicate_error`, `upload_document`.
- *Follow-up:* Why make the client decide? → *Answer:* Only the user knows whether it's a mistake, a re-index, or an intentional new version.

**4.4 [Intermediate] Are deletes idempotent?**
- *Short:* Yes: deleting something that doesn't exist returns 204.
- *Detailed:* Documents, conversations and SQL connections; the demo connection returns 409. Ownership is checked first, so another workspace's document is "absent" and its file is never touched.
- *KnowFlow:* `delete_document`, `sql_assistant/service.py::delete_connection`.
- *Follow-up:* Downside? → *Answer:* A typo'd id silently succeeds; acceptable for idempotent retries, and the audit trail still records the call.

**4.5 [Advanced] How is pagination done?**
- *Short:* `limit`/`offset` with a `Page[T]` response containing items and total.
- *Detailed:* Generic Pydantic model `class Page[T](BaseModel)`; fine for small lists; keyset pagination would be the next step at scale.
- *KnowFlow:* `schemas/common.py::Page`, `GET /documents?limit&offset`.
- *Follow-up:* Why keyset at scale? → *Answer:* OFFSET scans and discards rows; keyset uses the index directly and is stable under inserts.

**4.6 [Expert] Is `POST /chat/query` idempotent? Should it be?**
- *Short:* No — each call generates and stores a new turn.
- *Detailed:* To make retries safe you'd accept an idempotency key and return the stored answer for repeats; useful because answers take ~a minute and clients time out.
- *KnowFlow:* NOT IMPLEMENTED; client timeout is 600 s.
- *Follow-up:* Where to store keys? → *Answer:* A unique column on `messages` or a small table with TTL.

## 5. Next.js and TypeScript

**5.1 [Beginner] What's the App Router layout here?**
- *Short:* `app/layout.tsx` wraps all pages with providers and the shell; each route is a small server page rendering one client view.
- *Detailed:* 8 routes plus `not-found.tsx`; titles via `metadata` and a template.
- *KnowFlow:* `apps/web/src/app/*`.
- *Follow-up:* Why are the views client components? → *Answer:* They hold state, poll, and handle uploads — all browser work.

**5.2 [Beginner] Why validate API responses at runtime in TypeScript?**
- *Short:* Types disappear at runtime; the API is an external input.
- *Detailed:* Small validators (`obj`, `str`, `int`, `oneOf`, `arr`) throw on bad shapes → `invalid_response` error, instead of the UI crashing later.
- *KnowFlow:* `lib/api/validate.ts`, `parseAnswer` in `lib/api/chat.ts`.
- *Follow-up:* Why not zod? → *Answer:* Kept dependency-free deliberately; zod would be fine.

**5.3 [Intermediate] How does upload progress work?**
- *Short:* XMLHttpRequest, because `fetch` has no upload-progress events.
- *Detailed:* `xhr.upload.onprogress` drives the bar; a client-side `precheckFile` rejects bad extensions/sizes before sending.
- *KnowFlow:* `lib/api/documents.ts::uploadDocument`, `precheckFile`; `library/use-upload-queue.ts`.
- *Follow-up:* Can the server trust the precheck? → *Answer:* No; it's UX only. The server validates everything again.

**5.4 [Intermediate] How are timeouts handled in the client?**
- *Short:* `AbortSignal.timeout` per call, combined with a caller signal via `AbortSignal.any`.
- *Detailed:* Defaults to 10 s; chat gets 600 s, model validation 300 s. Timeout → `ApiError("timeout")`; network failure → `api_unreachable`.
- *KnowFlow:* `lib/api/client.ts::requestJson`.
- *Follow-up:* Why distinguish them? → *Answer:* Different user advice: "slow model" vs "API down".

**5.5 [Advanced] How is responsiveness verified?**
- *Short:* Playwright checks every page for horizontal overflow at 390/820/1440 px in CI config; a live check covered 12 widths 320–2560.
- *Detailed:* The fix pattern for tables: scroll inside their own container so the page never widens.
- *KnowFlow:* `apps/web/e2e/smoke.spec.ts`; commit `b36571d`.
- *Follow-up:* What can automation miss? → *Answer:* Overlaps and readability; that's why screenshots were also reviewed.

**5.6 [Expert] How would you add optimistic UI for chat?**
- *Short:* Render the user's message immediately with a pending assistant bubble; reconcile with the server's ids.
- *Detailed:* Keep a temp id; on error, mark the bubble failed with a retry; on success, replace with the stored message and citations. Disable sending while one is in flight (server gate allows 1).
- *KnowFlow:* `ask-view.tsx` already shows a pending state while `askQuestion` runs.
- *Follow-up:* With streaming? → *Answer:* Append tokens to the pending bubble; finalise citations at the end.

## 6. PostgreSQL

**6.1 [Beginner] What's a generated column and why use one for search?**
- *Short:* A column computed by Postgres from other columns; it can't drift from the source.
- *Detailed:* `search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(section_path,'') || ' ' || text)) STORED`.
- *KnowFlow:* `db/models.py::Chunk.search_tsv`, migration 0002.
- *Follow-up:* Cost? → *Answer:* Computed on every insert/update and stored, so writes are a bit slower and rows bigger.

**6.2 [Beginner] What do the CHECK constraints protect?**
- *Short:* Data invariants the app also enforces: valid statuses, file types, positive sizes, SHA-256 format.
- *Detailed:* Defence in depth: a bug or manual SQL can't store an impossible status.
- *KnowFlow:* `ck_documents_status_valid`, `ck_documents_sha256_hex`, `ck_chunks_page_range_valid`.
- *Follow-up:* Why also in code? → *Answer:* Code gives friendly errors earlier; the DB is the last line.

**6.3 [Intermediate] Explain `FOR UPDATE SKIP LOCKED`.**
- *Short:* Lock the selected row; other transactions skip locked rows instead of waiting.
- *Detailed:* Lets N workers pull distinct jobs from one table without a broker.
- *KnowFlow:* `claim_next_job`, `recover_stale_jobs`, `runner.claim_next_run`.
- *Follow-up:* What if the worker dies mid-job? → *Answer:* The lock is released with the connection; the job stays `running` until its heartbeat is stale (300 s), then it's re-queued.

**6.4 [Intermediate] How does the SQL Analyst stay read-only at the database level?**
- *Short:* A login role with only SELECT, `default_transaction_read_only = on`, and a role-level statement timeout.
- *Detailed:* Created by the seed script; `CONNECT` on the app DB revoked from PUBLIC; each query also runs `SET TRANSACTION READ ONLY`.
- *KnowFlow:* `sql_assistant/demo.py::seed`, `database.py::execute`.
- *Follow-up:* Why both role default and SET TRANSACTION? → *Answer:* Either alone could be misconfigured on a user-added connection; layers.

**6.5 [Advanced] What does `pool_pre_ping=True` buy you?**
- *Short:* It tests a pooled connection before use, so a Postgres restart doesn't cause errors on stale connections.
- *Detailed:* Combined with 3 s pool/connect timeouts, a dead DB produces a fast `503 database_unavailable` instead of hanging.
- *KnowFlow:* `db/session.py::get_engine`, `core/errors.py::_database_error`.
- *Follow-up:* Cost? → *Answer:* One cheap round trip per checkout.

**6.6 [Expert] How would you make re-indexing zero-downtime?**
- *Short:* Build the new embedding version alongside the old, then switch the active flag.
- *Detailed:* KnowFlow already stores vectors per `embedding_version_id`, but `_complete` rewrites chunks per document and the active version switches at probe time; a blue/green approach would keep the old active until all documents have new vectors, then flip `is_active` (the partial unique index guarantees one active).
- *KnowFlow:* `embedding_versions`, `uq_embedding_versions_single_active`, `ensure_embedding_version`.
- *Follow-up:* What about chunk ids? → *Answer:* They change on re-chunking, which is why evaluation labels use evidence matchers, not ids.

## 7. Database indexing

**7.1 [Beginner] Which index serves the document list?**
- *Short:* `ix_documents_workspace_created (workspace_id, created_at)`.
- *Detailed:* Matches `WHERE workspace_id = ? ORDER BY created_at`.
- *KnowFlow:* `db/models.py`.
- *Follow-up:* Column order? → *Answer:* Equality column first, then the sort column.

**7.2 [Beginner] What's a GIN index and why is it on `search_tsv`?**
- *Short:* An inverted index (lexeme → rows), ideal for `@@` full-text matches.
- *Detailed:* Without it every query would scan and evaluate every tsvector.
- *KnowFlow:* `ix_chunks_search_tsv USING gin`.
- *Follow-up:* GIN vs GiST for FTS? → *Answer:* GIN is faster to query, slower to update; right for read-heavy search.

**7.3 [Intermediate] What's a partial unique index used for here?**
- *Short:* Enforcing "at most one row with flag = true".
- *Detailed:* `CREATE UNIQUE INDEX … ON workspaces(is_default) WHERE is_default`; same for the active embedding version.
- *KnowFlow:* `uq_workspaces_single_default`, `uq_embedding_versions_single_active`; tested in `test_second_default_workspace_is_rejected`.
- *Follow-up:* Alternative? → *Answer:* A trigger or a singleton table; the partial index is declarative and cheap.

**7.4 [Intermediate] Why is there no vector index?**
- *Short:* Exact search is fast at this size, and the `vector` column is untyped, so HNSW can't be built on it directly.
- *Detailed:* TRD: "exact first, HNSW only if measured". Untyped lets multiple embedding versions/dimensions coexist.
- *KnowFlow:* `chunk_embeddings.embedding Vector()`; `retrieval/dense.py` docstring.
- *Follow-up:* How to add one? → *Answer:* Typed `vector(768)` column (or expression index with a cast) per version, `USING hnsw (… vector_cosine_ops)`, then compare recall@K with exact.

**7.5 [Advanced] Which index supports job claiming?**
- *Short:* `ix_ingestion_jobs_status_created (status, created_at)`.
- *Detailed:* The claim query filters `status='queued'` and orders by `created_at`.
- *KnowFlow:* `claim_next_job`.
- *Follow-up:* Would a partial index be better? → *Answer:* `WHERE status = 'queued'` would be smaller as history grows.

**7.6 [Expert] HNSW vs IVFFlat in pgvector?**
- *Short:* HNSW: better recall/latency, slower build, more memory; IVFFlat: faster build, needs training lists and probes, lower recall.
- *Detailed:* Tune HNSW with `m`, `ef_construction`, query-time `ef_search`; IVFFlat with `lists` and `probes`. Filters (workspace) interact with ANN — post-filtering can drop recall.
- *KnowFlow:* neither implemented.
- *Follow-up:* How do you test an ANN index? → *Answer:* Recall@K of ANN vs exact on the evaluation queries, plus p95 latency.

## 8. Vector databases

**8.1 [Beginner] What is a vector database?**
- *Short:* Storage plus nearest-neighbour search over embeddings, usually with metadata filters.
- *Detailed:* Dedicated ones add ANN indexes, sharding and replication; pgvector adds the same core to Postgres.
- *KnowFlow:* pgvector in Postgres 16 (0.8.7 on the Azure VM).
- *Follow-up:* What does KnowFlow filter on? → *Answer:* Embedding version, workspace, chunking strategy, document status, optional document ids.

**8.2 [Beginner] Cosine distance vs inner product vs L2?**
- *Short:* Cosine compares direction; inner product also weights magnitude; L2 is geometric distance.
- *Detailed:* For normalised vectors they rank identically. pgvector operators: `<=>` cosine distance, `<#>` negative inner product, `<->` L2.
- *KnowFlow:* `cosine_distance` → `<=>`; score = `1 − distance`.
- *Follow-up:* Why cosine for text? → *Answer:* Embedding models are trained with cosine-style objectives; magnitude isn't meaningful.

**8.3 [Intermediate] How do you avoid mixing vectors from different models?**
- *Short:* Every vector row has an `embedding_version_id`; search compares only the active version.
- *Detailed:* The version records model, digest and probed dimension (unique together).
- *KnowFlow:* `chunk_embeddings` PK `(chunk_id, embedding_version_id)`; `dense_search` filter.
- *Follow-up:* What if the model is updated under the same tag? → *Answer:* The digest changes → a new version is created.

**8.4 [Intermediate] Metadata filtering: before or after the vector search?**
- *Short:* Here, in the same SQL query (WHERE + ORDER BY distance).
- *Detailed:* With exact search the filter is applied first and results are exact. With ANN indexes, filters can reduce recall (post-filtering) unless the index supports filtered search or you partition.
- *KnowFlow:* `lexical.py::scoped` reused by `dense.py`.
- *Follow-up:* How would you scale per-tenant? → *Answer:* Partition or partial indexes by workspace, or one collection per tenant in a dedicated DB.

**8.5 [Advanced] When is pgvector the wrong choice?**
- *Short:* Very large corpora with high QPS, multi-region, or when you need features like built-in hybrid scoring at scale.
- *Detailed:* Single-node Postgres limits; index builds are heavy; vacuum on large vector tables.
- *KnowFlow:* fine at 5 documents; ADR-003 records the trade-off.
- *Follow-up:* Migration path? → *Answer:* Keep the retrieval interface (`retrieve`) and swap `dense_search` for a client to the new store.

**8.6 [Expert] How do you evaluate a vector store change?**
- *Short:* Same gold set, same embeddings, compare Recall@K/MRR and p95 latency vs the exact baseline.
- *Detailed:* KnowFlow's runs store config, so you'd add the index type as a recorded setting and run on dev, then once on test.
- *KnowFlow:* Evaluation Lab presets; `evaluation_runs.config`.
- *Follow-up:* What else? → *Answer:* Index build time, memory, write latency during ingestion.

## 9. Embeddings

**9.1 [Beginner] What is an embedding?**
- *Short:* A fixed-length vector representing meaning, so similar texts are close.
- *Detailed:* Produced by an encoder model; compared with cosine similarity.
- *KnowFlow:* `nomic-embed-text:v1.5`, 768 dimensions (probed).
- *Follow-up:* Why probe instead of hard-coding 768? → *Answer:* Models change; probing prevents storing incompatible vectors (`embedding_dimension_changed`).

**9.2 [Beginner] Why "search_query:" and "search_document:" prefixes?**
- *Short:* nomic was trained with task prefixes; without them retrieval quality drops.
- *Detailed:* Asymmetric retrieval: short questions vs long passages.
- *KnowFlow:* `registry.py::task_prefixes`, stored on `embedding_versions`.
- *Follow-up:* What if you switch to a model without prefixes? → *Answer:* `task_prefixes` returns empty strings for other models.

**9.3 [Intermediate] What text exactly gets embedded for a chunk?**
- *Short:* Section path + newline + chunk text.
- *Detailed:* Headings add context ("Annual leave") that the passage may not repeat.
- *KnowFlow:* `embedding_stage.py::embedding_text`.
- *Follow-up:* Risk? → *Answer:* Long section paths dominate short chunks; could weight or trim.

**9.4 [Intermediate] How are embedding outputs validated?**
- *Short:* Same count as inputs, same dimension, all finite numbers.
- *Detailed:* `validate_vectors` raises `model_bad_response` or `embedding_dimension_changed`.
- *KnowFlow:* `ollama.py::validate_vectors`; test `test_vector_validation_rejects_wrong_dimension_and_non_finite_values`.
- *Follow-up:* Why check finite? → *Answer:* A NaN in a vector makes every distance NaN and silently breaks ranking.

**9.5 [Advanced] Bi-encoder vs cross-encoder?**
- *Short:* Bi-encoders embed texts separately (fast, indexable); cross-encoders read pairs together (accurate, slow).
- *Detailed:* Use bi-encoder for recall over the corpus, cross-encoder to rerank a shortlist.
- *KnowFlow:* nomic (bi-encoder) + optional `bge-reranker-v2-m3` (cross-encoder, not installed).
- *Follow-up:* Cost of the cross-encoder? → *Answer:* One forward pass per (query, candidate) — 20 per question here.

**9.6 [Expert] How would you choose an embedding model properly?**
- *Short:* Measure on your own labelled queries, not a leaderboard alone.
- *Detailed:* Compare Recall@K/MRR on the dev split, check dimension (storage, speed), max input length (truncation), CPU latency, licence; re-index cost. KnowFlow's Settings flow (validate → save → reindex) plus the Evaluation Lab support exactly this.
- *KnowFlow:* `POST /settings/models/validate`, `PUT /settings/models`, `POST /settings/reindex`.
- *Follow-up:* What's Matryoshka truncation? → *Answer:* Some models (nomic v1.5 among them, per its model card) allow using a prefix of the vector at lower dimension with modest loss; KnowFlow doesn't use it.

## 10. RAG

**10.1 [Beginner] What is retrieval-augmented generation?**
- *Short:* Retrieve relevant passages for a question, put them in the prompt, and have the model answer only from them.
- *Detailed:* Reduces hallucination and lets answers cite sources; quality depends on retrieval first.
- *KnowFlow:* `rag/service.py::ask` → `retrieve` → `answer_question`.
- *Follow-up:* Does RAG eliminate hallucination? → *Answer:* No. KnowFlow verifies that citations point to supplied passages, but a cited sentence can still be wrong (the 24-vs-26-days case).

**10.2 [Beginner] What happens when nothing relevant is found?**
- *Short:* It abstains with "No supporting source found".
- *Detailed:* Four reasons: `no_sources`, `weak_evidence` (dense max cosine < 0.45, no model call), `model_abstained`, `unsupported` (no valid citation survived).
- *KnowFlow:* `rag/answer.py::ABSTAIN_TEXT`, `answer_question`.
- *Follow-up:* How did abstention score? → *Answer:* 12/12 correct on the held-out test split, 7/7 on the safety probes (evaluation report).

**10.3 [Intermediate] How is the context window budgeted?**
- *Short:* Up to 6000 characters of de-duplicated passages in rank order.
- *Detailed:* `pack_context` skips the same chunk or a passage contained in another from the same document; always keeps at least one.
- *KnowFlow:* `rag_context_chars = 6000`, `rag_top_k = 6`.
- *Follow-up:* Why characters, not tokens? → *Answer:* No tokenizer offline; ~4 chars/token is a safe estimate for `num_ctx = 4096`.

**10.4 [Intermediate] How do you restrict an answer to certain documents?**
- *Short:* `document_ids` in the request; validated as ready and in the workspace, then applied in the retrieval SQL.
- *Detailed:* Invalid scope → 422 `invalid_document_scope`.
- *KnowFlow:* `ChatQuery.document_ids`, `_validate_documents`, `Scope.document_ids`; test `test_document_scope_is_validated_and_applied`.
- *Follow-up:* Why validate before retrieving? → *Answer:* To give a clear error instead of a silent empty result.

**10.5 [Advanced] What's stored per answer, and why?**
- *Short:* The answer, citations, and metadata: retrieval trace (mode, timings, candidate ranks), model, prompt version, tokens, latency.
- *Detailed:* Enables error analysis (retrieval vs generation), reproducibility (prompt version), and the Activity summary (median answer time).
- *KnowFlow:* `messages.citations`, `messages.metadata` (ADR-000 G-3).
- *Follow-up:* Privacy? → *Answer:* Stored in the local DB, never logged; logs carry only ids/counts/timings.

**10.6 [Expert] How would you add multi-turn context safely?**
- *Short:* Rewrite the follow-up into a standalone question using recent turns, then retrieve as usual.
- *Detailed:* Feeding raw history into the answer prompt inflates context and can import unsupported claims from earlier answers; a rewrite step keeps retrieval grounded. Cost: one more model call (~tens of seconds on CPU), which is why it isn't done.
- *KnowFlow:* NOT IMPLEMENTED; turns are stored per conversation.
- *Follow-up:* How to evaluate it? → *Answer:* A conversational gold set with follow-ups whose evidence differs from the first turn.

## 11. Chunking

**11.1 [Beginner] Why chunk at all?**
- *Short:* Retrieval and prompts work on passages, not whole documents.
- *Detailed:* Too big → diluted embeddings and wasted context; too small → missing context.
- *KnowFlow:* 1200 chars, 200 overlap (fixed).
- *Follow-up:* Why 1200? → *Answer:* A default from the TRD that fits several passages into a 4096-token context; not tuned on the dev split yet.

**11.2 [Beginner] Fixed vs recursive?**
- *Short:* Fixed = sliding windows with overlap ignoring structure; recursive = split on paragraph/line/sentence/word inside each section and merge up to the size.
- *Detailed:* Recursive never crosses a page or heading boundary, so citations stay precise.
- *KnowFlow:* `chunk_fixed`, `chunk_recursive` (ADR-005).
- *Follow-up:* What did you measure? → *Answer:* Fixed: Recall@5 0.989 but MRR 0.837; recursive dense: Recall 0.947, MRR 0.879.

**11.3 [Intermediate] Why store both strategies?**
- *Short:* So the Evaluation Lab compares them on identical documents without re-ingesting.
- *Detailed:* `chunks.strategy` with unique `(document_id, strategy, chunk_index)`; retrieval filters by strategy.
- *KnowFlow:* `process_job` chunks with every strategy in `STRATEGIES`.
- *Follow-up:* Production cost? → *Answer:* Double storage and embedding time; you'd keep only the winner.

**11.4 [Intermediate] How does the fixed chunker avoid cutting words?**
- *Short:* `_snap_end` moves the cut back to the last space/newline in the second half of the window.
- *Detailed:* If none exists it cuts at the size; `start = max(end − overlap, start + 1)` guarantees progress.
- *KnowFlow:* `chunking.py::_snap_end`.
- *Follow-up:* Edge case? → *Answer:* A 3000-char URL with no spaces gets cut mid-token.

**11.5 [Advanced] How are page numbers kept for fixed chunks that span pages?**
- *Short:* Offsets of each unit in the joined text are tracked; a chunk's pages are the min/max of units it overlaps.
- *Detailed:* `spans: list[(start, end, unit)]`; units are joined with `"\n\n"` (+2 offset).
- *KnowFlow:* `chunk_fixed`.
- *Follow-up:* Section path? → *Answer:* Taken from the first covered unit — imprecise for spanning chunks, another reason recursive cites better.

**11.6 [Expert] What chunking would you try next?**
- *Short:* Tune size on dev; semantic chunking (split where embedding similarity drops); parent-child (retrieve small, show larger).
- *Detailed:* The semantic chunking experiment is listed as not built (README). Parent-child fits the existing `document_sections` table as the "parent".
- *KnowFlow:* `document_sections` stores units; NOT IMPLEMENTED.
- *Follow-up:* Cost of semantic chunking? → *Answer:* Embedding every sentence during ingestion — slow on CPU.

## 12. Hybrid search

**12.1 [Beginner] What is hybrid search?**
- *Short:* Combining semantic (vector) and keyword search results.
- *Detailed:* Each catches what the other misses; results are fused.
- *KnowFlow:* `retrieve(mode="hybrid")` → dense + lexical → `rrf`.
- *Follow-up:* Result? → *Answer:* S3 hybrid beat S2 dense on every metric (nDCG@5 0.905 vs 0.891).

**12.2 [Beginner] Why did plain Postgres FTS return nothing for questions?**
- *Short:* `plainto_tsquery` ANDs every term, and a whole question rarely appears in one chunk.
- *Detailed:* Measured 0 hits for "How much can I spend on a hotel per night?"; KnowFlow ORs the lexemes instead.
- *KnowFlow:* `lexical.py::any_terms_query`.
- *Follow-up:* Doesn't OR return too much? → *Answer:* Yes, which is why ranking matters: `ts_rank_cd` favours chunks with more terms closer together.

**12.3 [Intermediate] What does `ts_rank_cd(..., 32)` mean?**
- *Short:* Cover-density ranking (proximity-aware) normalised as rank/(rank+1).
- *Detailed:* Normalisation 32 bounds scores to (0,1) so they're comparable across queries.
- *KnowFlow:* `lexical_search`.
- *Follow-up:* Is that BM25? → *Answer:* No; Postgres FTS has no BM25 built in. It behaves similarly enough for short chunks here.

**12.4 [Intermediate] Why is lexical-only so strong on your set?**
- *Short:* The questions reuse the documents' words and identifiers.
- *Detailed:* MRR 0.901 lexical vs 0.891 hybrid; codes like `SEC-USB`, `FIN-TE-07` are exact-match wins.
- *KnowFlow:* evaluation report.
- *Follow-up:* So why not lexical in production? → *Answer:* Paraphrased questions would fail; hybrid is robust to both, and that's untested here — say so.

**12.5 [Advanced] What does the hybrid cost in latency?**
- *Short:* About 2 ms more than dense (lexical p50 2 ms); dense is dominated by embedding the query (~40 ms).
- *Detailed:* Retrieval p50: S2 40 ms, S3 42 ms.
- *KnowFlow:* evaluation report.
- *Follow-up:* Run them in parallel? → *Answer:* Possible, but the saving (~2 ms) isn't worth threads here.

**12.6 [Expert] Why is the weak-evidence threshold disabled in hybrid mode?**
- *Short:* Hybrid scores are RRF values (~0.03), not cosine similarities, so a 0.45 threshold is meaningless.
- *Detailed:* The gate is applied only when `result.mode == "dense"`.
- *KnowFlow:* `rag/service.py::ask`, `runner.py::score_case`.
- *Follow-up:* How would you gate hybrid? → *Answer:* Use the dense component's max cosine from the candidates' trace, or a calibrated threshold on RRF.

## 13. RRF

**13.1 [Beginner] Give the RRF formula.**
- *Short:* `score(d) = Σ_r 1 / (k + rank_r(d))`, with k = 60.
- *Detailed:* Ranks start at 1; documents missing from a list get nothing from it.
- *KnowFlow:* `retrieval/fusion.py::rrf`.
- *Follow-up:* Compute: rank 1 in dense, rank 3 in lexical? → *Answer:* 1/61 + 1/63 = 0.03227.

**13.2 [Beginner] Why rank-based fusion?**
- *Short:* Scores from different retrievers aren't comparable; ranks are.
- *Detailed:* Cosine ~0.4–0.9 vs ts_rank_cd ~0–1 with different distributions.
- *KnowFlow:* fusion docstring.
- *Follow-up:* What's lost? → *Answer:* Confidence information — a huge score gap counts the same as a tiny one.

**13.3 [Intermediate] What does k do?**
- *Short:* Controls how much top ranks dominate; larger k flattens differences.
- *Detailed:* k = 60: rank 1 vs 2 differ by 0.00026; so appearing in both lists matters more than being first in one.
- *KnowFlow:* `RRF_K` setting, recorded per run.
- *Follow-up:* Tuned? → *Answer:* No — the standard value; tuning would happen on the dev split.

**13.4 [Intermediate] How are ties broken?**
- *Short:* By chunk id, for determinism.
- *Detailed:* `sorted(..., key=lambda c: (-score, str(chunk_id)))`.
- *KnowFlow:* `rrf`.
- *Follow-up:* Why care? → *Answer:* Reproducible evaluation runs.

**13.5 [Advanced] How many candidates go into fusion?**
- *Short:* 20 from each retriever (`rag_candidates`), then top_k after fusion.
- *Detailed:* More candidates → better fusion recall, slightly more work; irrelevant at this corpus size.
- *KnowFlow:* `RetrievalConfig.candidates`.
- *Follow-up:* What if a chunk is rank 21 in dense? → *Answer:* It contributes nothing from dense.

**13.6 [Expert] Alternatives to RRF and when they win.**
- *Short:* Normalised weighted sum, CombSUM/CombMNZ, learned fusion.
- *Detailed:* Weighted score fusion can beat RRF when one retriever is reliably better and scores are calibrated; learned fusion needs labelled data at scale.
- *KnowFlow:* RRF only.
- *Follow-up:* How to compare? → *Answer:* Add a preset with the new fusion and compare on dev in the Evaluation Lab.

## 14. Reranking

**14.1 [Beginner] What does a reranker do?**
- *Short:* Re-scores a shortlist of candidates with a more accurate (slower) model.
- *Detailed:* A cross-encoder reads (question, passage) together.
- *KnowFlow:* `models/reranker.py::CrossEncoderReranker`, `rerank`.
- *Follow-up:* Is it used? → *Answer:* Implemented but off and not installed; S4 NOT MEASURED.

**14.2 [Beginner] Which model, and why that one?**
- *Short:* `BAAI/bge-reranker-v2-m3` (configurable `RERANKER_MODEL`).
- *Detailed:* A widely used multilingual cross-encoder; runs on CPU via sentence-transformers.
- *KnowFlow:* `core/config.py::reranker_model`.
- *Follow-up:* Why not installed? → *Answer:* ~2.3 GB of weights + torch on a 7.3 GB laptop; not approved.

**14.3 [Intermediate] How is it loaded?**
- *Short:* Lazily, once per process, behind a lock.
- *Detailed:* `get_reranker` caches instances by model name; `_load` checks the package exists first and raises `reranker_unavailable` otherwise.
- *KnowFlow:* `reranker.py`.
- *Follow-up:* Why lazy? → *Answer:* Startup and memory stay unaffected unless someone asks for reranking.

**14.4 [Intermediate] What happens to scores and ranks?**
- *Short:* `score` becomes the cross-encoder score; `ranks["rerank"]` is added; earlier ranks are kept.
- *Detailed:* The trace still shows dense/lexical ranks for analysis.
- *KnowFlow:* `rerank()`.
- *Follow-up:* And the weak-evidence gate? → *Answer:* Not applied (mode is `hybrid+rerank`).

**14.5 [Advanced] What latency would you expect?**
- *Short:* Not measured; roughly one CPU forward pass per candidate (20), likely seconds on CPU.
- *Detailed:* Negligible next to 30–60 s of generation, but measurable; that's what S4 would record.
- *KnowFlow:* NOT MEASURED.
- *Follow-up:* How to reduce? → *Answer:* Fewer candidates (10), a smaller cross-encoder, GPU, or ONNX.

**14.6 [Expert] How would you decide whether to enable it?**
- *Short:* Run S4 vs S3 on dev; enable only if MRR/nDCG improve meaningfully for acceptable latency, confirm once on test.
- *Detailed:* The setting stays off "unless measured to help" (config comment); ADR-004.
- *KnowFlow:* `ENABLE_RERANKER=false`.
- *Follow-up:* What if recall is already 0.97? → *Answer:* Reranking improves ordering (MRR/nDCG), not recall@20.

## 15. LLM fundamentals

**15.1 [Beginner] Which LLM does KnowFlow use and why?**
- *Short:* `qwen3:4b` via Ollama — small enough for a CPU laptop, decent at instructions and JSON.
- *Detailed:* Recorded as Q4_K_M with its digest; `qwen3:8b` suggested for 16 GB+ machines.
- *KnowFlow:* `.env.example`, evaluation report.
- *Follow-up:* Weaknesses observed? → *Answer:* Invalid SQL sometimes; ignored the "cite each side" rule on a dated conflict.

**15.2 [Beginner] What is temperature?**
- *Short:* Randomness of sampling; lower = more deterministic.
- *Detailed:* RAG 0.1, SQL 0.0 in KnowFlow.
- *KnowFlow:* `rag_temperature`, `assistant.py::generate`.
- *Follow-up:* Is 0 fully deterministic? → *Answer:* Mostly, but no seed is set and hardware/threads can still cause small differences.

**15.3 [Intermediate] What's `num_ctx` and `num_predict`?**
- *Short:* Context window size and max output tokens for an Ollama call.
- *Detailed:* 4096 context; 700 output tokens for RAG, 1000 for SQL.
- *KnowFlow:* `OllamaClient.chat` options.
- *Follow-up:* What if output hits the limit? → *Answer:* `done_reason == "length"`; broken JSON then raises `model_output_truncated`.

**15.4 [Intermediate] Why `think: false` for qwen3?**
- *Short:* Qwen3 can emit a reasoning trace; KnowFlow disables it to save CPU time for structured answers.
- *Detailed:* The schema-constrained JSON doesn't need hidden reasoning.
- *KnowFlow:* `ollama.py::OllamaClient.chat`.
- *Follow-up:* Would thinking help the conflict case? → *Answer:* Possibly — an experiment worth running on dev, at a latency cost.

**15.5 [Advanced] What is quantisation and what's Q4_K_M?**
- *Short:* Storing weights in fewer bits; Q4_K_M is a 4-bit GGUF K-quant (medium).
- *Detailed:* ~4× smaller than FP16, faster on CPU, small quality loss.
- *KnowFlow:* reported per model on the Settings page (`InstalledModel.quantization`).
- *Follow-up:* Memory use? → *Answer:* NOT MEASURED in the repo.

**15.6 [Expert] How would you pick between a bigger local model and a hosted API?**
- *Short:* Measure answer quality and latency on the same gold set; weigh privacy/cost constraints.
- *Detailed:* The `ChatModel` protocol makes the swap cheap; ADR-007 forbids hosted APIs in this project by design.
- *KnowFlow:* `registry.chat_model`.
- *Follow-up:* What metrics? → *Answer:* Abstention accuracy, citation precision, injection resistance, p50/p95 latency — already in the Lab.

## 16. Transformers and attention

**16.1 [Beginner] What does attention do, in one sentence?**
- *Short:* Lets each token weigh every other token when building its representation.
- *Detailed:* `softmax(QKᵀ/√d)·V`.
- *KnowFlow:* theory; relevant to why long prompts are slow on CPU.
- *Follow-up:* Why √d? → *Answer:* Keeps dot products from growing with dimension, so softmax doesn't saturate.

**16.2 [Beginner] Decoder-only vs encoder models?**
- *Short:* Decoders generate left-to-right (LLMs); encoders read the whole input at once (embeddings, cross-encoders).
- *Detailed:* qwen3 is a decoder; nomic and the reranker are encoders.
- *KnowFlow:* the two model roles.
- *Follow-up:* Why can't you index with a cross-encoder? → *Answer:* It needs the query to score each passage.

**16.3 [Intermediate] Why does prompt length dominate CPU latency?**
- *Short:* Prefill processes every prompt token through all layers; attention grows quadratically with length.
- *Detailed:* KnowFlow caps sources at 6000 chars and context at 4096 tokens.
- *KnowFlow:* `rag_context_chars`, `num_ctx`.
- *Follow-up:* What's the KV cache? → *Answer:* Stored keys/values of past tokens so each new token doesn't recompute them.

**16.4 [Intermediate] What is positional information and why does it matter for long context?**
- *Short:* Models need token positions; methods like RoPE encode them; quality can degrade far from training lengths.
- *Detailed:* "Lost in the middle": facts in the middle of long contexts are used less reliably — one reason to keep context short and ranked.
- *KnowFlow:* rank-ordered packing.
- *Follow-up:* Would putting the best passage last help? → *Answer:* Possibly; untested here.

**16.5 [Advanced] How does constrained decoding to a JSON schema work?**
- *Short:* At each step, tokens that would make the output invalid under the schema/grammar are masked out.
- *Detailed:* Ollama's `format` parameter; guarantees syntactic validity in most cases, not semantic correctness.
- *KnowFlow:* `format = ANSWER_SCHEMA / SQL_SCHEMA`.
- *Follow-up:* Then why validate? → *Answer:* Length cut-offs, wrong-but-valid content, and defence in depth.

**16.6 [Expert] Why can a small model ignore an instruction like "cite each side"?**
- *Short:* Limited capacity to track multiple constraints; the instruction competes with "answer in 1–4 sentences" and the strong first passage.
- *Detailed:* Fixes: make conflicts explicit in the prompt (mark superseded docs, add dates), post-check for multiple documents with conflicting numbers, or a larger model.
- *KnowFlow:* observed 2026-11-08 (24 vs 26 days).
- *Follow-up:* How to verify a fix? → *Answer:* The 5 dated-conflict cases in the gold set, with labels accepting both documents.

## 17. Ollama and open-source models

**17.1 [Beginner] What does Ollama do?**
- *Short:* Runs local models behind an HTTP API and manages downloads.
- *Detailed:* Endpoints used: `/api/embed`, `/api/chat`, `/api/tags`, `/api/show`, `/api/version`.
- *KnowFlow:* `models/ollama.py::OllamaClient`.
- *Follow-up:* Does the app pull models? → *Answer:* Never; readiness shows the `ollama pull` command.

**17.2 [Beginner] Why `127.0.0.1` and not `localhost` for Ollama?**
- *Short:* On Windows, `localhost` tries IPv6 first and adds ~2 s.
- *Detailed:* Documented in `.env.example`.
- *KnowFlow:* `OLLAMA_BASE_URL`.
- *Follow-up:* Another small config detail that caused a real bug? → *Answer:* Uvicorn's 5 s keep-alive vs the Next.js proxy's pooled sockets → sporadic ECONNRESET/500, fixed with `--timeout-keep-alive 75` (commit `3ea498e`).

**17.3 [Intermediate] How are Ollama errors mapped?**
- *Short:* Timeout → `model_timeout`; connection error → `ollama_unavailable`; 404 → `model_missing`; ≥400 → `model_error` with Ollama's reason.
- *Detailed:* One retry after 2 s on 5xx; retryable errors become 503 at the API.
- *KnowFlow:* `OllamaClient._post`, `_send`; tests in `test_ollama_adapter.py`.
- *Follow-up:* Why retry 5xx once? → *Answer:* On small machines a 5xx often means a model is loading while another is resident.

**17.4 [Intermediate] How does readiness tell "busy" from "down"?**
- *Short:* If a generation holds the gate and the 3-second probe times out, it reports busy.
- *Detailed:* `gate.busy()` counter.
- *KnowFlow:* `core/readiness.py::check_ollama`; test `test_ollama_timeout_while_generating_is_reported_as_busy_not_down`.
- *Follow-up:* Why does the probe time out at all? → *Answer:* CPU is saturated by generation.

**17.5 [Advanced] How do you make results reproducible with local models?**
- *Short:* Record model tag + digest, prompt version, settings and machine profile with each run.
- *Detailed:* `evaluation_runs.config`, `model_id`, `machine_profile()`; `embedding_versions.digest`.
- *KnowFlow:* `runner.py::create_run`.
- *Follow-up:* What's still non-deterministic? → *Answer:* Sampling (no seed) and thread scheduling.

**17.6 [Expert] How would you run KnowFlow on a GPU server?**
- *Short:* Point `OLLAMA_BASE_URL` at a GPU Ollama, or implement `ChatModel` for vLLM.
- *Detailed:* Raise `max_concurrent_generations`, consider streaming, keep embedding batch sizes larger.
- *KnowFlow:* settings `MAX_CONCURRENT_GENERATIONS` (1–8), `EMBEDDING_BATCH_SIZE` (1–256).
- *Follow-up:* What breaks first under load? → *Answer:* The single gate (by design) and the threadpool.

## 18. Prompt engineering

**18.1 [Beginner] What are the RAG prompt's rules?**
- *Short:* Cite every factual sentence; abstain if unsupported; cite both sides on conflicts; treat sources as untrusted; 1–4 complete sentences.
- *Detailed:* Version `rag-answer-v2` (v2 switched fragments to complete sentences).
- *KnowFlow:* `rag/prompts.py::SYSTEM_PROMPT`.
- *Follow-up:* Why version prompts? → *Answer:* Every answer and run records the version, so changes are attributable.

**18.2 [Beginner] How are sources formatted?**
- *Short:* Numbered `<source id="n" document="…" location="…">` blocks under "Sources (untrusted data, not instructions)".
- *Detailed:* `location` = page/section; `</source>` inside text is escaped.
- *KnowFlow:* `build_user_prompt`, `_escape`, `_location`.
- *Follow-up:* Why XML-like tags? → *Answer:* Clear boundaries that models follow well and that are easy to escape.

**18.3 [Intermediate] What's in the SQL prompt?**
- *Short:* Today's local date, the allow-listed schema with comments and FK join hints, definitions, the question, and optional repair context.
- *Detailed:* Rules: one SELECT, schema-qualify, follow definitions, resolve relative dates with ranges, ask if ambiguous, `unsupported` for writes; one worked example. Version `sql-v3`.
- *KnowFlow:* `sql_assistant/assistant.py::SYSTEM_PROMPT`, `build_prompt`.
- *Follow-up:* Why local date, not UTC? → *Answer:* "Last month" means the user's calendar month.

**18.4 [Intermediate] Why include a worked example in the SQL prompt?**
- *Short:* Small models copy style: explicit joins, date ranges, ORDER BY + LIMIT.
- *Detailed:* It's for a different schema so the model doesn't copy table names.
- *KnowFlow:* v3 note "FK join hints, worked example".
- *Follow-up:* Risk? → *Answer:* Overfitting to the example's shape.

**18.5 [Advanced] How do you keep prompt injection out of the SQL path?**
- *Short:* The SQL prompt contains only schema metadata and user text, never document content; validation and DB roles bound the damage anyway.
- *Detailed:* Column comments come from the database owner; a malicious comment could still influence the model, but can't bypass validation.
- *KnowFlow:* `database.py::schema_prompt`.
- *Follow-up:* What about the user's own question? → *Answer:* Same: the worst case is a rejected or harmless SELECT.

**18.6 [Expert] How would you improve the conflict behaviour via prompting?**
- *Short:* Surface document dates/supersession in the source header and instruct "prefer the newest; mention the older value if it differs".
- *Detailed:* The 2024 handbook's heading literally says "superseded"; making that a structured attribute (`status="superseded"`) is clearer for a 4B model. Measure on the 5 dated-conflict cases, bump the prompt version.
- *KnowFlow:* NOT IMPLEMENTED; observed failure 2026-11-08.
- *Follow-up:* Why not just delete old versions? → *Answer:* Users may need history; the PRD asks to present conflicts, not hide them.

## 19. Structured outputs

**19.1 [Beginner] Why force JSON output?**
- *Short:* So the program can read the answer, citations and abstention flag reliably.
- *Detailed:* Free text would need fragile parsing; JSON + schema + Pydantic gives typed data.
- *KnowFlow:* `ANSWER_SCHEMA`, `ModelAnswer`.
- *Follow-up:* Fields? → *Answer:* `answer`, `citations: int[]`, `abstained`, `missing`.

**19.2 [Beginner] What happens on invalid JSON?**
- *Short:* `model_invalid_output` (503, retryable): "Try asking again".
- *Detailed:* If `done_reason == "length"` → `model_output_truncated`.
- *KnowFlow:* `answer_question` except-blocks.
- *Follow-up:* Auto-retry? → *Answer:* Not today — each retry costs 30–60 s on CPU.

**19.3 [Intermediate] Why both a JSON schema in the request and Pydantic after?**
- *Short:* The schema makes valid JSON likely; Pydantic guarantees it before use.
- *Detailed:* Pydantic also enforces limits (≤ 8000 chars, ≤ 50 citations) the schema doesn't.
- *KnowFlow:* `ModelAnswer` field constraints.
- *Follow-up:* Name a semantic check beyond the schema. → *Answer:* SQL: `ready` must include SQL; `clarification_required` must include 2–4 options.

**19.4 [Intermediate] Where do inline markers and the citations list disagree, which wins?**
- *Short:* Inline `[n]` markers in the text are the source of truth.
- *Detailed:* The list is used only if the text has no valid markers; then markers are appended.
- *KnowFlow:* `verify_citations`.
- *Follow-up:* Why? → *Answer:* Markers show which sentence uses which source; a bare list doesn't.

**19.5 [Advanced] How is the SQL output schema different?**
- *Short:* A status enum (`ready`/`clarification_required`/`unsupported`) with conditional fields.
- *Detailed:* Clarification has `question`, `missing_concept`, 2–4 `options{label, definition}`; `reason` for unsupported.
- *KnowFlow:* `assistant.py::SQL_SCHEMA`, `ModelSqlOutput`.
- *Follow-up:* Why let the model refuse? → *Answer:* "Delete every order" → `unsupported` (observed live) is better than a rejected query.

**19.6 [Expert] How would you measure structured-output reliability?**
- *Short:* Rate of `model_invalid_output` / truncation per 100 calls, by model and prompt version.
- *Detailed:* Error codes are already logged and audited; aggregate them per run; compare prompt versions.
- *KnowFlow:* NOT MEASURED as a metric; errors recorded in `evaluation_results.error`.
- *Follow-up:* Typical fix when it's high? → *Answer:* Shorter schema, more `num_predict`, or a model better at JSON.

## 20. Text-to-SQL

**20.1 [Beginner] Walk through the SQL flow.**
- *Short:* Glossary clarification → role check → schema introspection → model → AST validation → read-only execution → results.
- *Detailed:* Rejected SQL is shown but never run; one repair on execution errors.
- *KnowFlow:* `sql_assistant/service.py::ask`.
- *Follow-up:* Which step needs no model? → *Answer:* The glossary clarification — instant.

**20.2 [Beginner] Why ask "what does best mean"?**
- *Short:* Different definitions are different queries with different answers.
- *Detailed:* Revenue vs order count vs average order value rank different customers.
- *KnowFlow:* demo glossary `best customer` (ambiguous, 3 options).
- *Follow-up:* What if the glossary doesn't know a term? → *Answer:* The model can return `clarification_required` itself (source `model`).

**20.3 [Intermediate] How does the model know table relationships?**
- *Short:* The schema prompt includes FK join hints from `pg_constraint`.
- *Detailed:* Lines like `JOIN: sales.orders.customer_id -> sales.customers.id`.
- *KnowFlow:* `database.py::introspect`, `schema_prompt`.
- *Follow-up:* Why `pg_constraint` and not `information_schema`? → *Answer:* It works without privileges on the referenced table.

**20.4 [Intermediate] How are relative dates handled?**
- *Short:* The prompt includes the server's local date and asks for date ranges.
- *Detailed:* "last month" = previous calendar month; avoid `EXTRACT` on the current month.
- *KnowFlow:* `build_prompt(today=...)`, rule 4.
- *Follow-up:* Time zone pitfall? → *Answer:* The server's local zone, not the user's browser — fine for single-user local.

**20.5 [Advanced] What's the repair loop?**
- *Short:* One retry with the failed SQL and the database's error message.
- *Detailed:* Only for `sql_execution_failed`; timeouts and refusals aren't repairable; the user triggers it.
- *KnowFlow:* `Repair`, `SqlAnswerOut.repairable`.
- *Follow-up:* Is the DB error safe to show the model? → *Answer:* Postgres query errors on a validated SELECT contain no credentials (comment in `execute`).

**20.6 [Expert] How would you benchmark Text-to-SQL?**
- *Short:* Questions with expected SQL or expected result sets; execution accuracy (results match) beats string match.
- *Detailed:* `evaluation_cases.expected_sql` exists in the schema but no SQL benchmark has been run (README: "No SQL accuracy benchmark has been run").
- *KnowFlow:* NOT MEASURED.
- *Follow-up:* How to handle ambiguity in the benchmark? → *Answer:* Include the clarification choice in each case.

## 21. SQLGlot

**21.1 [Beginner] What is SQLGlot?**
- *Short:* A Python SQL parser/transpiler that builds an AST for many dialects.
- *Detailed:* KnowFlow parses with `read="postgres"`.
- *KnowFlow:* `validation.py::validate_sql`.
- *Follow-up:* Why not regex? → *Answer:* Regex misses `DELETE` inside a CTE, comments and literals.

**21.2 [Beginner] How do you detect multiple statements?**
- *Short:* `sqlglot.parse` returns a list; exactly one is allowed.
- *Detailed:* `select 1; drop table customers` → rejected.
- *KnowFlow:* `validate_sql`.
- *Follow-up:* What about a trailing semicolon? → *Answer:* Fine: `SELECT name FROM customers;` parses to one statement.

**21.3 [Intermediate] How are unqualified tables handled?**
- *Short:* Qualified with the first allowed schema; CTE names are exempt.
- *Detailed:* `node.set("db", exp.to_identifier(default_schema))`.
- *KnowFlow:* `select * from customers` → `SELECT * FROM sales.customers LIMIT 501`.
- *Follow-up:* Why qualify? → *Answer:* The executed SQL is unambiguous, and the schema check applies to every table.

**21.4 [Intermediate] How are functions checked?**
- *Short:* Deny-list by name plus prefixes `pg_`, `lo_`, `dblink`, `xpath`.
- *Detailed:* `exp.Anonymous` (unknown functions) and known `exp.Func` nodes both checked.
- *KnowFlow:* `DANGEROUS_FUNCTIONS`, `_function_name`.
- *Follow-up:* Why deny-list rather than allow-list? → *Answer:* An allow-list of all safe Postgres functions is large; the DB role and read-only transaction cover what a deny-list misses. An allow-list would be stricter.

**21.5 [Advanced] How is the row cap applied to UNIONs?**
- *Short:* Wrapped: `SELECT * FROM (<union>) AS q LIMIT 501`.
- *Detailed:* For a plain SELECT, the existing numeric LIMIT is reduced to ≤ 501; a non-numeric LIMIT is rejected.
- *KnowFlow:* `validate_sql`.
- *Follow-up:* Why 501? → *Answer:* `max_rows + 1` detects truncation.

**21.6 [Expert] What if SQLGlot misparses something?**
- *Short:* Parse errors → rejected (`sql_parse_error`); a misparse that hides a write would still hit the read-only role and transaction.
- *Detailed:* The validator's docstring says it must reject unsafe SQL even if other layers were misconfigured — and vice versa.
- *KnowFlow:* `FORBIDDEN_NODES` resolved by `getattr` for version differences.
- *Follow-up:* How do you keep it honest across versions? → *Answer:* The 35-case unsafe test list runs on every change.

## 22. AI safety

**22.1 [Beginner] What's prompt injection?**
- *Short:* Text in the input that tries to override the system's instructions.
- *Detailed:* Indirect injection comes from retrieved documents — the vendor FAQ sample does exactly this.
- *KnowFlow:* `samples/documents/vendor-faq-untrusted.txt`.
- *Follow-up:* What did the model do live? → *Answer:* Answered "No supporting source found…" and didn't follow it (2026-11-08).

**22.2 [Beginner] How are uploads made safe?**
- *Short:* Extension, MIME, magic bytes, size; sandboxed extraction with a timeout.
- *Detailed:* Files stored under generated names outside any web root.
- *KnowFlow:* `validation.py`, `storage.py`, `extraction.py`.
- *Follow-up:* Zip bombs? → *Answer:* DOCX validation reads only the central directory and caps entries at 10,000.

**22.3 [Intermediate] What's logged, and what isn't?**
- *Short:* Ids, counts, statuses, timings; never questions, document text or secrets.
- *Detailed:* Key + pattern redaction (URLs with passwords, `password=`, Fernet tokens, Bearer); audit metadata limited to short scalars.
- *KnowFlow:* `core/logging.py`, `modules/audit.py::_safe`.
- *Follow-up:* Where *is* the question stored? → *Answer:* In the local DB (`messages`, `sql_queries`), which is user data.

**22.4 [Intermediate] How are SQL connection passwords protected?**
- *Short:* Fernet encryption at rest, write-only API, key from env or a 0600 file.
- *Detailed:* Driver errors never echoed; history stores SQL with literals redacted.
- *KnowFlow:* `secrets.py`, `database.py::_connection_error`, `redact_literals`.
- *Follow-up:* Key rotation? → *Answer:* Not implemented; a changed key gives `secret_unreadable` and asks to re-add the connection.

**22.5 [Advanced] What's the biggest security gap?**
- *Short:* No application authentication or authorisation.
- *Detailed:* Single-user by design; the Azure deployment adds Caddy basic auth (one shared password). No roles, no per-user data.
- *KnowFlow:* `get_default_workspace`.
- *Follow-up:* First step to fix? → *Answer:* OIDC login in front, a `user_id` → workspace mapping, and every query already filters by workspace.

**22.6 [Expert] Can citation verification be gamed by an injected document?**
- *Short:* Yes, partly: an injected passage can make the model cite *it*; the citation is "valid" because the passage was supplied.
- *Detailed:* Verification proves provenance, not truth. Mitigations: trust levels per document, flagging untrusted sources in the UI, injection classifiers at ingestion.
- *KnowFlow:* injection-document cases in the gold set; q38 citation error.
- *Follow-up:* Would you block untrusted documents? → *Answer:* Mark and down-weight them; blocking loses legitimate content.

## 23. Evaluation

**23.1 [Beginner] Define Recall@K and MRR.**
- *Short:* Recall@K = share of evidence found in the top K; MRR = mean of 1/rank of the first relevant result.
- *Detailed:* KnowFlow S3: Recall@5 0.968, MRR 0.891.
- *KnowFlow:* `metrics.py::retrieval_metrics`.
- *Follow-up:* Why is precision@5 only ~0.2? → *Answer:* Most cases have one relevant passage, so the max is ~0.2.

**23.2 [Beginner] Why no LLM judge?**
- *Short:* Deterministic metrics are reproducible and free; judges need calibration and add cost/bias.
- *Detailed:* Answer metrics are computed mechanically: abstention, citation precision vs evidence, injection marker.
- *KnowFlow:* "No LLM judge is used anywhere here".
- *Follow-up:* What can't you measure then? → *Answer:* Faithfulness and answer correctness — NOT MEASURED.

**23.3 [Intermediate] Explain nDCG with an example.**
- *Short:* Discounted gain of relevant results by rank, normalised by the ideal order.
- *Detailed:* Two evidence items at ranks 1 and 3: DCG = 1 + 0.5 = 1.5; IDCG = 1 + 0.631 = 1.631; nDCG = 0.920.
- *KnowFlow:* each evidence item gains once.
- *Follow-up:* Why gain once? → *Answer:* Overlapping fixed chunks would otherwise inflate the score.

**23.4 [Intermediate] Why evidence matchers instead of chunk ids?**
- *Short:* Chunk ids change on every re-index; `{document, quote}` labels survive and work for both strategies.
- *Detailed:* ADR-000 G-9; `expected_chunk_ids` still supported.
- *KnowFlow:* `metrics.py::matches`.
- *Follow-up:* Weakness? → *Answer:* A chunk that paraphrases the evidence without the exact quote isn't credited.

**23.5 [Advanced] What does the dev/test split protect against?**
- *Short:* Overfitting choices to the questions you report on.
- *Detailed:* Tune on 38 dev cases; run the 12 test cases once per reported configuration.
- *KnowFlow:* `evaluation_cases.split`.
- *Follow-up:* Is 12 enough? → *Answer:* No — one case moves a metric by 8 points; report n with every number, as the report does.

**23.6 [Expert] How would you make the evaluation trustworthy enough to publish?**
- *Short:* Human-reviewed labels, 100–150 cases, paraphrases and distractors, repeated runs with variance, and calibrated faithfulness checks.
- *Detailed:* Fix the dated-conflict labels to accept both documents; add an independent question writer.
- *KnowFlow:* TRD target; README limitations.
- *Follow-up:* How do you report uncertainty? → *Answer:* Bootstrap confidence intervals over cases.

## 24. Docker

**24.1 [Beginner] What does Docker Compose run in KnowFlow?**
- *Short:* Only PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16`).
- *Detailed:* Port bound to `127.0.0.1`, named volume, init SQL creates the extension, healthcheck with `pg_isready`.
- *KnowFlow:* `infra/docker-compose.yml`.
- *Follow-up:* Why not containerise everything? → *Answer:* The dev laptop had no Docker (ADR-008); Ollama on the host uses the host's resources directly.

**24.2 [Beginner] Why bind the DB port to 127.0.0.1?**
- *Short:* So the database is never reachable from the network.
- *Detailed:* Docker publishes to `0.0.0.0` by default, bypassing many host firewalls.
- *KnowFlow:* `"127.0.0.1:${POSTGRES_PORT:-5432}:5432"`.
- *Follow-up:* Same on Azure? → *Answer:* Yes; only Caddy is public.

**24.3 [Intermediate] What's in the Hugging Face Dockerfile?**
- *Short:* One image with Postgres+pgvector, Ollama + models, the API, worker, web and Caddy.
- *Detailed:* Clones the GitHub repo at build (Hugging Face rejects plain binary files), runs as uid 1000, a `start.sh` supervisor.
- *KnowFlow:* `deploy/huggingface/`. **Never built** — Docker Spaces need PRO.
- *Follow-up:* What would you check first if you built it? → *Answer:* The Ollama install inside the image, Postgres running as non-root, and image size.

**24.4 [Intermediate] Why does the Compose file use `--wait` in `make db-up`?**
- *Short:* To block until the healthcheck passes, so migrations don't race the DB start.
- *Detailed:* `pg_isready -U … -d …` every 5 s, 20 retries.
- *KnowFlow:* `Makefile`, compose healthcheck.
- *Follow-up:* What happens if migrations run before Postgres is ready anyway? → *Answer:* The engine's 3 s connect timeout fails fast with a clear error; on Azure, `setup.sh` runs `docker compose up -d --wait` before `alembic upgrade head`, and systemd restarts the API (`Restart=always`) if it starts too early.

**24.5 [Advanced] Multi-stage builds — where are they used?**
- *Short:* The HF Dockerfile copies Node and Caddy binaries from official images instead of installing them.
- *Detailed:* `COPY --from=node …`, `COPY --from=caddy …`; model layer placed before code so code changes don't re-download weights.
- *KnowFlow:* `deploy/huggingface/Dockerfile`.
- *Follow-up:* Cache-busting for git clones? → *Answer:* `ADD` of the GitHub ref API URL changes when the branch moves.

**24.6 [Expert] How would you containerise for production?**
- *Short:* Separate images for API, worker and web; Postgres managed; GPU inference service; secrets from a vault.
- *Detailed:* Non-root users, read-only root FS, healthchecks mapped to `/health/live` and `/health/ready`, resource limits per container.
- *KnowFlow:* PLANNED.
- *Follow-up:* Liveness vs readiness? → *Answer:* `/health/live` = restart if failing; `/health/ready` = don't route traffic until dependencies are up.

## 25. Git and CI/CD

**25.1 [Beginner] How was work organised in git?**
- *Short:* A feature branch per milestone (M0–M8), merged with `--no-ff`, tagged `v1.0.0-rc.1`.
- *Detailed:* Conventional commit prefixes (`feat`, `fix`, `docs`, `chore`, `ci`).
- *KnowFlow:* `docs/branch-strategy.md`, git log.
- *Follow-up:* How many commits? → *Answer:* 60 on main as of 2026-11-08.

**25.2 [Beginner] What does the CI workflow check?**
- *Short:* No paid APIs/secrets; API lint+types+migrations+tests on a Postgres service; web lint/format/types/tests/build/Playwright; compose config.
- *Detailed:* Five jobs in `.github/workflows/ci.yml`.
- *KnowFlow:* see above.
- *Follow-up:* Has it run? → *Answer:* No — 0 runs on GitHub; same checks pass locally. Say this.

**25.3 [Intermediate] What's `alembic check` for in CI?**
- *Short:* It fails if the ORM models and the migrations disagree.
- *Detailed:* Prevents "works on my machine" schema drift.
- *KnowFlow:* CI `api` job.
- *Follow-up:* Also run locally? → *Answer:* Yes, 2026-11-08: "No new upgrade operations detected".

**25.4 [Intermediate] How are secrets kept out of git?**
- *Short:* `.gitignore` for `.env`, keys, data and model weights; a CI step fails if they're tracked.
- *Detailed:* `git ls-files | grep -E '(^|/)\.env$|^data/.+|\.gguf$|\.safetensors$'`.
- *KnowFlow:* `ci.yml` policy job.
- *Follow-up:* Leaked anyway? → *Answer:* Rotate first, then purge history.

**25.5 [Advanced] How does the CI avoid downloading model weights?**
- *Short:* Ollama isn't in CI; model-dependent tests use fake transports; real-model tests are opt-in.
- *Detailed:* `KNOWFLOW_RUN_OLLAMA=1` gates `test_real_ollama.py`.
- *KnowFlow:* CI comment "CI never downloads LLM weights".
- *Follow-up:* Then how is the real-model path tested? → *Answer:* Locally and on the live system (A-to-Z check).

**25.6 [Expert] What would you add to CD?**
- *Short:* On a tag: run CI, then `knowflow-azure.ps1 update` (or a GitHub Action with Azure credentials) and a smoke test against `/health/ready`.
- *Detailed:* Plus an evaluation regression gate on dev metrics.
- *KnowFlow:* manual `update` today.
- *Follow-up:* Rollback? → *Answer:* `git checkout <tag>` on the VM + `setup.sh`; migrations would need down-revisions.

## 26. Deployment

**26.1 [Beginner] Where is KnowFlow deployed?**
- *Short:* An Azure for Students VM (4 vCPU, 16 GB) in Central India, started on demand, behind HTTPS and a password.
- *Detailed:* `https://knowflow-priyanshu.centralindia.cloudapp.azure.com`; stopped by default.
- *KnowFlow:* `deploy/azure/`.
- *Follow-up:* Why on demand? → *Answer:* Always-on would use the $100 credit in ~5–6 weeks; stopped costs ~$2.64/month.

**26.2 [Beginner] What runs on the VM?**
- *Short:* Caddy, three systemd services (api, worker, web), Docker Postgres, Ollama.
- *Detailed:* Only Caddy listens publicly; SSH allowed only from the owner's IP.
- *KnowFlow:* `setup.sh`.
- *Follow-up:* How do services start after `start`? → *Answer:* systemd `WantedBy=multi-user.target`; Docker `restart: unless-stopped`.

**26.3 [Intermediate] How does `stop` save money without changing the URL?**
- *Short:* Deallocate the VM and delete the public IP; `start` re-creates the IP with the same DNS label.
- *Detailed:* The DNS name belongs to the label, not the IP; Caddy's certificate is for the name, so it's reused.
- *KnowFlow:* `knowflow-azure.ps1::Remove-PublicIp`, `Add-PublicIp`.
- *Follow-up:* What bug did this have? → *Answer:* `start` crashed after `stop` on PowerShell 5.1 (stderr treated as fatal); fixed in `65af69c`.

**26.4 [Intermediate] Why did the Hugging Face plan fail?**
- *Short:* Creating a Docker Space on free `cpu-basic` returned HTTP 402: it requires PRO.
- *Detailed:* Discovered at deployment time; the files remain for PRO users.
- *KnowFlow:* `docs/deploy-huggingface.md` note.
- *Follow-up:* Lesson? → *Answer:* Verify a provider's current terms before building for it.

**26.5 [Advanced] Which production bug did the live check find?**
- *Short:* Sporadic HTTP 500 from `ECONNRESET` between the Next.js proxy and Uvicorn.
- *Detailed:* Uvicorn closes idle keep-alive connections after 5 s; the proxy reused one at the moment it closed. Fix: `--timeout-keep-alive 75`; re-test: 103 checks, 0 problems.
- *KnowFlow:* commit `3ea498e`.
- *Follow-up:* Why wasn't it caught in tests? → *Answer:* Tests mock or bypass the proxy; it needs real sockets and idle gaps.

**26.6 [Expert] How would you harden the deployment?**
- *Short:* Real auth (OIDC), fail2ban/rate limits at Caddy, automatic security updates, backups of the Postgres volume, monitoring and alerts.
- *Detailed:* Also: secrets in Key Vault, the DB on a managed service, log shipping.
- *KnowFlow:* PLANNED.
- *Follow-up:* Backups now? → *Answer:* None automated; `pg_dump` manually.

## 27. Performance optimisation

**27.1 [Beginner] Where does the time go for one answer?**
- *Short:* Almost all in CPU generation (30–60 s); retrieval ~40 ms.
- *Detailed:* Trace example (Azure): embed_query 37 ms, dense 4 ms, generation 5.8 s for a short answer; typical answers longer.
- *KnowFlow:* `RetrievalTrace.timings_ms`.
- *Follow-up:* Biggest lever? → *Answer:* Hardware (GPU) or a smaller prompt/output.

**27.2 [Beginner] Why only one generation at a time?**
- *Short:* On CPU, two generations each run slower and memory can't hold more; a queue is fairer.
- *Detailed:* `BoundedSemaphore(1)`, wait 10 s → 429 `generation_busy`.
- *KnowFlow:* `models/gate.py`.
- *Follow-up:* Shared with SQL? → *Answer:* Yes, one gate for both.

**27.3 [Intermediate] How do you avoid model swapping on low RAM?**
- *Short:* You mostly can't at 7.3 GB — Ollama keeps one model resident, so embedding and generation swap.
- *Detailed:* On the 16 GB VM both fit; `OLLAMA_KEEP_ALIVE=30m` keeps them loaded between questions.
- *KnowFlow:* evaluation report note; `setup.sh` Ollama override.
- *Follow-up:* What did swapping cost? → *Answer:* It's part of the 57 s p50 / 138 s p95 answer latency on the laptop.

**27.4 [Intermediate] What's cheap to optimise in retrieval?**
- *Short:* Cache query embeddings; it's 90%+ of retrieval time.
- *Detailed:* Exact vector search ~1–2 ms; FTS ~2 ms.
- *KnowFlow:* NOT IMPLEMENTED.
- *Follow-up:* Cache key? → *Answer:* (embedding version id, normalised question).

**27.5 [Advanced] How do you keep the ingestion worker from looking dead during long embeds?**
- *Short:* Refresh `heartbeat_at` after every embedding batch.
- *Detailed:* Otherwise `recover_stale_jobs` would re-queue a healthy job after 300 s.
- *KnowFlow:* `embedding_stage.py::embed`.
- *Follow-up:* Batch size trade-off? → *Answer:* Bigger batches are faster per chunk but longer between heartbeats and higher memory.

**27.6 [Expert] Plan a 10× latency improvement for answers.**
- *Short:* GPU inference with streaming; shorter context (top-K 3–4 after reranking); smaller `num_predict`; keep models warm.
- *Detailed:* Measure first: tokens/s (NOT MEASURED today) and prefill vs decode split from Ollama's durations; optimise the larger one. Quality must be re-checked on the gold set after each change.
- *KnowFlow:* trace timings + evaluation latency percentiles.
- *Follow-up:* Perceived latency? → *Answer:* Streaming the first tokens in < 1 s changes UX more than total time.

---

## Part Q — Managerial and HR preparation

Ground rules: use real evidence; never invent users, teammates, impact or timelines. KnowFlow is a
solo project built from 6 to 8 November 2026 with an AI coding agent (58 of 60 commits are
co-authored by Claude). Interviewers increasingly *expect* AI-assisted development; what they test is
whether you understand and own the result. Answer frameworks below are first-person, in your words.

**Q1. Why did you build KnowFlow?**
Framework: problem → constraint → goal. "Most document chatbots I tried either made things up or
sent documents to an external API, and nobody could say whether a change made them better. I wanted
to build one where every answer is tied to a passage you can open, that runs on my own laptop for
free, and where retrieval quality is measured rather than guessed."

**Q2. Why this project rather than something else?**
"It covers the full stack an AI engineer works across — ingestion, embeddings, retrieval, prompting,
structured outputs, safety, evaluation, and a real UI — and it forced trade-offs: a 7.3 GB CPU laptop
and a zero budget."

**Q3. What was your individual contribution?** *(the most important honest answer)*
"It's a solo project. I wrote the product and technical requirements — the PRD, TRD and design spec —
and made the key decisions: local models only, PostgreSQL for everything, what to measure, which
models to approve, and how to deploy. I built it with an AI coding agent, milestone by milestone; the
git history shows that openly. My job was to direct it, review what it produced, run and verify every
milestone, and push back when something didn't match the spec. For example, I ran an end-to-end check
on the deployed system and found a keep-alive race that caused random 500 errors, and a bug in my
start script that would have broken the first demo. I can explain any part of the code in depth."
Do **not** say "I wrote every line". If asked "Which parts did you write by hand?", answer truthfully.

**Q4. Hardest technical challenge?**
Pick one with evidence. Option A — *lexical search returned nothing for natural questions*: Postgres
FTS ANDs all terms, so "How much can I spend on a hotel per night?" matched 0 chunks; switching to an
OR of the stemmed lexemes ranked by cover density fixed it, and hybrid then beat dense-only on every
metric. Option B — *SQL safety*: regex can't see a `DELETE` inside a CTE; parsing to an AST and
layering a read-only role, transaction and timeout made it robust. Option C — *running on 7.3 GB*:
only one model fits in memory, so I capped generation to one at a time and set long, explicit timeouts.

**Q5. What failed during development?**
Real items: the 4B model sometimes writes invalid SQL (handled with one repair attempt); a citation
pointed to the wrong chunk (q38); the model picked a superseded policy (24 vs 26 days); Hugging Face
free Docker Spaces turned out to need PRO, so I moved to Azure for Students; GitHub Actions never ran.

**Q6. Biggest mistake?**
"Recommending a free host before checking its current terms — Hugging Face changed its free tier, and
I'd already written the deployment files. Now I verify a provider's current limits first." Or: "I
didn't get the evaluation labels reviewed by a person before publishing numbers; I now state that
limitation up front."

**Q7. Why local models?**
Cost (zero), privacy (documents stay local), reproducibility (model digests), offline use. Trade-off:
slower, smaller models — accepted for this use case and measured honestly.

**Q8. How did you manage a zero budget?**
Open-source models via Ollama; Postgres for vectors, search and data; no paid services; a CI check
that fails on paid-API SDKs; deployment on Azure student credit with start/stop so a stopped server
costs about $2.64/month.

**Q9. How did you prioritise features?**
Milestones M0–M8 from the specs: foundation → upload → ingestion → local models → basic RAG →
retrieval experiments → Text-to-SQL → safety/polish → release. Cut or deferred when they'd cost a lot
of CPU or time for unclear value: RAG clarification classifier (G-8), streaming, OCR, reranker install.

**Q10. How did you test quality?**
Three layers: 282 backend tests (unit, API, integration with real Postgres), 80 frontend unit tests
and 28 Playwright tests; a deterministic evaluation set with retrieval and answer metrics; and a live
end-to-end check of all 45 API operations plus 103 responsive-layout checks on the deployed system.

**Q11. What would you improve with more time?**
Default the UI to hybrid; fix dated-conflict handling and re-measure; run the reranker experiment;
human-review and grow the gold set to 100–150 cases with paraphrases; add faithfulness checking; add
auth; get CI running on GitHub.

**Q12. How would you scale it?**
Typed vector column + HNSW index; more workers (the queue already uses `SKIP LOCKED`); a GPU inference
server (vLLM) or a hosted model behind the existing `ChatModel` protocol; auth + real multi-tenancy
(the schema is already workspace-scoped); object storage for files; streaming responses.

**Q13. Conflicting requirements?**
Real example: the TRD required Docker Compose but the dev laptop had no Docker; resolved by keeping
Compose for other environments and using native Postgres locally, recorded in ADR-008. Another: the
TRD mentioned RAG clarification; the PRD only required it for SQL; recorded as G-8 with the reason
(cost of an extra model call on CPU). "I write the conflict down and the decision rule, not just the
outcome."

**Q14. How did you maintain code quality?**
Strict typing (mypy strict, TypeScript strict), linters and formatters, tests per milestone, ADRs for
decisions, a traceability matrix from requirements to tests, and feature branches merged per
milestone.

**Q15. How would you work in a team?**
Be honest that this was solo. Show habits that transfer: written specs and ADRs, small reviewable
commits, branch-per-milestone, tests as contracts, explicit limitations in docs.

**Q16. How do you handle feedback?**
Concrete: when the end-to-end check found bugs, the fixes were small, tested and committed with the
reason in the message; when the evaluation showed hybrid was better, the README said so — and also that
the UI still defaults to dense, which is something to change.

**Q17. Why should we hire you as an AI Engineer?**
"Because I treat model output as untrusted input, measure before claiming, and can explain the whole
path from a PDF's bytes to a cited answer — including where it fails. KnowFlow shows that with real
code, real numbers and the limitations written next to them."

---

## Part R — Stress interview

Each answer: the direct answer first, then the probing follow-ups you should expect.

**R1. Why PostgreSQL + pgvector instead of a dedicated vector database?**
One transactional store: chunks, vectors and the `ready` flag commit together, so search never sees
half a document; FTS and vectors live next to each other for hybrid search; one service to run on a
small machine (ADR-003). At this scale exact search takes ~1–2 ms. *Follow-ups:* "At 10M vectors?" →
typed `vector(768)` + HNSW, measure recall vs exact, partition by workspace; consider a dedicated
store when you need horizontal scaling or very high QPS. "HNSW trade-offs?" → build time and memory,
approximate recall controlled by `ef_search`, slower writes.

**R2. Why both dense and lexical retrieval?**
They fail differently: dense handles paraphrase; lexical nails exact identifiers like `SEC-USB` or
`FIN-TE-07` that embeddings blur. Measured: S3 hybrid beat S2 dense on every metric (MRR 0.891 vs
0.879). *Follow-up:* "Lexical alone scored even higher (MRR 0.901) — why not just use that?" → because
this question set reuses document wording; a paraphrase set would favour dense, and hybrid is the safer
default; I haven't measured a paraphrase set, so I wouldn't claim more.

**R3. Why RRF instead of another fusion?**
Scores from cosine and `ts_rank_cd` aren't on the same scale; RRF uses ranks only, needs no
normalisation or training, and is robust (k = 60 from Cormack et al.). *Follow-ups:* "Alternatives?" →
weighted score fusion after min-max/z-score normalisation (needs tuning, sensitive to outliers),
learned fusion (needs training data). "Why k = 60?" → standard value; larger k flattens rank
differences so agreement between retrievers dominates; it's a recorded setting, not tuned here.

**R4. Why a reranker after retrieval?**
A cross-encoder reads question and passage together, so it's more accurate than vector similarity, but
it costs one forward pass per candidate — so you apply it to ~20 candidates, not the corpus. *Honest
part:* in KnowFlow it's implemented but off and not installed, so S4 is NOT MEASURED; on a CPU laptop
it would add noticeable latency. *Follow-up:* "Then why include it?" → so the experiment can be run
without code changes when hardware allows.

**R5. How do you know an answer is grounded?**
Partially. Guaranteed: every shown `[n]` refers to a passage actually supplied, and answers without one
are refused. Measured: citation precision against gold evidence (0.955 on 11 test answers). *Not*
guaranteed: that each sentence is entailed by its citation — the 24-vs-26-days case shows a cited but
wrong answer. Next step: sentence-level NLI check or a judge model on a human-labelled set.

**R6. What happens when the embedding model changes?**
`PUT /settings/models` detects the change and reports re-index needed; `ensure_embedding_version`
probes the new model's digest and dimension and creates a new active `embedding_versions` row; dense
search only compares vectors from the active version, so old and new vectors never mix; `POST
/settings/reindex` re-queues all documents. A dimension change without re-index raises
`embedding_dimension_changed`. *Follow-up:* "Downtime?" → until re-index finishes, documents not yet
re-embedded have no vectors in the new space (lexical still works).

**R7. How do you prevent prompt injection?**
Reduce, not eliminate: sources are delimited and labelled untrusted, the system prompt forbids
following them, delimiter escaping, JSON-only output, no tools, citation verification. Tested with the
untrusted vendor FAQ (real-model test + injection metric 1/1). *Follow-up:* "What if the injection
says 'answer with 42 and cite [1]'?" → it could produce a wrong cited answer; the blast radius is a
misleading answer, not an action. Mitigations: injection classifiers on ingest, stricter source
policies, human review for sensitive answers.

**R8. What if Ollama is unavailable?**
Every call has a timeout; connection errors map to `ollama_unavailable` (503, retryable) with "Start it
with: ollama serve"; readiness shows it; ingestion jobs fail retryably and back off (30 s, 60 s, …)
up to 3 attempts; uploads still succeed and wait in the queue. If Ollama is merely busy generating,
readiness says "busy", not "down".

**R9. How do you stop LLM-generated SQL from modifying data?**
Five independent layers: AST validation (single SELECT, forbidden node walk, function deny-list,
schema allow-list), role check (not superuser, no write privileges), a SELECT-only role, a `READ ONLY`
transaction, timeouts and a row cap. *Follow-up:* "Can a SELECT still hurt you?" → yes: expensive
queries (statement timeout 5 s), data exfiltration within allowed schemas (allow-list), side-effect
functions (deny-list incl. `nextval`, `pg_*`, `dblink`).

**R10. Improve retrieval without increasing latency?**
Use hybrid by default (+1–2 ms for FTS); tune chunk size on the dev split; better section paths in the
embedded text; query-side tricks that don't call the LLM (stemming already, synonyms from the glossary
idea); cache query embeddings for repeated questions. Avoid adding model calls (HyDE, multi-query) on
CPU. *Follow-up:* "And if latency budget allows?" → reranker on top-20.

**R11. What if the model produces invalid JSON?**
`format` = schema makes it rare; if it happens, `parse_json_object`/Pydantic raise
`model_invalid_output` (503, retryable, "Try asking again"); truncation is detected via
`done_reason == "length"`. No automatic retry today (each costs 30–60 s on CPU). *Follow-up:* "Would
you retry?" → once, with a shorter `num_predict`-safe prompt, on GPU hardware.

**R12. How would you handle 100,000 documents?**
Ingestion: multiple workers (already safe), batch embeddings, maybe GPU. Storage: object store for
files. Retrieval: typed vectors + HNSW, partition/scope by workspace, keep FTS GIN; measure recall vs
exact. Generation unchanged (top-K is constant). Evaluation: a larger, human-reviewed set with
distractors. *Follow-up:* "Chunk count?" → at ~10 chunks/doc ×2 strategies = ~2M chunks; consider
storing only the winning strategy in production.

**R13. What if the evaluation dataset is biased?**
It is: written by the coding agent against the same corpus, reusing its wording (which is why lexical
does so well), tiny and synthetic. Mitigations: human review, paraphrased questions, questions written
by people who haven't read the documents, distractor documents, held-out split used once, report
sample sizes with every number.

**R14. How do you distinguish retrieval failure from generation failure?**
Retrieval metrics are computed independently of answers; every answer stores candidate ranks; failure
categories separate `evidence_not_retrieved` / `partial_recall` from `irrelevant_citation` /
`wrong_abstention`. Example: in the 24-vs-26 case both passages were ranks 1–2, so it was a generation
error.

**R15. Your answers take a minute. Is this usable?**
For a local, private tool on a CPU laptop, it's the honest cost; the UI shows progress and stage
timings. With a GPU or a hosted model behind the same `ChatModel` interface, generation drops to
seconds. Retrieval itself is ~40 ms.

**R16. Isn't it risky that an AI agent wrote most of the code?**
"That's exactly why the project has strict typing, 390 automated tests across backend and frontend,
recorded decisions and an end-to-end check against the live system — which caught real bugs. I'd
apply the same discipline to code from any author, including me."
