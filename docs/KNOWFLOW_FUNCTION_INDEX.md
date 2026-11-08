# KnowFlow Function and Class Index

> **Generated from the source code**, not written by hand. Backend entries come from parsing
> every module under `apps/api/app` with Python's `ast` module (signatures, defaults, return
> annotations and the first paragraph of each docstring). Frontend entries come from a scan
> of `export` declarations under `apps/web/src`. Generated on 2026-11-08 from commit
> `65af69c`. If the code changes, regenerate it rather than editing it.
>
> Companion documents: [Master guide](KNOWFLOW_ENGINEERING_AND_INTERVIEW_MASTER_GUIDE.md) ·
> [API reference](KNOWFLOW_API_REFERENCE.md) · [Question bank](KNOWFLOW_INTERVIEW_QUESTION_BANK.md)

## Counts

| Scope | Files | Classes | Top-level functions | Methods |
|---|---|---|---|---|
| Backend (`apps/api/app`) | 64 | 154 | 263 | 50 |
| Frontend (`apps/web/src`, non-test) | 51 | — | 122 exported functions/components | 79 exported types/interfaces/consts |

**Total documented symbols: 668** (backend 467, frontend 201).

## Most important call chains

Read these first. Each arrow is a real call in the code.

| Workflow | Call chain |
|---|---|
| Upload | `api/v1/documents.py::upload_document` → `modules/documents/service.py::upload_document` → `validation.sanitize_filename`, `format_for_filename`, `check_declared_mime` → `FileStorage.receive` → `validation.check_signature` → `repository.find_by_checksum` → `_queue_job` → `FileStorage.commit` → `session.commit` |
| Ingestion | `workers/ingestion.py::run` → `claim_next_job` (`FOR UPDATE SKIP LOCKED`) → `process_job` → `extraction.extract_with_timeout` (child process) → `chunking.chunk` (fixed + recursive) → `embedding_stage.attach_embedding.embed` → `OllamaEmbedding.embed_documents` → `OllamaClient.embed` → `_complete` (one transaction) |
| Ask | `api/v1/chat.py::chat_query` → `registry.chat_model` → `rag/service.py::ask` → `retrieval/service.py::retrieve` → (`_dense` → `OllamaEmbedding.embed_query` → `dense_search`) / `lexical_search` / `fusion.rrf` / `reranker.rerank` → `gate.generation_slot` → `rag/answer.py::answer_question` → `pack_context` → `prompts.build_user_prompt` → `OllamaChat.complete` → `ollama.parse_json_object` → `ModelAnswer.model_validate` → `verify_citations` |
| SQL | `api/v1/sql.py::query` → `sql_assistant/service.py::ask` → `assistant.pending_clarification` → `database.check_read_only` / `require_read_only` → `database.introspect` → `assistant.resolved_definitions` → `assistant.generate` → `validation.validate_sql` → `database.execute` → `_log` |
| Evaluation | `api/v1/evaluations.py::create_run` → `runner.create_run` → worker `run` → `runner.claim_next_run` → `runner.execute_run` → `runner.score_case` → `retrieve` → `metrics.relevance` / `metrics.retrieval_metrics` → (`answer_question`) → `metrics.aggregate` |

## Backend

### HTTP layer (FastAPI routers and dependencies)

#### `apps/api/app/api/deps.py`

*Request-scoped dependencies. Tests override `get_session` and `get_storage`.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `get_storage` | function | 15 | `(settings: Annotated[Settings, Depends(get_settings)]) -> FileStorage` |  |
| `current_workspace` | function | 24 | `(session: SessionDep) -> Workspace` |  |

#### `apps/api/app/api/v1/activity.py`

*Activity / troubleshooting endpoints (PRD §4 Activity, DRD §7.1 key metrics).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `EventOut` | class (BaseModel) | 42 | `id: str; created_at: datetime; actor: str; action: str; resource_type: str; resource_id: str \| None; request_id: str \| None; metadata: dict[str, Any]` |  |
| `EventPage` | class (BaseModel) | 53 | `items: list[EventOut]; total: int` |  |
| `JobOut` | class (BaseModel) | 58 | `id: str; document_id: str; document_name: str; status: str; stage: str \| None; attempts: int; error_code: str \| None; error_message: str \| None; created_at: datetime; started_at: datetime \| None; completed_at: datetime \| None; duration_ms: int \| None` |  |
| `LatestRun` | class (BaseModel) | 73 | `id: str; label: str; status: str; recall_at_k: float \| None; mrr: float \| None; cases: int; created_at: datetime` |  |
| `SummaryOut` | class (BaseModel) | 83 | `documents: int; documents_ready: int; documents_processing: int; documents_failed: int; chunks: int; questions_7d: int; abstained_7d: int; answer_latency_p50_ms: float \| None; sql_questions_7d: int; latest_evaluation: LatestRun \| None` |  |
| `events` | function `@router.get('/events', response_model=EventPage)` | 97 | `(session: SessionDep, workspace: WorkspaceDep, category: Category = 'all', limit: Annotated[int, Query(ge=1, le=200)] = 50, offset: Annotated[int, Query(ge=0)] = 0) -> EventPage` |  |
| `jobs` | function `@router.get('/jobs', response_model=list[JobOut])` | 134 | `(session: SessionDep, workspace: WorkspaceDep, status: Literal['all', 'failed', 'active'] = 'all', limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[JobOut]` |  |
| `summary` | function `@router.get('/summary', response_model=SummaryOut)` | 177 | `(session: SessionDep, workspace: WorkspaceDep) -> SummaryOut` |  |

#### `apps/api/app/api/v1/chat.py`

*Ask KnowFlow endpoints (TRD §8): grounded answers, conversations and feedback.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `chat_query` | function `@router.post('/chat/query', response_model=AnswerOut, responses=_ERRORS)` | 31 | `(body: ChatQuery, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> AnswerOut` | Answer from retrieved evidence with verified citations, or abstain. Not streamed (v1). |
| `list_conversations` | function `@router.get('/conversations', response_model=Page[ConversationOut])` | 52 | `(session: SessionDep, workspace: WorkspaceDep, page: Annotated[PageParams, Depends(page_params)]) -> Page[ConversationOut]` |  |
| `get_conversation` | function `@router.get('/conversations/{conversation_id}', response_model=ConversationDetail, responses={404: {'model': ErrorResponse}})` | 68 | `(conversation_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> ConversationDetail` |  |
| `rename_conversation` | function `@router.patch('/conversations/{conversation_id}', response_model=ConversationDetail, responses={404: {'model': ErrorResponse}})` | 80 | `(conversation_id: uuid.UUID, body: RenameConversation, session: SessionDep, workspace: WorkspaceDep) -> ConversationDetail` |  |
| `delete_conversation` | function `@router.delete('/conversations/{conversation_id}', status_code=status.HTTP_204_NO_CONTENT)` | 93 | `(conversation_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> Response` | Idempotent; deletes messages and feedback with it. |
| `put_feedback` | function `@router.put('/messages/{message_id}/feedback', status_code=status.HTTP_204_NO_CONTENT, responses={404: {'model': ErrorResponse}})` | 113 | `(message_id: uuid.UUID, body: FeedbackIn, session: SessionDep, workspace: WorkspaceDep) -> Response` |  |

#### `apps/api/app/api/v1/documents.py`

*Knowledge Library endpoints (TRD §8): upload, list, detail, delete.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_not_found` | function | 36 | `() -> AppError` |  |
| `get_upload_policy` | function `@router.get('/upload-policy', response_model=UploadPolicyOut)` | 41 | `(settings: SettingsDep) -> UploadPolicyOut` | What the upload UI shows before a file is chosen (PRD §5.2). |
| `upload_document` | function `@router.post('', status_code=status.HTTP_202_ACCEPTED, response_model=UploadResult, responses={200: {'model': UploadResult, 'description': 'Duplicate skipped'}, **_ERRORS})` | 63 | `(response: Response, file: Annotated[UploadFile, File(description='PDF (text-based), DOCX, TXT or Markdown')], session: SessionDep, storage: StorageDep, workspace: WorkspaceDep, settings: SettingsDep, on_duplicate: Annotated[DuplicateAction \| None, Query(description='How to handle identical content. Omit to get a 409 with choices.')] = None) -> UploadResult` |  |
| `list_documents` | function `@router.get('', response_model=Page[DocumentOut])` | 110 | `(session: SessionDep, workspace: WorkspaceDep, page: Annotated[PageParams, Depends(page_params)], status_filter: Annotated[DocumentStatus \| None, Query(alias='status', description='Only documents in this state')] = None) -> Page[DocumentOut]` |  |
| `get_document` | function `@router.get('/{document_id}', response_model=DocumentOut, responses={404: {'model': ErrorResponse}})` | 133 | `(document_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> DocumentOut` |  |
| `_document_out` | function | 142 | `(session: Session, document: Document) -> DocumentOut` |  |
| `retry_document` | function `@router.post('/{document_id}/retry', status_code=status.HTTP_202_ACCEPTED, response_model=DocumentOut, responses={404: {'model': ErrorResponse}})` | 154 | `(document_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> DocumentOut` | Queue processing again (failed ingestion, or a manual re-index). Idempotent. |
| `list_chunks` | function `@router.get('/{document_id}/chunks', response_model=Page[ChunkOut], responses={404: {'model': ErrorResponse}})` | 171 | `(document_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep, page: Annotated[PageParams, Depends(page_params)], strategy: Annotated[ChunkStrategy, Query(description='Chunking strategy')] = 'recursive') -> Page[ChunkOut]` | Chunk inspection (PRD §5.2, DRD §7.2 document drawer). |
| `extraction_preview` | function `@router.get('/{document_id}/extraction', response_model=ExtractionPreviewOut, responses={404: {'model': ErrorResponse}})` | 197 | `(document_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep, limit: Annotated[int, Query(ge=1, le=50)] = 5, max_chars: Annotated[int, Query(ge=100, le=5000)] = 1500) -> ExtractionPreviewOut` | The first extracted pages/sections, truncated, for the document drawer preview. |
| `delete_document` | function `@router.delete('/{document_id}', status_code=status.HTTP_204_NO_CONTENT)` | 223 | `(document_id: uuid.UUID, session: SessionDep, storage: StorageDep, workspace: WorkspaceDep) -> Response` | Idempotent: deleting a missing (or foreign-workspace) document also returns 204. |

#### `apps/api/app/api/v1/evaluations.py`

*Evaluation Lab endpoints (TRD §8, PRD §5.4).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `create_dataset` | function `@router.post('/datasets', response_model=DatasetOut, status_code=201, responses={409: {'model': ErrorResponse}})` | 36 | `(body: DatasetIn, session: SessionDep, workspace: WorkspaceDep) -> DatasetOut` |  |
| `list_datasets` | function `@router.get('/datasets', response_model=list[DatasetOut])` | 43 | `(session: SessionDep, workspace: WorkspaceDep) -> list[DatasetOut]` |  |
| `get_dataset` | function `@router.get('/datasets/{dataset_id}', response_model=DatasetDetail, responses=_404)` | 48 | `(dataset_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> DatasetOut` |  |
| `delete_dataset` | function `@router.delete('/datasets/{dataset_id}', status_code=status.HTTP_204_NO_CONTENT)` | 53 | `(dataset_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> Response` |  |
| `import_cases` | function `@router.post('/datasets/{dataset_id}/cases/import', response_model=ImportSummary, responses={**_404, 409: {'model': ErrorResponse}})` | 64 | `(dataset_id: uuid.UUID, file: Annotated[UploadFile, File(description='CSV or JSONL evaluation cases')], session: SessionDep, workspace: WorkspaceDep) -> ImportSummary` |  |
| `load_sample` | function `@router.post('/sample', response_model=SampleLoaded, status_code=202)` | 89 | `(session: SessionDep, storage: StorageDep, workspace: WorkspaceDep, settings: SettingsDep) -> SampleLoaded` | Upload the synthetic sample documents and create the bundled gold set (PRD §5.1). |
| `create_run` | function `@router.post('/runs', response_model=RunOut, status_code=202, responses={**_404, 409: {'model': ErrorResponse}})` | 113 | `(body: RunIn, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> RunOut` | Queue a run; the worker executes it in the background. |
| `list_runs` | function `@router.get('/runs', response_model=list[RunOut])` | 131 | `(session: SessionDep, workspace: WorkspaceDep, dataset_id: uuid.UUID \| None = None) -> list[RunOut]` |  |
| `get_run` | function `@router.get('/runs/{run_id}', response_model=RunDetail, responses=_404)` | 138 | `(run_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> RunDetail` |  |
| `export_run` | function `@router.get('/runs/{run_id}/export', responses=_404)` | 143 | `(run_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep, format: Annotated[Literal['json', 'csv'], Query()] = 'json') -> Response` |  |
| `delete_run` | function `@router.delete('/runs/{run_id}', status_code=status.HTTP_204_NO_CONTENT, responses={409: {'model': ErrorResponse}})` | 164 | `(run_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> Response` |  |

#### `apps/api/app/api/v1/health.py`

*Liveness and readiness endpoints (TRD §8).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_effective` | function | 21 | `(settings: Settings) -> tuple[str, str] \| None` | Saved model selection, if the database is reachable; else the .env defaults. |
| `LiveResponse` | class (BaseModel) | 39 | `status: Literal['ok']` |  |
| `ReadyResponse` | class (BaseModel) | 43 | `status: Literal['ready', 'degraded', 'not_ready']; checks: list[DependencyCheck]` |  |
| `get_readiness_probes` | function | 49 | `(settings: Annotated[Settings, Depends(get_settings)]) -> list[ReadinessProbe]` |  |
| `live` | function `@router.get('/live', response_model=LiveResponse)` | 61 | `() -> LiveResponse` |  |
| `ready` | function `@router.get('/ready', response_model=ReadyResponse, responses={503: {'model': ReadyResponse, 'description': 'A required dependency is down'}})` | 70 | `(response: Response, probes: Annotated[list[ReadinessProbe], Depends(get_readiness_probes)]) -> ReadyResponse` |  |

#### `apps/api/app/api/v1/jobs.py`

*Ingestion job progress (TRD §8).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `get_job` | function `@router.get('/{job_id}', response_model=JobOut, responses={404: {'model': ErrorResponse}})` | 16 | `(job_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> JobOut` |  |

#### `apps/api/app/api/v1/search.py`

*Passage search over ready documents (lexical in M2; dense and hybrid join later).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `search` | function `@router.get('', response_model=SearchResponse)` | 22 | `(session: SessionDep, workspace: WorkspaceDep, q: Annotated[str, Query(min_length=1, max_length=500, description='Search text')], settings: SettingsDep, strategy: ChunkStrategy = 'recursive', mode: Literal['lexical', 'dense'] = 'lexical', limit: Annotated[int, Query(ge=1, le=50)] = 10) -> SearchResponse` |  |

#### `apps/api/app/api/v1/settings.py`

*Models & Settings endpoints (TRD §8): local runtime only, no provider keys.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `get_models` | function `@router.get('/models', response_model=ModelSettingsOut)` | 21 | `(session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> ModelSettingsOut` |  |
| `validate_models` | function `@router.post('/models/validate', response_model=ValidateResponse)` | 28 | `(body: ValidateRequest, session: SessionDep, settings: SettingsDep) -> ValidateResponse` | Probe availability, structured output and the real embedding dimension. |
| `save_models` | function `@router.put('/models', response_model=SaveResponse)` | 36 | `(body: SaveRequest, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> SaveResponse` |  |
| `reindex` | function `@router.post('/reindex', response_model=ReindexResponse, status_code=202)` | 57 | `(session: SessionDep, workspace: WorkspaceDep) -> ReindexResponse` | Queue all documents for processing again, e.g. after changing the embedding model. |

#### `apps/api/app/api/v1/sql.py`

*SQL Analyst endpoints (TRD §8). Secrets are write-only; execution is read-only.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `list_connections` | function `@router.get('/connections', response_model=list[ConnectionOut])` | 28 | `(session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> list[ConnectionOut]` |  |
| `test_connection` | function `@router.post('/connections/test', response_model=ConnectionOut, status_code=201, responses=_ERR)` | 35 | `(body: ConnectionIn, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> ConnectionOut` | Connect, verify the role is read-only and save. The password is never returned. |
| `delete_connection` | function `@router.delete('/connections/{connection_id}', status_code=status.HTTP_204_NO_CONTENT, responses=_ERR)` | 54 | `(connection_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> Response` |  |
| `get_schema` | function `@router.get('/schema/{connection_id}', response_model=SchemaOut, responses=_ERR)` | 63 | `(connection_id: uuid.UUID, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> SchemaOut` | Allow-listed tables, columns, types, descriptions and the glossary. No data rows. |
| `put_glossary` | function `@router.put('/connections/{connection_id}/glossary', response_model=list[GlossaryTermIO], responses=_ERR)` | 73 | `(connection_id: uuid.UUID, body: list[GlossaryTermIO], session: SessionDep, workspace: WorkspaceDep) -> list[GlossaryTermIO]` |  |
| `query` | function `@router.post('/query', response_model=SqlAnswerOut, responses=_ERR)` | 92 | `(body: SqlQueryIn, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep) -> SqlAnswerOut` | Either a clarification (nothing executed) or validated read-only SQL with its result. |
| `history` | function `@router.get('/connections/{connection_id}/history', response_model=list[HistoryItem], responses=_ERR)` | 112 | `(connection_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> list[HistoryItem]` |  |

#### `apps/api/app/api/v1/workspaces.py`

*Workspace endpoints (WSP-02): read and rename the local default workspace.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `get_current_workspace` | function `@router.get('/current', response_model=WorkspaceOut)` | 17 | `(workspace: WorkspaceDep) -> WorkspaceOut` |  |
| `update_workspace` | function `@router.patch('/{workspace_id}', response_model=WorkspaceOut, responses={404: {'model': ErrorResponse}})` | 26 | `(workspace_id: uuid.UUID, body: WorkspaceUpdate, session: SessionDep, workspace: WorkspaceDep) -> WorkspaceOut` |  |

### Cross-cutting infrastructure

#### `apps/api/app/core/config.py`

*Application configuration, validated once at startup (TRD §15: no hardcoded secrets).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `Settings` | class (BaseSettings) | 14 | `app_env: Literal['development', 'test', 'production']; log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR']; postgres_host: str; postgres_port: int; postgres_user: str; postgres_password: SecretStr; postgres_db: str; ollama_base_url: str; ollama_generation_model: str; ollama_embedding_model: str; health_check_timeout_seconds: float; embedding_batch_size: int …` | All runtime configuration. Values come from the environment or the repo-root `.env`. |
| ↳ `Settings.database_url` | method | 89 | `() -> URL` | SQLAlchemy URL built from parts so the password is never string-formatted into logs. |
| `get_settings` | function `@lru_cache` | 102 | `() -> Settings` |  |

#### `apps/api/app/core/errors.py`

*Consistent error envelope with stable codes and request_id; never leaks stack traces (TRD §8).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `ErrorDetail` | class (BaseModel) | 19 | `code: str; message: str; request_id: str \| None; fields: list[dict[str, Any]] \| None; details: dict[str, Any] \| None` |  |
| `ErrorResponse` | class (BaseModel) | 28 | `error: ErrorDetail` |  |
| `AppError` | class (Exception) | 32 |  | Raise for expected, user-explainable failures. `message` must be safe to show users. |
| ↳ `AppError.__init__` | method | 35 | `(code: str, message: str, status_code: int = 400, details: dict[str, Any] \| None = None) -> None` |  |
| `error_response` | function | 62 | `(status: int, code: str, message: str) -> JSONResponse` |  |
| `_app_error` | function | 69 | `(_: Request, exc: Exception) -> JSONResponse` |  |
| `_http_error` | function | 74 | `(_: Request, exc: Exception) -> JSONResponse` |  |
| `_validation_error` | function | 81 | `(_: Request, exc: Exception) -> JSONResponse` |  |
| `_database_error` | function | 95 | `(_: Request, exc: Exception) -> JSONResponse` |  |
| `_unhandled_error` | function | 115 | `(_: Request, exc: Exception) -> JSONResponse` |  |
| `register_error_handlers` | function | 120 | `(app: FastAPI) -> None` |  |

#### `apps/api/app/core/logging.py`

*Structured JSON logging with request correlation and secret redaction (TRD §3, §11).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `redact_text` | function | 44 | `(text: str) -> str` |  |
| `redact` | function | 50 | `(value: Any) -> Any` | Recursively replace values whose key looks sensitive, and secrets inside strings. |
| `JsonFormatter` | class (logging.Formatter) | 63 |  |  |
| ↳ `JsonFormatter.format` | method | 64 | `(record: logging.LogRecord) -> str` |  |
| `configure_logging` | function | 82 | `(level: str) -> None` |  |

#### `apps/api/app/core/middleware.py`

*Request correlation middleware: every request gets a request_id and one structured log line.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `register_request_middleware` | function | 19 | `(app: FastAPI) -> None` |  |

#### `apps/api/app/core/readiness.py`

*Dependency readiness probes for /health/ready (TRD §4.3, §12).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `DependencyCheck` | class (BaseModel) | 24 | `name: str; state: CheckState; required: bool; detail: str; remediation: str \| None; latency_ms: float \| None` |  |
| `ReadinessProbe` | class (Protocol) | 33 |  |  |
| ↳ `ReadinessProbe.__call__` | method | 34 | `() -> list[DependencyCheck]` |  |
| `_elapsed_ms` | function | 37 | `(started: float) -> float` |  |
| `check_postgres` | function | 47 | `(engine: Engine) -> list[DependencyCheck]` |  |
| `check_schema` | function | 88 | `(engine: Engine) -> list[DependencyCheck]` | Is the database migrated to the revision this code expects? (STK-20) |
| `_ollama_probe_client` | function `@lru_cache(maxsize=4)` | 124 | `(base_url: str, timeout: float) -> httpx.Client` |  |
| `check_ollama` | function | 129 | `(settings: Settings, client: httpx.Client \| None = None, models: tuple[str, str] \| None = None, busy: bool = False) -> list[DependencyCheck]` |  |
| `check_worker` | function | 200 | `(engine: Engine, settings: Settings) -> list[DependencyCheck]` | Is an ingestion worker heart-beating? Uploads queue fine without one, but never progress. |

#### `apps/api/app/core/upload_limit.py`

*Reject oversized uploads before the body is read (SEC-01, SEC-07).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `UploadSizeLimitMiddleware` | class (—) | 17 |  |  |
| ↳ `UploadSizeLimitMiddleware.__init__` | method | 18 | `(app: ASGIApp, *, path: str, max_file_bytes: int) -> None` |  |
| ↳ `UploadSizeLimitMiddleware.__call__` | method | 23 | `(scope: Scope, receive: Receive, send: Send) -> None` |  |

### Database layer

#### `apps/api/app/db/base.py`

*Declarative base with a deterministic constraint naming convention (stable Alembic diffs).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `Base` | class (DeclarativeBase) | 15 |  |  |

#### `apps/api/app/db/migrations.py`

*Alembic helpers shared by readiness checks and tests.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `alembic_config` | function | 14 | `() -> Config` |  |
| `expected_heads` | function `@lru_cache` | 19 | `() -> frozenset[str]` | Revisions this code expects the database to be at. |
| `current_heads` | function | 24 | `(connection: Connection) -> frozenset[str]` |  |

#### `apps/api/app/db/models.py`

*ORM models (TRD §7). Every content table is scoped by `workspace_id` (CON-08, SEC-03).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_in` | function | 37 | `(column: str, values: tuple[str, ...]) -> str` |  |
| `TimestampMixin` | class (—) | 41 | `created_at: Mapped[datetime]; updated_at: Mapped[datetime]` |  |
| `Workspace` | class (TimestampMixin, Base) | 50 | `id: Mapped[uuid.UUID]; name: Mapped[str]; is_default: Mapped[bool]` |  |
| `Document` | class (TimestampMixin, Base) | 68 | `id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; original_name: Mapped[str]; storage_key: Mapped[str]; file_type: Mapped[str]; mime_type: Mapped[str]; size_bytes: Mapped[int]; sha256: Mapped[str]; version: Mapped[int]; status: Mapped[str]; page_count: Mapped[int \| None]; extracted_char_count: Mapped[int \| None] …` |  |
| `IngestionJob` | class (Base) | 113 | `id: Mapped[uuid.UUID]; document_id: Mapped[uuid.UUID]; status: Mapped[str]; stage: Mapped[str \| None]; attempts: Mapped[int]; error_code: Mapped[str \| None]; error_message_safe: Mapped[str \| None]; created_at: Mapped[datetime]; started_at: Mapped[datetime \| None]; completed_at: Mapped[datetime \| None]; retry_after: Mapped[datetime \| None]; heartbeat_at: Mapped[datetime \| None] …` |  |
| `DocumentSection` | class (Base) | 146 | `id: Mapped[uuid.UUID]; document_id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; ordinal: Mapped[int]; page_number: Mapped[int \| None]; section_path: Mapped[str \| None]; text: Mapped[str]` | The normalized extracted text, kept for traceability and the extraction preview. |
| `Chunk` | class (Base) | 168 | `id: Mapped[uuid.UUID]; document_id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; strategy: Mapped[str]; chunk_index: Mapped[int]; text: Mapped[str]; page_start: Mapped[int \| None]; page_end: Mapped[int \| None]; section_path: Mapped[str \| None]; char_count: Mapped[int]; token_count: Mapped[int]; content_hash: Mapped[str] …` | A retrievable passage (TRD §7). `search_tsv` is generated by PostgreSQL for FTS. |
| `WorkerHeartbeat` | class (Base) | 213 | `name: Mapped[str]; pid: Mapped[int]; last_seen_at: Mapped[datetime]` | One row per worker process name; lets /health/ready say whether ingestion is running. |
| `EmbeddingVersion` | class (Base) | 223 | `id: Mapped[uuid.UUID]; model: Mapped[str]; digest: Mapped[str]; dimension: Mapped[int]; document_prefix: Mapped[str]; query_prefix: Mapped[str]; is_active: Mapped[bool]; created_at: Mapped[datetime]` | One embedding space: model tag + digest + measured dimension (TRD §4.2, §7, ADR-002). |
| `ChunkEmbedding` | class (Base) | 255 | `chunk_id: Mapped[uuid.UUID]; embedding_version_id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; embedding: Mapped[list[float]]` | A chunk's vector in one embedding space. Untyped `vector` so dimensions can differ by version; exact (sequential) cosine search is the measured baseline (TRD §3). |
| `ModelSettings` | class (Base) | 278 | `id: Mapped[int]; generation_model: Mapped[str]; embedding_model: Mapped[str]; reranker_enabled: Mapped[bool]; validation: Mapped[dict[str, object]]; updated_at: Mapped[datetime]` | User-selected local models (PRD §5.6). One row; absent means "use .env defaults". |
| `Conversation` | class (TimestampMixin, Base) | 299 | `id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; title: Mapped[str]; messages: Mapped[list['Message']]` |  |
| `Message` | class (Base) | 320 | `id: Mapped[uuid.UUID]; conversation_id: Mapped[uuid.UUID]; role: Mapped[str]; content: Mapped[str]; citations: Mapped[list[dict[str, object]]]; metadata_: Mapped[dict[str, object]]; created_at: Mapped[datetime]; conversation: Mapped[Conversation]` | One chat turn. Assistant messages carry citations and the retrieval trace (TRD §7). |
| `MessageFeedback` | class (Base) | 350 | `message_id: Mapped[uuid.UUID]; rating: Mapped[str]; reason: Mapped[str \| None]; created_at: Mapped[datetime]` | Helpful / not helpful on an answer, kept for error analysis (PRD §5.3). |
| `EvaluationDataset` | class (Base) | 369 | `id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; name: Mapped[str]; version: Mapped[str]; task_type: Mapped[str]; description: Mapped[str \| None]; created_at: Mapped[datetime]` | A versioned gold set (TRD §7, §9). Cases are immutable once a run references them. |
| `EvaluationCase` | class (Base) | 393 | `id: Mapped[uuid.UUID]; dataset_id: Mapped[uuid.UUID]; external_id: Mapped[str]; split: Mapped[str]; question: Mapped[str]; reference_answer: Mapped[str \| None]; answerable: Mapped[bool]; expected_evidence: Mapped[list[dict[str, object]]]; expected_chunk_ids: Mapped[list[str]]; expected_sql: Mapped[str \| None]; tags: Mapped[list[str]]` |  |
| `EvaluationRun` | class (Base) | 422 | `id: Mapped[uuid.UUID]; dataset_id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; label: Mapped[str]; config: Mapped[dict[str, object]]; strategy: Mapped[str]; model_id: Mapped[str \| None]; status: Mapped[str]; progress: Mapped[int]; total: Mapped[int]; aggregate_metrics: Mapped[dict[str, object]]; error: Mapped[str \| None] …` |  |
| `EvaluationResult` | class (Base) | 459 | `id: Mapped[uuid.UUID]; run_id: Mapped[uuid.UUID]; case_id: Mapped[uuid.UUID]; retrieved_ids: Mapped[list[dict[str, object]]]; answer: Mapped[str \| None]; metrics: Mapped[dict[str, object]]; failure_category: Mapped[str \| None]; latency_ms: Mapped[int \| None]; error: Mapped[str \| None]` |  |
| `SqlConnection` | class (Base) | 482 | `id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; display_name: Mapped[str]; db_type: Mapped[str]; host: Mapped[str]; port: Mapped[int]; database_name: Mapped[str]; username: Mapped[str]; encrypted_secret_ref: Mapped[str]; allowed_schemas: Mapped[list[str]]; is_demo: Mapped[bool]; created_at: Mapped[datetime]` | A read-only database the SQL Analyst may query (TRD §7). The secret is write-only: stored encrypted (Fernet) and never returned by the API (ADR-006, ADR-000 G-4). |
| `SqlGlossaryTerm` | class (Base) | 510 | `id: Mapped[uuid.UUID]; connection_id: Mapped[uuid.UUID]; term: Mapped[str]; kind: Mapped[str]; definition: Mapped[str \| None]; synonyms: Mapped[list[str]]; options: Mapped[list[dict[str, object]]]` | Business definitions shown to the user and the model (TRD §10). `ambiguous` terms carry 2-4 options and always trigger a clarification until the user picks one. |
| `SqlQueryLog` | class (Base) | 535 | `id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID]; connection_id: Mapped[uuid.UUID]; question: Mapped[str]; status: Mapped[str]; clarification: Mapped[dict[str, object] \| None]; sql_redacted: Mapped[str \| None]; decision: Mapped[dict[str, object]]; row_count: Mapped[int \| None]; duration_ms: Mapped[int \| None]; created_at: Mapped[datetime]` | Every SQL Analyst turn with its safety decision, for reproducibility (TRD §10). String literals in stored SQL are redacted; credentials are never stored here. |
| `AuditEvent` | class (Base) | 569 | `id: Mapped[uuid.UUID]; workspace_id: Mapped[uuid.UUID \| None]; actor: Mapped[str]; action: Mapped[str]; resource_type: Mapped[str]; resource_id: Mapped[str \| None]; request_id: Mapped[str \| None]; metadata_safe: Mapped[dict[str, object]]; created_at: Mapped[datetime]` | Who did what, when, with which request (TRD §7, §11). `metadata_safe` holds ids, counts and statuses only: never document text, questions, SQL literals or credentials. |

#### `apps/api/app/db/session.py`

*Shared SQLAlchemy engine and request sessions. Sync engine + psycopg 3: endpoints are `def` and run in the threadpool.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `get_engine` | function `@lru_cache` | 18 | `() -> Engine` |  |
| `_session_factory` | function `@lru_cache` | 31 | `() -> sessionmaker[Session]` |  |
| `get_session` | function | 35 | `() -> Iterator[Session]` | FastAPI dependency: one session per request, always closed (rolled back if uncommitted). |

### Application factory

#### `apps/api/app/main.py`

*FastAPI application factory. Run: uvicorn app.main:app --port 8000*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `create_app` | function | 13 | `(settings: Settings \| None = None) -> FastAPI` |  |

### Audit trail

#### `apps/api/app/modules/audit.py`

*Audit trail (TRD §7 audit_events, §11). Records ids, counts and statuses, never content.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_safe` | function | 18 | `(metadata: dict[str, Any]) -> dict[str, object]` |  |
| `record` | function | 27 | `(session: Session, *, workspace_id: uuid.UUID \| None, action: str, resource_type: str, resource_id: object \| None = None, actor: str = 'local-user') -> None` |  |
| `audit_commit` | function | 50 | `(session: Session, workspace_id: uuid.UUID \| None, action: str, resource_type: str, resource_id: object \| None = None) -> None` | Record an event for a change that has just been made, and commit it. |

### Document upload, validation, storage, extraction, chunking

#### `apps/api/app/modules/documents/chunking.py`

*Chunking strategies (TRD §9 S1/S2, ADR-005).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `ChunkingConfig` | class (—) | 27 | `size: int; overlap: int` |  |
| `Chunk` | class (—) | 37 | `index: int; text: str; page_start: int \| None; page_end: int \| None; section_path: str \| None; strategy: Strategy` |  |
| ↳ `Chunk.char_count` | method | 46 | `() -> int` |  |
| ↳ `Chunk.token_count` | method | 50 | `() -> int` |  |
| ↳ `Chunk.content_hash` | method | 54 | `() -> str` |  |
| `_section` | function | 58 | `(unit: Unit) -> str \| None` |  |
| `_snap_end` | function | 62 | `(text: str, start: int, end: int) -> int` | Move a window end back to the last whitespace so words aren't cut, if one is close. |
| `chunk_fixed` | function | 72 | `(units: list[Unit], cfg: ChunkingConfig) -> list[Chunk]` |  |
| `_split` | function | 109 | `(text: str, size: int, separators: tuple[str, ...] = _SEPARATORS) -> list[str]` | Split text into pieces no longer than `size`, preferring the coarsest separator. |
| `_merge` | function | 127 | `(pieces: list[str], size: int) -> list[str]` |  |
| `chunk_recursive` | function | 140 | `(units: list[Unit], cfg: ChunkingConfig) -> list[Chunk]` |  |
| `chunk` | function | 157 | `(units: list[Unit], strategy: Strategy, cfg: ChunkingConfig) -> list[Chunk]` |  |

#### `apps/api/app/modules/documents/extraction.py`

*Text extraction with page / heading metadata (TRD §6.1, ING-06..ING-08).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `Unit` | class (—) | 22 | `text: str; page: int \| None; section_path: tuple[str, ...]` |  |
| `Extraction` | class (—) | 29 | `units: list[Unit]; page_count: int \| None; granularity: Granularity; char_count: int` |  |
| `Limits` | class (—) | 37 | `max_pages: int; max_chars: int` |  |
| `ExtractionError` | class (Exception) | 42 |  | A safe, plain-language extraction failure. `retryable` is False for bad input. |
| ↳ `ExtractionError.__init__` | method | 45 | `(code: str, message: str, *, retryable: bool = False) -> None` |  |
| `_rebuild_error` | function | 56 | `(code: str, message: str, retryable: bool) -> ExtractionError` |  |
| `normalize` | function | 67 | `(text: str) -> str` |  |
| `_pdf` | function | 77 | `(path: Path, limits: Limits) -> tuple[list[Unit], int]` |  |
| `_docx` | function | 107 | `(path: Path) -> list[Unit]` |  |
| `_markdown` | function | 150 | `(text: str) -> list[Unit]` |  |
| `_read_text` | function | 176 | `(path: Path) -> str` |  |
| `extract` | function | 183 | `(path: Path, file_type: str, limits: Limits) -> Extraction` | Parse one stored file. Raises `ExtractionError` with a user-safe message. |
| `_child` | function | 226 | `(path: str, file_type: str, limits: Limits) -> Extraction \| ExtractionError` |  |
| `extract_with_timeout` | function | 235 | `(path: Path, file_type: str, limits: Limits, timeout_seconds: float) -> Extraction` | Run `extract` in a spawned child process and kill it if it runs too long. |

#### `apps/api/app/modules/documents/repository.py`

*Document and job queries. Every function takes `workspace_id` so no query can cross a workspace boundary by omission (SEC-03).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `get_document` | function | 14 | `(session: Session, workspace_id: uuid.UUID, document_id: uuid.UUID) -> Document \| None` |  |
| `list_documents` | function | 22 | `(session: Session, workspace_id: uuid.UUID, *, limit: int, offset: int, status: str \| None = None) -> tuple[Sequence[Document], int]` |  |
| `find_by_checksum` | function | 44 | `(session: Session, workspace_id: uuid.UUID, sha256: str) -> Sequence[Document]` | All versions with this content, newest version first. |
| `latest_jobs` | function | 53 | `(session: Session, document_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, IngestionJob]` |  |
| `active_job` | function | 67 | `(session: Session, document_id: uuid.UUID) -> IngestionJob \| None` |  |
| `get_job` | function | 79 | `(session: Session, workspace_id: uuid.UUID, job_id: uuid.UUID) -> IngestionJob \| None` |  |
| `chunk_counts` | function | 91 | `(session: Session, document_ids: Sequence[uuid.UUID], strategy: str = DEFAULT_STRATEGY) -> dict[uuid.UUID, int]` |  |
| `list_chunks` | function | 104 | `(session: Session, workspace_id: uuid.UUID, document_id: uuid.UUID, *, strategy: str, limit: int, offset: int) -> tuple[Sequence[Chunk], int]` |  |
| `list_sections` | function | 125 | `(session: Session, workspace_id: uuid.UUID, document_id: uuid.UUID, *, limit: int) -> tuple[Sequence[DocumentSection], int]` |  |

#### `apps/api/app/modules/documents/service.py`

*Document use cases: upload (with duplicate handling) and delete (ING-05, ING-12, ING-13).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `UploadOutput` | class (—) | 35 | `outcome: UploadOutcome; document: Document; job: IngestionJob \| None` |  |
| `to_document_out` | function | 41 | `(document: Document, latest_job: IngestionJob \| None, chunk_count: int \| None = None) -> DocumentOut` |  |
| `_duplicate_error` | function | 61 | `(existing: Document, latest_job: IngestionJob \| None) -> AppError` |  |
| `_queue_job` | function | 73 | `(session: Session, document: Document) -> IngestionJob` |  |
| `_reindex` | function | 80 | `(session: Session, document: Document) -> IngestionJob` | Queue processing again. Idempotent: an already queued/running job is reused. |
| `retry_document` | function | 89 | `(session: Session, document: Document) -> IngestionJob` | Queue a failed (or ready) document again. Reuses an active job, so it is idempotent. |
| `upload_document` | function | 94 | `(session: Session, storage: FileStorage, workspace: Workspace, *, filename: str \| None, declared_mime: str \| None, source: BinaryIO, max_bytes: int, on_duplicate: DuplicateAction \| None) -> UploadOutput` |  |
| `delete_document` | function | 175 | `(session: Session, storage: FileStorage, workspace_id: uuid.UUID, document_id: uuid.UUID) -> bool` | Delete metadata, jobs and the stored file. Idempotent; returns whether anything existed. |

#### `apps/api/app/modules/documents/storage.py`

*Local file storage for uploads (ING-03, ING-04, SEC-06).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `StorageError` | class (AppError) | 30 |  |  |
| ↳ `StorageError.__init__` | method | 31 | `(message: str = 'The file could not be stored.') -> None` |  |
| `IncomingFile` | class (—) | 36 | `path: Path; size_bytes: int; sha256: str` |  |
| `make_storage_key` | function | 42 | `(workspace_id: uuid.UUID, document_id: uuid.UUID) -> str` |  |
| `FileStorage` | class (—) | 46 |  |  |
| ↳ `FileStorage.__init__` | method | 47 | `(root: Path) -> None` |  |
| ↳ `FileStorage._incoming_dir` | method | 50 | `() -> Path` |  |
| ↳ `FileStorage.path_for` | method | 55 | `(key: str) -> Path` | Resolve a storage key to a path, refusing anything that could escape the root. |
| ↳ `FileStorage.receive` | method | 64 | `(source: BinaryIO, max_bytes: int) -> IncomingFile` | Stream `source` to an incoming file, hashing it and enforcing `max_bytes`. |
| ↳ `FileStorage.discard` | method | 89 | `(incoming: IncomingFile) -> None` |  |
| ↳ `FileStorage.commit` | method | 92 | `(incoming: IncomingFile, key: str) -> Path` | Move an incoming file to its final location. Never overwrites an existing file. |
| ↳ `FileStorage.delete` | method | 105 | `(key: str) -> bool` | Remove a stored file. Missing files are fine: deletion is idempotent. |

#### `apps/api/app/modules/documents/validation.py`

*Upload validation (ING-01, ING-02, SEC-01): extension allowlist, declared MIME, file signature.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `FileFormat` | class (—) | 27 | `file_type: FileType; label: str; mime_type: str; extensions: tuple[str, ...]; accepted_mimes: frozenset[str]` |  |
| `UploadRejectedError` | class (AppError) | 58 |  | A user-correctable upload problem. Messages name the file problem, never internals. |
| `sanitize_filename` | function | 62 | `(raw: str \| None) -> str` | Display name only: last path segment, no control characters, NFC, at most 255 chars. |
| `format_for_filename` | function | 76 | `(name: str) -> FileFormat` |  |
| `check_declared_mime` | function | 88 | `(fmt: FileFormat, declared: str \| None) -> None` |  |
| `_signature_error` | function | 99 | `(fmt: FileFormat, why: str) -> UploadRejectedError` |  |
| `_check_pdf` | function | 105 | `(path: Path, fmt: FileFormat) -> None` |  |
| `_check_docx` | function | 113 | `(path: Path, fmt: FileFormat) -> None` |  |
| `_check_text` | function | 128 | `(path: Path, fmt: FileFormat) -> None` |  |
| `check_signature` | function | 148 | `(fmt: FileFormat, path: Path) -> None` |  |

### Evaluation Lab

#### `apps/api/app/modules/evaluation/importer.py`

*CSV / JSONL import of evaluation cases with row-level errors (TRD §8, PRD §5.4).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `EvidenceIn` | class (BaseModel) | 23 | `document: str; quote: str \| None; page: int \| None` |  |
| `CaseIn` | class (BaseModel) | 29 | `id: str \| None; split: str; question: str; reference_answer: str \| None; answerable: bool; expected_evidence: list[EvidenceIn]; expected_chunk_ids: list[str]; expected_sql: str \| None; tags: list[str]` |  |
| ↳ `CaseIn.split_valid` | method | 42 | `(v: str) -> str` |  |
| ↳ `CaseIn.strip` | method | 50 | `(v: str) -> str` |  |
| `RowError` | class (—) | 57 | `row: int; message: str` |  |
| `_list` | function | 62 | `(value: Any) -> list[str]` |  |
| `_bool` | function | 70 | `(value: Any) -> Any` |  |
| `_from_csv_row` | function | 80 | `(row: dict[str, str]) -> dict[str, Any]` |  |
| `parse_cases` | function | 100 | `(filename: str, content: bytes) -> tuple[list[CaseIn], list[RowError]]` |  |

#### `apps/api/app/modules/evaluation/metrics.py`

*Deterministic retrieval and answer metrics (TRD §9). No LLM judge is used anywhere here.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `norm` | function | 30 | `(text: str) -> str` |  |
| `Retrieved` | class (—) | 35 | `chunk_id: str; document_name: str; text: str; page_start: int \| None; page_end: int \| None` |  |
| `matches` | function | 43 | `(chunk: Retrieved, evidence: dict[str, Any]) -> bool` |  |
| `relevance` | function | 56 | `(retrieved: list[Retrieved], evidence: list[dict[str, Any]], chunk_ids: list[str]) -> tuple[list[bool], list[int \| None]]` | Per chunk: relevant?, and which evidence item it is the *first* match for (for nDCG). |
| `retrieval_metrics` | function | 75 | `(retrieved: list[Retrieved], evidence: list[dict[str, Any]], chunk_ids: list[str], k: int) -> dict[str, float]` |  |
| `percentile` | function | 103 | `(values: list[float], p: float) -> float \| None` |  |
| `aggregate` | function | 112 | `(results: list[dict[str, Any]]) -> dict[str, Any]` | Means over the cases each metric applies to, with the sample count for each. |

#### `apps/api/app/modules/evaluation/runner.py`

*Evaluation runs (TRD §9, PRD §5.4): created by the API, executed by the worker, case by case.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `RunConfigIn` | class (BaseModel) | 61 | `preset: Preset; chunk_strategy: Literal['fixed', 'recursive']; mode: Literal['dense', 'lexical', 'hybrid']; rerank: bool; top_k: int; candidates: int; split: Literal['dev', 'test', 'all']; generate_answers: bool; label: str \| None` |  |
| ↳ `RunConfigIn.resolved` | method | 72 | `() -> 'RunConfigIn'` |  |
| `machine_profile` | function | 78 | `() -> dict[str, Any]` |  |
| `_cases` | function | 116 | `(session: Session, dataset_id: uuid.UUID, split: str) -> list[EvaluationCase]` |  |
| `create_run` | function | 123 | `(session: Session, settings: Settings, workspace_id: uuid.UUID, dataset_id: uuid.UUID, cfg_in: RunConfigIn) -> EvaluationRun` |  |
| `recover_stale_runs` | function | 204 | `(session: Session, settings: Settings) -> int` |  |
| `claim_next_run` | function | 217 | `(session: Session) -> uuid.UUID \| None` |  |
| `_failure` | function | 236 | `(metrics: dict[str, Any], answerable: bool) -> str \| None` |  |
| `score_case` | function | 250 | `(session: Session, settings: Settings, run: EvaluationRun, case: EvaluationCase, chat: ChatModel \| None, reranker: rr.Reranker \| None) -> EvaluationResult` |  |
| `execute_run` | function | 350 | `(factory: sessionmaker[Session], settings: Settings, run_id: uuid.UUID, *, chat_factory: Callable[[Session], ChatModel], reranker: rr.Reranker \| None = None) -> None` |  |

#### `apps/api/app/modules/evaluation/service.py`

*Evaluation datasets and runs: CRUD, import, sample loading and export (PRD §5.4).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_dataset` | function | 39 | `(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID) -> EvaluationDataset` |  |
| `create_dataset` | function | 50 | `(session: Session, workspace_id: uuid.UUID, body: DatasetIn) -> EvaluationDataset` |  |
| `_missing_documents` | function | 72 | `(session: Session, workspace_id: uuid.UUID, cases: list[EvaluationCase]) -> list[str]` |  |
| `dataset_out` | function | 93 | `(session: Session, ds: EvaluationDataset, with_cases: bool = False) -> DatasetOut` |  |
| `list_datasets` | function | 136 | `(session: Session, workspace_id: uuid.UUID) -> list[DatasetOut]` |  |
| `get_dataset` | function | 145 | `(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID) -> DatasetOut` |  |
| `delete_dataset` | function | 149 | `(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID) -> None` |  |
| `add_cases` | function | 158 | `(session: Session, ds: EvaluationDataset, cases: list[CaseIn]) -> int` |  |
| `import_cases` | function | 186 | `(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID, filename: str, content: bytes) -> tuple[int, list[RowError]]` |  |
| `load_sample` | function | 206 | `(session: Session, storage: FileStorage, workspace: Workspace, samples_root: Path, max_bytes: int) -> tuple[uuid.UUID, int, int]` | Upload the synthetic sample corpus (skipping identical files) and its gold set. |
| `run_out` | function | 272 | `(run: EvaluationRun) -> RunOut` |  |
| `list_runs` | function | 276 | `(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID \| None) -> list[RunOut]` |  |
| `_run` | function | 288 | `(session: Session, workspace_id: uuid.UUID, run_id: uuid.UUID) -> EvaluationRun` |  |
| `get_run` | function | 299 | `(session: Session, workspace_id: uuid.UUID, run_id: uuid.UUID) -> RunDetail` |  |
| `delete_run` | function | 331 | `(session: Session, workspace_id: uuid.UUID, run_id: uuid.UUID) -> None` |  |
| `export_run` | function | 356 | `(detail: RunDetail, fmt: str) -> tuple[str, str]` | (content, media type). JSON includes the full config; CSV is one row per case. |

### Local model integration (Ollama, embeddings, reranker, gate)

#### `apps/api/app/modules/models/embedding_stage.py`

*Ingestion stage 3: embed chunks locally in batches and store them with their version (M3).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `embedding_text` | function | 26 | `(chunk: Chunk) -> str` |  |
| `attach_embedding` | function | 30 | `(pipeline: Pipeline) -> None` |  |

#### `apps/api/app/modules/models/gate.py`

*One process-wide cap on concurrent local generations (TRD §11 DoS, §12).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_semaphore` | function | 20 | `(settings: Settings) -> threading.BoundedSemaphore` |  |
| `generation_slot` | function `@contextmanager` | 29 | `(settings: Settings) -> Iterator[None]` |  |
| `busy` | function | 48 | `() -> bool` |  |

#### `apps/api/app/modules/models/interfaces.py`

*Provider-agnostic model interfaces (TRD §4). v1 ships Ollama implementations only.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `ModelError` | class (Exception) | 7 |  | A user-safe model failure. `retryable` marks transient problems (timeouts, not running). |
| ↳ `ModelError.__init__` | method | 10 | `(code: str, message: str, *, retryable: bool = False) -> None` |  |
| `ChatMessage` | class (—) | 18 | `role: Literal['system', 'user', 'assistant']; content: str` |  |
| `ChatResult` | class (—) | 24 | `content: str; model: str; latency_ms: int; prompt_tokens: int \| None; completion_tokens: int \| None; done_reason: str \| None` |  |
| `EmbeddingModel` | class (Protocol) | 33 | `name: str` |  |
| ↳ `EmbeddingModel.embed_documents` | method | 36 | `(texts: list[str]) -> list[list[float]]` |  |
| ↳ `EmbeddingModel.embed_query` | method | 38 | `(text: str) -> list[float]` |  |
| `ChatModel` | class (Protocol) | 41 | `name: str` |  |
| ↳ `ChatModel.complete` | method | 44 | `(messages: list[ChatMessage], *, temperature: float, json_schema: dict[str, Any] \| None = None, num_predict: int = 768) -> ChatResult` |  |

#### `apps/api/app/modules/models/ollama.py`

*Ollama adapters: the only model provider KnowFlow ships (TRD §4, ADR-001, ADR-007).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `InstalledModel` | class (—) | 24 | `name: str; digest: str; size_bytes: int; family: str \| None; parameter_size: str \| None; quantization: str \| None` |  |
| `OllamaClient` | class (—) | 33 |  |  |
| ↳ `OllamaClient.__init__` | method | 34 | `(base_url: str, *, timeout: float, transport: httpx.BaseTransport \| None = None) -> None` |  |
| ↳ `OllamaClient.close` | method | 41 | `() -> None` |  |
| ↳ `OllamaClient._post` | method | 44 | `(path: str, payload: dict[str, Any], *, timeout: float \| None = None) -> Any` |  |
| ↳ `OllamaClient._send` | method | 71 | `(path: str, payload: dict[str, Any], timeout: float \| None) -> httpx.Response` |  |
| ↳ `OllamaClient.version` | method | 87 | `() -> str` |  |
| ↳ `OllamaClient.list_models` | method | 95 | `() -> list[InstalledModel]` |  |
| ↳ `OllamaClient.show` | method | 117 | `(model: str) -> dict[str, Any]` |  |
| ↳ `OllamaClient.embed` | method | 121 | `(model: str, texts: list[str]) -> list[list[float]]` |  |
| ↳ `OllamaClient.chat` | method | 128 | `(model: str, messages: list[ChatMessage], *, temperature: float, json_schema: dict[str, Any] \| None = None, num_ctx: int = 4096, num_predict: int = 768, timeout: float \| None = None, think: bool = False) -> ChatResult` |  |
| `validate_vectors` | function | 165 | `(vectors: list[list[float]], dimension: int \| None) -> int` | Every vector has the same (expected) dimension and only finite values (TRD §6.1). |
| `parse_json_object` | function | 182 | `(content: str) -> dict[str, Any]` | Structured output is untrusted until parsed and validated by the caller. |
| `_runtime_reason` | function | 193 | `(response: httpx.Response) -> str` | Ollama's own error text (e.g. "model requires more system memory"), shortened. |

#### `apps/api/app/modules/models/registry.py`

*Which local models are in use, and the embedding space they define (PRD §5.6, TRD §4.2).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `EffectiveModels` | class (—) | 27 | `generation_model: str; embedding_model: str; reranker_enabled: bool` |  |
| `effective_models` | function | 33 | `(session: Session, settings: Settings) -> EffectiveModels` |  |
| `ollama_client` | function `@lru_cache(maxsize=4)` | 45 | `(base_url: str, timeout: float) -> OllamaClient` |  |
| `client_for` | function | 49 | `(settings: Settings) -> OllamaClient` |  |
| `task_prefixes` | function | 53 | `(model: str) -> tuple[str, str]` | nomic-embed-text is trained with task prefixes; without them retrieval quality drops. |
| `model_digest` | function | 60 | `(client: OllamaClient, model: str) -> str` |  |
| `probe_dimension` | function | 69 | `(client: OllamaClient, model: str) -> int` |  |
| `active_embedding_version` | function | 74 | `(session: Session) -> EmbeddingVersion \| None` |  |
| `ensure_embedding_version` | function | 78 | `(session: Session, client: OllamaClient, model: str) -> EmbeddingVersion` | Return the active version for `model`, probing and activating a new one when needed. |
| `OllamaEmbedding` | class (—) | 116 |  |  |
| ↳ `OllamaEmbedding.__init__` | method | 117 | `(client: OllamaClient, version: EmbeddingVersion, batch_size: int) -> None` |  |
| ↳ `OllamaEmbedding.embed_documents` | method | 125 | `(texts: list[str]) -> list[list[float]]` |  |
| ↳ `OllamaEmbedding.embed_query` | method | 134 | `(text: str) -> list[float]` |  |
| `OllamaChat` | class (—) | 140 |  |  |
| ↳ `OllamaChat.__init__` | method | 141 | `(client: OllamaClient, model: str, settings: Settings) -> None` |  |
| ↳ `OllamaChat.complete` | method | 146 | `(messages: list[ChatMessage], *, temperature: float, json_schema: dict[str, Any] \| None = None, num_predict: int = 768) -> ChatResult` |  |
| `chat_model` | function | 165 | `(session: Session, settings: Settings) -> OllamaChat` |  |
| `query_embedder` | function | 171 | `(session: Session, settings: Settings) -> OllamaEmbedding \| None` | Embedder for queries in the *active* space, or None when nothing is embedded yet. |

#### `apps/api/app/modules/models/reranker.py`

*Optional local CrossEncoder reranker (TRD §4.2, ADR-004). Off by default.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `Reranker` | class (Protocol) | 19 | `name: str` |  |
| ↳ `Reranker.score` | method | 22 | `(query: str, passages: list[str]) -> list[float]` |  |
| `available` | function | 25 | `() -> bool` |  |
| `CrossEncoderReranker` | class (—) | 29 |  |  |
| ↳ `CrossEncoderReranker.__init__` | method | 30 | `(model_name: str) -> None` |  |
| ↳ `CrossEncoderReranker._load` | method | 35 | `() -> Any` |  |
| ↳ `CrossEncoderReranker.score` | method | 49 | `(query: str, passages: list[str]) -> list[float]` |  |
| `get_reranker` | function | 57 | `(model_name: str) -> CrossEncoderReranker` |  |
| `rerank` | function | 63 | `(reranker: Reranker, query: str, candidates: list[Candidate]) -> list[Candidate]` |  |

#### `apps/api/app/modules/models/service.py`

*Model settings use cases: inspect the local runtime, validate a selection, save it (PRD §5.6).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_client` | function | 41 | `(settings: Settings) -> OllamaClient` |  |
| `_kind` | function | 45 | `(m: InstalledModel) -> str` |  |
| `reranker_available` | function | 52 | `() -> bool` |  |
| `documents_needing_reindex` | function | 56 | `(session: Session, workspace_id: uuid.UUID) -> int` | Ready documents with no vectors in the active embedding space. |
| `describe` | function | 74 | `(session: Session, settings: Settings, workspace_id: uuid.UUID) -> ModelSettingsOut` |  |
| `_Probe` | class (BaseModel) | 125 | `ok: bool` |  |
| `validate` | function | 136 | `(session: Session, settings: Settings, req: ValidateRequest) -> ValidateResponse` |  |
| `save` | function | 233 | `(session: Session, settings: Settings, req: SaveRequest) -> bool` | Persist the selection. Returns True when existing vectors must be rebuilt. |
| `reindex_all` | function | 271 | `(session: Session, workspace_id: uuid.UUID) -> int` | Queue every ready or failed document that isn't already queued/running. |

### Grounded answer generation

#### `apps/api/app/modules/rag/answer.py`

*Grounded answer generation (TRD §6.2): pack evidence, abstain on weak evidence, generate with a JSON schema, then *verify* citations before anything reaches the user.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `ModelAnswer` | class (BaseModel) | 25 | `answer: str; citations: list[int]; abstained: bool; missing: str \| None` |  |
| `Citation` | class (—) | 33 | `number: int; candidate: Candidate` |  |
| `GroundedAnswer` | class (—) | 39 | `text: str; citations: list[Citation]; abstained: bool; abstain_reason: AbstainReason \| None; sources_considered: int; sources_supplied: int; model: str \| None; prompt_version: str; generation_ms: int \| None; tokens: dict[str, int \| None]` |  |
| `pack_context` | function | 52 | `(candidates: list[Candidate], max_chars: int) -> list[Candidate]` | Deduplicate overlapping passages and stay inside the context budget, keeping rank order. |
| `verify_citations` | function | 74 | `(text: str, listed: list[int], n_sources: int) -> tuple[str, list[int]]` | Drop invalid markers and renumber. Returns (text, original source numbers in new order). |
| `answer_question` | function | 107 | `(question: str, candidates: list[Candidate], chat: ChatModel, *, max_context_chars: int, min_score: float \| None, temperature: float) -> GroundedAnswer` |  |

#### `apps/api/app/modules/rag/prompts.py`

*Versioned RAG prompts (TRD §4.3, §15). Change the text => bump PROMPT_VERSION.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_location` | function | 41 | `(c: Candidate) -> str` |  |
| `_escape` | function | 54 | `(text: str) -> str` |  |
| `build_user_prompt` | function | 59 | `(question: str, sources: list[Candidate]) -> str` |  |

#### `apps/api/app/modules/rag/service.py`

*Ask KnowFlow use case: validate scope -> retrieve -> answer -> persist the turn (TRD §6.2).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_title` | function | 42 | `(question: str) -> str` |  |
| `_validate_documents` | function | 47 | `(session: Session, workspace_id: uuid.UUID, ids: list[uuid.UUID]) -> None` |  |
| `citation_out` | function | 63 | `(c: Any) -> CitationOut` |  |
| `ask` | function | 78 | `(session: Session, settings: Settings, workspace_id: uuid.UUID, query: ChatQuery, chat: ChatModel, *, retriever: Retriever = retrieve) -> AnswerOut` |  |
| `list_conversations` | function | 215 | `(session: Session, workspace_id: uuid.UUID, *, limit: int, offset: int) -> tuple[list[ConversationOut], int]` |  |
| `get_conversation` | function | 248 | `(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> Conversation` |  |
| `conversation_detail` | function | 259 | `(session: Session, conversation: Conversation) -> ConversationDetail` |  |
| `set_feedback` | function | 290 | `(session: Session, workspace_id: uuid.UUID, message_id: uuid.UUID, rating: str, reason: str \| None) -> None` |  |

### Dense, lexical and hybrid retrieval

#### `apps/api/app/modules/retrieval/dense.py`

*Dense retrieval with pgvector exact cosine search (TRD §3: exact first, HNSW only if measured).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `dense_search` | function | 17 | `(session: Session, query_vector: list[float], version_id: uuid.UUID, scope: Scope, limit: int) -> list[Candidate]` |  |

#### `apps/api/app/modules/retrieval/fusion.py`

*Reciprocal Rank Fusion (TRD §6.2, ADR-004): score(d) = Σ 1 / (k + rank_r(d)).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `rrf` | function | 10 | `(ranked_lists: dict[str, list[Candidate]], k: int = 60) -> list[Candidate]` |  |

#### `apps/api/app/modules/retrieval/lexical.py`

*PostgreSQL full-text retrieval (TRD §3, §9): OR over the question's stemmed terms, ranked by `ts_rank_cd` (cover density), so chunks matching more and closer terms rank first.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `scoped` | function | 22 | `(stmt: Select[tuple[Chunk, str]], scope: Scope) -> Select[tuple[Chunk, str]]` |  |
| `to_candidate` | function | 34 | `(chunk: Chunk, name: str, score: float, retriever: str, rank: int) -> Candidate` |  |
| `any_terms_query` | function | 49 | `(query: str) -> ColumnElement[Any]` |  |
| `lexical_search` | function | 54 | `(session: Session, query: str, scope: Scope, limit: int) -> list[Candidate]` |  |

#### `apps/api/app/modules/retrieval/service.py`

*One entry point for retrieval, shared by RAG and the Evaluation Lab (TRD §6.2, §9).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `RetrievalConfig` | class (—) | 32 | `mode: RetrievalMode; strategy: ChunkStrategy; top_k: int; candidates: int; rerank: bool; rrf_k: int` |  |
| `RetrievalResult` | class (—) | 43 | `candidates: list[Candidate]; mode: str; strategy: ChunkStrategy; timings_ms: dict[str, int]; embedding_version_id: uuid.UUID \| None; reranked: bool` |  |
| `_ms` | function | 52 | `(started: float) -> int` |  |
| `_dense` | function | 56 | `(session: Session, settings: Settings, question: str, scope: Scope, limit: int, timings: dict[str, int]) -> tuple[list[Candidate], uuid.UUID]` |  |
| `retrieve` | function | 84 | `(session: Session, settings: Settings, question: str, config: RetrievalConfig, scope: Scope, *, reranker: Reranker \| None = None) -> RetrievalResult` |  |

#### `apps/api/app/modules/retrieval/types.py`

*Shared retrieval types. Every retriever returns ranked `Candidate`s for the same chunk set.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `Scope` | class (—) | 11 | `workspace_id: uuid.UUID; strategy: ChunkStrategy; document_ids: tuple[uuid.UUID, ...] \| None` | What a query may see. The workspace filter is applied inside every SQL query (SEC-03). |
| `Candidate` | class (—) | 20 | `chunk_id: uuid.UUID; document_id: uuid.UUID; document_name: str; text: str; page_start: int \| None; page_end: int \| None; section_path: str \| None; chunk_index: int; score: float; ranks: dict[str, int]` |  |

### Text-to-SQL

#### `apps/api/app/modules/sql_assistant/assistant.py`

*Text-to-SQL with clarification (TRD §6.3, §10; PRD §5.5, Journey C).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `GlossaryEntry` | class (—) | 31 | `term: str; kind: Literal['definition', 'ambiguous']; definition: str \| None; synonyms: list[str]; options: list[dict[str, str]]` |  |
| `Choice` | class (—) | 40 | `term: str; option_id: str \| None; custom_definition: str \| None` |  |
| `_pattern` | function | 46 | `(phrase: str) -> re.Pattern[str]` |  |
| `matching_terms` | function | 52 | `(question: str, glossary: list[GlossaryEntry]) -> list[GlossaryEntry]` |  |
| `pending_clarification` | function | 57 | `(question: str, glossary: list[GlossaryEntry], choices: list[Choice]) -> GlossaryEntry \| None` |  |
| `resolved_definitions` | function | 67 | `(question: str, glossary: list[GlossaryEntry], choices: list[Choice]) -> list[tuple[str, str]]` | (term, definition) pairs the model must follow for this question. |
| `ClarificationOption` | class (BaseModel) | 87 | `label: str; definition: str` |  |
| `ModelClarification` | class (BaseModel) | 92 | `question: str; missing_concept: str; options: list[ClarificationOption]` |  |
| `ModelSqlOutput` | class (BaseModel) | 98 | `status: Literal['ready', 'clarification_required', 'unsupported']; sql: str \| None; explanation: str; assumptions: list[str]; tables: list[str]; clarification: ModelClarification \| None; reason: str \| None` |  |
| `Repair` | class (—) | 170 | `sql: str; error: str` | A previous attempt the database rejected; the model gets one chance to fix it. |
| `build_prompt` | function | 177 | `(question: str, schema_text: str, definitions: list[tuple[str, str]], today: date, repair: Repair \| None = None) -> str` |  |
| `generate` | function | 197 | `(chat: ChatModel, question: str, schema_text: str, definitions: list[tuple[str, str]], today: date, repair: Repair \| None = None) -> tuple[ModelSqlOutput, int]` |  |

#### `apps/api/app/modules/sql_assistant/database.py`

*Connecting to an analysed database: read-only checks, schema introspection, execution.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `Target` | class (—) | 26 | `host: str; port: int; database: str; username: str; password: str` |  |
| `_engine` | function `@lru_cache(maxsize=8)` | 35 | `(host: str, port: int, database: str, username: str, password: str) -> Engine` |  |
| `engine_for` | function | 53 | `(t: Target) -> Engine` |  |
| `_connection_error` | function | 57 | `(exc: Exception) -> AppError` |  |
| `ReadOnlyCheck` | class (—) | 67 | `server_version: str; is_superuser: bool; writable_tables: list[str]; read_only_default: bool` |  |
| `check_read_only` | function | 74 | `(t: Target, schemas: list[str]) -> ReadOnlyCheck` |  |
| `require_read_only` | function | 102 | `(check: ReadOnlyCheck) -> None` |  |
| `Column` | class (—) | 120 | `name: str; data_type: str; nullable: bool; description: str \| None` |  |
| `Table` | class (—) | 128 | `schema: str; name: str; description: str \| None; columns: list[Column]; references: list[str]` |  |
| `introspect` | function | 137 | `(t: Target, schemas: list[str]) -> list[Table]` | Allow-listed schemas only: tables, columns, types and comments. No data is read. |
| `schema_prompt` | function | 188 | `(tables: list[Table]) -> str` | Compact schema description for the model: names, types, comments. Never credentials. |
| `_json_value` | function | 203 | `(v: Any) -> Any` |  |
| `QueryResult` | class (—) | 214 | `columns: list[str]; rows: list[list[Any]]; truncated: bool; duration_ms: int` |  |
| `execute` | function | 221 | `(t: Target, sql: str, *, max_rows: int, statement_timeout_ms: int, lock_timeout_ms: int) -> QueryResult` |  |

#### `apps/api/app/modules/sql_assistant/demo.py`

*Synthetic sales demo database for the SQL Analyst (PRD §5.5, §10; TRD §10).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_identifier` | function | 158 | `(value: str) -> str` |  |
| `_rows` | function | 164 | `(today: date) -> dict[str, list[tuple[object, ...]]]` |  |
| `admin_url` | function | 219 | `(settings: Settings, database: str) -> URL` |  |
| `seed` | function | 223 | `(settings: Settings \| None = None, *, today: date \| None = None) -> dict[str, int]` |  |
| `main` | function | 295 | `() -> None` |  |

#### `apps/api/app/modules/sql_assistant/secrets.py`

*Write-only connection secrets (TRD §7 `encrypted_secret_ref`, ADR-006, ADR-000 G-4).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `_key` | function | 17 | `(settings: Settings) -> bytes` |  |
| `encrypt` | function | 33 | `(settings: Settings, secret: str) -> str` |  |
| `decrypt` | function | 37 | `(settings: Settings, token: str) -> str` |  |

#### `apps/api/app/modules/sql_assistant/service.py`

*SQL Analyst use cases: connections, schema, glossary, questions and history (PRD §5.5).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `connection_out` | function | 111 | `(c: SqlConnection) -> ConnectionOut` |  |
| `_target` | function | 126 | `(settings: Settings, c: SqlConnection) -> db.Target` |  |
| `_replace_glossary` | function | 136 | `(session: Session, connection_id: uuid.UUID, terms: list[GlossaryTermIO]) -> None` |  |
| `ensure_demo_connection` | function | 162 | `(session: Session, settings: Settings, workspace_id: uuid.UUID) -> None` | Register the seeded demo database once it exists (scripts: dev.ps1 seed-demo). |
| `list_connections` | function | 195 | `(session: Session, settings: Settings, workspace_id: uuid.UUID) -> list[ConnectionOut]` |  |
| `get_connection` | function | 207 | `(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> SqlConnection` |  |
| `test_and_save` | function | 218 | `(session: Session, settings: Settings, workspace_id: uuid.UUID, body: ConnectionIn) -> ConnectionOut` | TRD §8 /sql/connections/test: connect, prove the role is read-only, then save. |
| `delete_connection` | function | 259 | `(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> None` |  |
| `glossary` | function | 270 | `(session: Session, cid: uuid.UUID) -> list[GlossaryTermIO]` |  |
| `save_glossary` | function | 288 | `(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID, terms: list[GlossaryTermIO]) -> list[GlossaryTermIO]` |  |
| `schema` | function | 297 | `(session: Session, settings: Settings, workspace_id: uuid.UUID, cid: uuid.UUID) -> SchemaOut` |  |
| `_entries` | function | 319 | `(terms: list[GlossaryTermIO]) -> list[GlossaryEntry]` |  |
| `_log` | function | 326 | `(session: Session, workspace_id: uuid.UUID, connection_id: uuid.UUID, answer: SqlAnswerOut, decision: dict[str, object]) -> SqlAnswerOut` |  |
| `ask` | function | 360 | `(session: Session, settings: Settings, workspace_id: uuid.UUID, body: SqlQueryIn, chat: ChatModel) -> SqlAnswerOut` |  |
| `history` | function | 470 | `(session: Session, workspace_id: uuid.UUID, cid: uuid.UUID) -> list[HistoryItem]` |  |

#### `apps/api/app/modules/sql_assistant/validation.py`

*SQL safety validation with SQLGlot's AST (TRD §6.3, §10, ADR-006). Regex is never used.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `SqlRejectedError` | class (Exception) | 110 |  |  |
| ↳ `SqlRejectedError.__init__` | method | 111 | `(reason: str, code: str = 'sql_rejected') -> None` |  |
| `ValidatedQuery` | class (—) | 118 | `sql: str; tables: list[str]; capped_at: int` |  |
| `_function_name` | function | 124 | `(node: object) -> str \| None` |  |
| `validate_sql` | function | 132 | `(sql: str, *, allowed_schemas: list[str], max_rows: int) -> ValidatedQuery` |  |
| `redact_literals` | function | 206 | `(sql: str) -> str` | Replace string literals with '?' before storing SQL in history (TRD §10). |

### Workspace resolution

#### `apps/api/app/modules/workspaces/service.py`

*Workspace resolution (WSP-02, CON-08). Local v1 is single-user: requests act in the default workspace, which the first migration creates. Every content query is still scoped by its id.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `get_default_workspace` | function | 11 | `(session: Session) -> Workspace` |  |
| `rename_workspace` | function | 22 | `(session: Session, workspace: Workspace, name: str) -> Workspace` |  |

### Pydantic request/response contracts

#### `apps/api/app/schemas/chat.py`

*Ask KnowFlow API contracts (TRD §8: /chat/query, /conversations).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `RetrievalConfigIn` | class (BaseModel) | 12 | `mode: Literal['dense', 'lexical', 'hybrid']; strategy: ChunkStrategy; top_k: int; rerank: bool` |  |
| `ChatQuery` | class (BaseModel) | 19 | `conversation_id: uuid.UUID \| None; question: str; document_ids: list[uuid.UUID] \| None; retrieval_config: RetrievalConfigIn` |  |
| ↳ `ChatQuery.not_blank` | method | 27 | `(v: str) -> str` |  |
| `CitationOut` | class (BaseModel) | 33 | `number: int; chunk_id: uuid.UUID; document_id: uuid.UUID; document_name: str; page_start: int \| None; page_end: int \| None; section_path: str \| None; excerpt: str` |  |
| `RetrievalTrace` | class (BaseModel) | 44 | `mode: str; strategy: str; top_k: int; candidates: int; sources_supplied: int; reranked: bool; timings_ms: dict[str, int]; candidate_ranks: list[dict[str, object]]` |  |
| `AnswerOut` | class (BaseModel) | 56 | `conversation_id: uuid.UUID; message_id: uuid.UUID; answer: str; citations: list[CitationOut]; abstained: bool; abstain_reason: str \| None; retrieval: RetrievalTrace; model: str \| None; prompt_version: str; latency_ms: int; request_id: str \| None` |  |
| `ConversationOut` | class (BaseModel) | 70 | `id: uuid.UUID; title: str; created_at: datetime; updated_at: datetime; message_count: int` |  |
| `FeedbackOut` | class (BaseModel) | 78 | `rating: Literal['helpful', 'not_helpful']; reason: str \| None` |  |
| `MessageOut` | class (BaseModel) | 83 | `id: uuid.UUID; role: Literal['user', 'assistant']; content: str; citations: list[CitationOut]; metadata: dict[str, object]; feedback: FeedbackOut \| None; created_at: datetime` |  |
| `ConversationDetail` | class (ConversationOut) | 93 | `messages: list[MessageOut]` |  |
| `RenameConversation` | class (BaseModel) | 97 | `title: str` |  |
| ↳ `RenameConversation.strip` | method | 102 | `(v: str) -> str` |  |
| `FeedbackIn` | class (BaseModel) | 108 | `rating: Literal['helpful', 'not_helpful']; reason: str \| None` |  |

#### `apps/api/app/schemas/common.py`

*Shared API contracts (API-05).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `Page` | class (BaseModel) | 9 | `items: list[T]; total: int; limit: int; offset: int` | Offset pagination. `total` is the full count of matching rows. |
| `PageParams` | class (BaseModel) | 18 | `limit: int; offset: int` |  |
| `page_params` | function | 25 | `(limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0, le=1000000)] = 0) -> PageParams` |  |

#### `apps/api/app/schemas/documents.py`

*Document and ingestion-job API contracts (TRD §8).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `JobOut` | class (BaseModel) | 17 | `id: uuid.UUID; document_id: uuid.UUID; status: JobStatus; stage: JobStage \| None; attempts: int; error_code: str \| None; error_message_safe: str \| None; created_at: datetime; started_at: datetime \| None; completed_at: datetime \| None` |  |
| `SafeError` | class (BaseModel) | 32 | `code: str; message: str` |  |
| `DocumentOut` | class (BaseModel) | 37 | `id: uuid.UUID; original_name: str; file_type: FileType; mime_type: str; size_bytes: int; sha256: str; version: int; status: DocumentStatus; page_count: int \| None; chunk_count: int \| None; extracted_char_count: int \| None; citation_granularity: Literal['page', 'section', 'document'] \| None …` |  |
| `UploadResult` | class (BaseModel) | 58 | `outcome: UploadOutcome; document_id: uuid.UUID; job_id: uuid.UUID \| None; status: DocumentStatus; document: DocumentOut` | `202` for created / new_version / reindexed, `200` for skipped (nothing new queued). |
| `SupportedFormatOut` | class (BaseModel) | 68 | `file_type: FileType; label: str; mime_type: str; extensions: list[str]` |  |
| `UploadPolicyOut` | class (BaseModel) | 75 | `max_bytes: int; formats: list[SupportedFormatOut]` |  |
| `ChunkOut` | class (BaseModel) | 80 | `id: uuid.UUID; document_id: uuid.UUID; strategy: ChunkStrategy; chunk_index: int; text: str; page_start: int \| None; page_end: int \| None; section_path: str \| None; char_count: int; token_count: int; content_hash: str` |  |
| `SectionOut` | class (BaseModel) | 96 | `ordinal: int; page_number: int \| None; section_path: str \| None; text: str` |  |
| `ExtractionPreviewOut` | class (BaseModel) | 105 | `total_sections: int; sections: list[SectionOut]` |  |

#### `apps/api/app/schemas/evaluation.py`

*Evaluation Lab API contracts (TRD §8).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `DatasetIn` | class (BaseModel) | 12 | `name: str; version: str; description: str \| None` |  |
| `DatasetOut` | class (BaseModel) | 18 | `id: uuid.UUID; name: str; version: str; description: str \| None; created_at: datetime; cases: int; dev_cases: int; test_cases: int; runs: int; missing_documents: list[str]` |  |
| `CaseOut` | class (BaseModel) | 32 | `id: uuid.UUID; external_id: str; split: str; question: str; reference_answer: str \| None; answerable: bool; expected_evidence: list[dict[str, Any]]; tags: list[str]` |  |
| `DatasetDetail` | class (DatasetOut) | 43 | `case_list: list[CaseOut]` |  |
| `ImportRowError` | class (BaseModel) | 47 | `row: int; message: str` |  |
| `ImportSummary` | class (BaseModel) | 52 | `imported: int; errors: list[ImportRowError]` |  |
| `SampleLoaded` | class (BaseModel) | 57 | `dataset_id: uuid.UUID; documents_queued: int; documents_existing: int` |  |
| `RunIn` | class (BaseModel) | 63 | `dataset_id: uuid.UUID; config: RunConfigIn` |  |
| `RunOut` | class (BaseModel) | 68 | `id: uuid.UUID; dataset_id: uuid.UUID; label: str; strategy: str; model_id: str \| None; status: str; progress: int; total: int; config: dict[str, Any]; aggregate_metrics: dict[str, Any]; error: str \| None; created_at: datetime …` |  |
| `ResultOut` | class (BaseModel) | 85 | `case_id: uuid.UUID; external_id: str; split: str; question: str; reference_answer: str \| None; answerable: bool; expected_evidence: list[dict[str, Any]]; tags: list[str]; retrieved: list[dict[str, Any]]; answer: str \| None; metrics: dict[str, Any]; failure_category: str \| None …` |  |
| `RunDetail` | class (RunOut) | 102 | `results: list[ResultOut]` |  |

#### `apps/api/app/schemas/search.py`

*Search API contracts.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `SearchHit` | class (BaseModel) | 11 | `chunk_id: uuid.UUID; document_id: uuid.UUID; document_name: str; text: str; page_start: int \| None; page_end: int \| None; section_path: str \| None; score: float; ranks: dict[str, int]` |  |
| `SearchResponse` | class (BaseModel) | 23 | `query: str; mode: Literal['lexical', 'dense', 'hybrid']; strategy: ChunkStrategy; hits: list[SearchHit]` |  |

#### `apps/api/app/schemas/settings.py`

*Models & Settings API contracts (TRD §8, PRD §5.6). No provider keys exist by design.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `InstalledModelOut` | class (BaseModel) | 9 | `name: str; digest: str; size_bytes: int; family: str \| None; parameter_size: str \| None; quantization: str \| None; kind: Literal['generation', 'embedding', 'unknown']` |  |
| `EmbeddingVersionOut` | class (BaseModel) | 19 | `model: str; digest: str; dimension: int; created_at: datetime` |  |
| `RerankerOut` | class (BaseModel) | 26 | `enabled: bool; available: bool; model: str; note: str` |  |
| `RuntimeOut` | class (BaseModel) | 33 | `reachable: bool; version: str \| None; base_url: str; error: str \| None` |  |
| `ModelSettingsOut` | class (BaseModel) | 40 | `runtime: RuntimeOut; installed: list[InstalledModelOut]; generation_model: str; embedding_model: str; reranker: RerankerOut; active_embedding: EmbeddingVersionOut \| None; documents_needing_reindex: int; setup_commands: list[str]` |  |
| `ModelSelection` | class (BaseModel) | 54 | `generation_model: str; embedding_model: str` |  |
| `ValidateRequest` | class (ModelSelection) | 59 | `probe_generation: bool` |  |
| `ValidationCheck` | class (BaseModel) | 64 | `name: str; state: Literal['ok', 'failed', 'skipped']; detail: str; latency_ms: int \| None` |  |
| `ValidateResponse` | class (BaseModel) | 71 | `ok: bool; checks: list[ValidationCheck]; embedding_dimension: int \| None; embedding_model_changed: bool` |  |
| `SaveRequest` | class (ModelSelection) | 78 | `reranker_enabled: bool` |  |
| `SaveResponse` | class (BaseModel) | 82 | `settings: ModelSettingsOut; reembed_required: bool` |  |
| `ReindexResponse` | class (BaseModel) | 87 | `queued: int` |  |

#### `apps/api/app/schemas/sql.py`

*SQL Analyst API contracts (TRD §8). Passwords are accepted, never returned.*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `ConnectionIn` | class (BaseModel) | 12 | `display_name: str; host: str; port: int; database_name: str; username: str; password: SecretStr; allowed_schemas: list[str]` |  |
| ↳ `ConnectionIn.schemas_valid` | method | 23 | `(v: list[str]) -> list[str]` |  |
| `ConnectionOut` | class (BaseModel) | 32 | `id: uuid.UUID; display_name: str; db_type: str; host: str; port: int; database_name: str; username: str; allowed_schemas: list[str]; is_demo: bool; created_at: datetime` |  |
| `ColumnOut` | class (BaseModel) | 46 | `name: str; data_type: str; nullable: bool; description: str \| None` |  |
| `TableOut` | class (BaseModel) | 53 | `schema_name: str; name: str; description: str \| None; columns: list[ColumnOut]` |  |
| `GlossaryOption` | class (BaseModel) | 60 | `id: str; label: str; definition: str` |  |
| `GlossaryTermIO` | class (BaseModel) | 66 | `term: str; kind: Literal['definition', 'ambiguous']; definition: str \| None; synonyms: list[str]; options: list[GlossaryOption]` |  |
| `SchemaOut` | class (BaseModel) | 74 | `connection: ConnectionOut; tables: list[TableOut]; glossary: list[GlossaryTermIO]; max_rows: int; statement_timeout_ms: int` |  |
| `ChoiceIn` | class (BaseModel) | 82 | `term: str; option_id: str \| None; custom_definition: str \| None` |  |
| `RepairIn` | class (BaseModel) | 88 | `sql: str; error: str` | Ask the model to fix a query the database rejected (one user-triggered attempt). |
| `SqlQueryIn` | class (BaseModel) | 95 | `connection_id: uuid.UUID; question: str; clarification_context: list[ChoiceIn]; repair: RepairIn \| None` |  |
| ↳ `SqlQueryIn.not_blank` | method | 103 | `(v: str) -> str` |  |
| `ClarificationOut` | class (BaseModel) | 109 | `term: str; question: str; options: list[GlossaryOption]; source: Literal['glossary', 'model']` |  |
| `SqlAnswerOut` | class (BaseModel) | 116 | `query_id: uuid.UUID; status: Literal['clarification_required', 'executed', 'rejected', 'failed', 'unsupported']; question: str; clarification: ClarificationOut \| None; sql: str \| None; explanation: str \| None; assumptions: list[str]; definitions_used: list[dict[str, str]]; tables: list[str]; columns: list[str]; rows: list[list[Any]]; row_count: int \| None …` |  |
| `HistoryItem` | class (BaseModel) | 142 | `id: uuid.UUID; question: str; status: str; row_count: int \| None; created_at: datetime` |  |

#### `apps/api/app/schemas/workspaces.py`

*Workspace API contracts (WSP-02).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `WorkspaceOut` | class (BaseModel) | 14 | `id: uuid.UUID; name: str; is_default: bool; created_at: datetime; updated_at: datetime` |  |
| `WorkspaceUpdate` | class (BaseModel) | 24 | `name: WorkspaceName` |  |

### Background worker

#### `apps/api/app/workers/ingestion.py`

*PostgreSQL-backed ingestion worker (TRD §3 "Background jobs", §6.1, §12).*

| Symbol | Kind | Line | Signature / fields | Responsibility (docstring) |
|---|---|---|---|---|
| `IngestionError` | class (Exception) | 53 |  |  |
| ↳ `IngestionError.__init__` | method | 54 | `(code: str, message: str, *, retryable: bool) -> None` |  |
| `EmbeddedChunks` | class (—) | 62 | `version_id: uuid.UUID; vectors: dict[tuple[str, int], list[float]]` |  |
| `Pipeline` | class (—) | 77 | `session_factory: sessionmaker[Session]; storage: FileStorage; settings: Settings; extractor: Extractor; embedder: ChunkEmbedder \| None; store_vectors: VectorWriter \| None; evaluations: 'EvaluationHooks \| None'` |  |
| ↳ `Pipeline.chunking_config` | method | 90 | `() -> chunking.ChunkingConfig` |  |
| `EvaluationHooks` | class (—) | 97 | `recover: Callable[[Session], int]; claim: Callable[[Session], uuid.UUID \| None]; execute: Callable[[uuid.UUID], None]` |  |
| `_now` | function | 103 | `() -> datetime` |  |
| `recover_stale_jobs` | function | 110 | `(session: Session, settings: Settings) -> int` | Re-queue (or fail) running jobs whose worker stopped heart-beating. |
| `claim_next_job` | function | 137 | `(session: Session) -> uuid.UUID \| None` |  |
| `beat` | function | 161 | `(session: Session) -> None` | Record that this worker process is alive (shown in /health/ready). |
| `_set_stage` | function | 176 | `(pipeline: Pipeline, job_id: uuid.UUID, stage: JobStage) -> None` |  |
| `_GoneError` | class (Exception) | 186 |  | The document (and its job) was deleted while processing; stop quietly. |
| `_fail` | function | 190 | `(pipeline: Pipeline, job_id: uuid.UUID, error: IngestionError) -> None` |  |
| `process_job` | function | 230 | `(pipeline: Pipeline, job_id: uuid.UUID) -> None` |  |
| `_complete` | function | 297 | `(pipeline: Pipeline, job_id: uuid.UUID, doc_id: uuid.UUID, workspace_id: uuid.UUID, extraction: Extraction, chunks: list[chunking.Chunk], embedded: EmbeddedChunks \| None) -> None` |  |
| `run` | function | 369 | `(pipeline: Pipeline, stop: threading.Event, *, once: bool = False) -> int` | Process jobs until `stop` is set (or the queue is empty when `once`). Returns jobs run. |
| `build_pipeline` | function | 396 | `(settings: Settings \| None = None) -> Pipeline` |  |
| `attach_evaluations` | function | 411 | `(pipeline: Pipeline) -> None` |  |
| `main` | function | 428 | `() -> None` |  |

## Frontend

`client` = the file starts with `"use client"` (runs in the browser). Others are server
components or plain modules. Pages under `src/app/` are thin server components that render
one client view each.

#### `apps/web/src/app/activity/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 5 |  |
| `ActivityPage` | function | 8 | `()` |

#### `apps/web/src/app/ask/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 5 |  |
| `AskPage` | function | 8 | `()` |

#### `apps/web/src/app/evaluation/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 5 |  |
| `EvaluationPage` | function | 8 | `()` |

#### `apps/web/src/app/help/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 5 |  |
| `HelpPage` | function | 7 | `()` |

#### `apps/web/src/app/layout.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 12 |  |
| `RootLayout` | function | 17 | `( …)` |

#### `apps/web/src/app/library/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 5 |  |
| `LibraryPage` | function | 8 | `()` |

#### `apps/web/src/app/not-found.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `NotFound` | function | 7 | `()` |

#### `apps/web/src/app/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `OverviewPage` | function | 10 | `()` |

#### `apps/web/src/app/settings/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 5 |  |
| `SettingsPage` | function | 8 | `()` |

#### `apps/web/src/app/sql/page.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `metadata` | const | 5 |  |
| `SqlPage` | function | 8 | `()` |

#### `apps/web/src/components/activity/activity-view.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `ActivityView` | function | 42 | `()` |

#### `apps/web/src/components/ask/answer-text.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `CitationChip` | function | 15 | `( …)` |
| `AnswerText` | function | 70 | `( …)` |

#### `apps/web/src/components/ask/ask-view.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `AskView` | function | 364 | `()` |

#### `apps/web/src/components/ask/source-drawer.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `SourceDrawer` | function | 17 | `( …)` |

#### `apps/web/src/components/brand/logo.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `LogoMark` | function | 4 | `( …)` |
| `Wordmark` | function | 26 | `( …)` |

#### `apps/web/src/components/evaluation/case-inspector.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `CaseInspector` | function | 21 | `( …)` |

#### `apps/web/src/components/evaluation/evaluation-view.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `METRICS` | const | 57 |  |
| `EvaluationView` | function | 429 | `()` |

#### `apps/web/src/components/help/help-view.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `HelpView` | function | 55 | `()` |

#### `apps/web/src/components/library/delete-document-dialog.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `DeleteDocumentDialog` | function | 19 | `( …)` |

#### `apps/web/src/components/library/document-drawer.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `locationLabel` | function | 37 | `(c …)` |
| `DocumentDrawer` | function | 67 | `( …)` |

#### `apps/web/src/components/library/document-status.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `DocumentStatusBadge` | function | 14 | `( …)` |
| `documentStatusLabel` | function | 19 | `(status: DocumentStatus): string` |

#### `apps/web/src/components/library/documents-table.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `DocumentsTable` | function | 61 | `( …)` |

#### `apps/web/src/components/library/library-view.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `PAGE_SIZE` | const | 32 |  |
| `PROGRESS_POLL_MS` | const | 34 |  |
| `LibraryView` | function | 70 | `()` |

#### `apps/web/src/components/library/upload-dropzone.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `UploadDropzone` | function | 15 | `( …)` |

#### `apps/web/src/components/library/upload-queue.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `UploadQueue` | function | 76 | `( …)` |

#### `apps/web/src/components/library/use-upload-queue.ts` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `UploadState` | type | 16 |  |
| `UploadItem` | interface | 18 |  |
| `useUploadQueue` | function | 41 | `( …)` |

#### `apps/web/src/components/overview/current-date.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `CurrentDate` | function | 20 | `()` |

#### `apps/web/src/components/overview/overview-dashboard.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `OverviewDashboard` | function | 28 | `()` |

#### `apps/web/src/components/overview/workspace-summary.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `WorkspaceSummary` | function | 126 | `()` |

#### `apps/web/src/components/settings/settings-view.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `SettingsView` | function | 105 | `()` |

#### `apps/web/src/components/shell/app-shell.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `AppShell` | function | 48 | `( …)` |

#### `apps/web/src/components/shell/nav-items.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `NavItem` | interface | 13 |  |
| `PRIMARY_NAV` | const | 25 |  |
| `SECONDARY_NAV` | const | 33 |  |
| `pageTitle` | function | 41 | `(pathname: string): string` |

#### `apps/web/src/components/shell/sidebar-nav.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `SidebarNav` | function | 66 | `( …)` |

#### `apps/web/src/components/shell/workspace-name.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `WorkspaceName` | function | 8 | `()` |

#### `apps/web/src/components/sql/sql-parts.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `formatSql` | function | 49 | `(sql: string): string` |
| `SqlCodeBlock` | function | 59 | `( …)` |
| `ClarificationPanel` | function | 100 | `( …)` |
| `ResultsTable` | function | 204 | `( …)` |
| `SchemaBrowser` | function | 264 | `( …)` |

#### `apps/web/src/components/sql/sql-view.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `SqlView` | function | 150 | `()` |

#### `apps/web/src/components/system-status/readiness-panel.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `ReadinessPanel` | function | 59 | `()` |

#### `apps/web/src/components/system-status/system-status-provider.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `SystemStatus` | type | 8 |  |
| `SystemStatusProvider` | function | 23 | `( …)` |
| `useSystemStatus` | function | 83 | `(): SystemStatusContextValue` |
| `summarize` | function | 90 | `(status: SystemStatus)` |

#### `apps/web/src/components/ui/copy-command.tsx` (client)

| Export | Kind | Line | Signature |
|---|---|---|---|
| `CopyCommand` | function | 9 | `( …)` |

#### `apps/web/src/components/ui/status-badge.tsx`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `StatusTone` | type | 5 |  |
| `StatusBadge` | function | 20 | `( …)` |

#### `apps/web/src/lib/api/activity.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `ActivityEvent` | interface | 4 |  |
| `IngestionJobRow` | interface | 15 |  |
| `ActivitySummary` | interface | 28 |  |
| `EventCategory` | type | 48 |  |
| `fetchEvents` | async function | 60 | `(category: EventCategory, limit = 50, signal?: AbortSignal)` |
| `fetchJobs` | async function | 89 | `(status: "all" \| "failed" \| "active", signal?: AbortSignal)` |
| `fetchSummary` | async function | 117 | `(signal?: AbortSignal)` |
| `describeEvent` | function | 153 | `(e: ActivityEvent): string` |

#### `apps/web/src/lib/api/chat.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `RetrievalMode` | type | 4 |  |
| `Citation` | interface | 6 |  |
| `RetrievalTrace` | interface | 17 |  |
| `Answer` | interface | 26 |  |
| `ConversationSummary` | interface | 40 |  |
| `ChatMessage` | interface | 47 |  |
| `ConversationDetail` | interface | 61 |  |
| `parseCitation` | function | 65 | `(raw: unknown, p: string): Citation` |
| `parseAnswer` | function | 94 | `(raw: unknown): Answer` |
| `parseConversation` | function | 144 | `(raw: unknown): ConversationDetail` |
| `askQuestion` | async function | 152 | `( …)` |
| `fetchConversations` | async function | 177 | `(signal?: AbortSignal)` |
| `fetchConversation` | async function | 187 | `(id: string, signal?: AbortSignal)` |
| `renameConversation` | async function | 195 | `(id: string, title: string)` |
| `deleteConversation` | async function | 204 | `(id: string)` |
| `sendFeedback` | async function | 210 | `( …)` |
| `citationLocation` | function | 222 | `(c …)` |

#### `apps/web/src/lib/api/client.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `ApiError` | class | 7 |  |
| `toApiError` | function | 37 | `(status: number, body: unknown, requestId: string \| null): ApiError` |
| `invalidResponse` | function | 59 | `(status: number, requestId: string \| null): ApiError` |
| `ApiResponse` | interface | 68 |  |
| `RequestOptions` | interface | 74 |  |
| `requestJson` | async function | 84 | `<T>( …)` |
| `getJson` | function | 131 | `<T>( …)` |

#### `apps/web/src/lib/api/documents.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `DOCUMENT_STATUSES` | const | 4 |  |
| `DocumentStatus` | type | 12 |  |
| `FileType` | type | 18 |  |
| `DuplicateAction` | type | 20 |  |
| `IngestionJob` | interface | 22 |  |
| `LibraryDocument` | interface | 31 |  |
| `DocumentPage` | interface | 51 |  |
| `UploadPolicy` | interface | 58 |  |
| `UploadResult` | interface | 63 |  |
| `parseDocument` | function | 81 | `(raw: unknown, path = "document"): LibraryDocument` |
| `parseDocumentPage` | function | 110 | `(raw: unknown): DocumentPage` |
| `parseUploadPolicy` | function | 120 | `(raw: unknown): UploadPolicy` |
| `parseUploadResult` | function | 138 | `(raw: unknown): UploadResult` |
| `duplicateOf` | function | 147 | `(error: ApiError): LibraryDocument \| null` |
| `fetchDocuments` | async function | 156 | `( …)` |
| `fetchUploadPolicy` | async function | 165 | `(signal?: AbortSignal)` |
| `retryDocument` | async function | 169 | `(id: string)` |
| `fetchDocument` | async function | 177 | `(id: string, signal?: AbortSignal)` |
| `ChunkStrategy` | type | 183 |  |
| `DocumentChunk` | interface | 185 |  |
| `ChunkPage` | interface | 195 |  |
| `parseChunkPage` | function | 200 | `(raw: unknown): ChunkPage` |
| `fetchChunks` | async function | 219 | `( …)` |
| `ExtractionPreview` | interface | 232 |  |
| `parseExtraction` | function | 242 | `(raw: unknown): ExtractionPreview` |
| `fetchExtraction` | async function | 258 | `(id: string, signal?: AbortSignal)` |
| `IN_PROGRESS` | const | 269 |  |
| `deleteDocument` | async function | 276 | `(id: string)` |
| `extensionOf` | function | 283 | `(name: string): string` |
| `precheckFile` | function | 289 | `(file: File, policy: UploadPolicy): string \| null` |
| `formatBytes` | function | 301 | `(bytes: number): string` |
| `uploadDocument` | function | 317 | `( …)` |

#### `apps/web/src/lib/api/evaluation.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `Dataset` | interface | 4 |  |
| `RunStatus` | type | 16 |  |
| `Aggregate` | interface | 18 |  |
| `Run` | interface | 40 |  |
| `RetrievedPassage` | interface | 56 |  |
| `CaseResult` | interface | 68 |  |
| `RunDetail` | interface | 85 |  |
| `RunConfig` | interface | 89 |  |
| `fetchDatasets` | async function | 159 | `(signal?: AbortSignal)` |
| `createDataset` | async function | 169 | `(name: string, version: string)` |
| `loadSample` | async function | 178 | `()` |
| `importCases` | async function | 196 | `(datasetId: string, file: File)` |
| `fetchRuns` | async function | 221 | `(datasetId: string \| null, signal?: AbortSignal)` |
| `fetchRun` | async function | 232 | `(id: string, signal?: AbortSignal)` |
| `startRun` | async function | 248 | `(datasetId: string, config: RunConfig)` |
| `deleteRun` | async function | 257 | `(id: string)` |
| `exportUrl` | function | 263 | `(id: string, format: "json" \| "csv")` |

#### `apps/web/src/lib/api/health.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `CheckState` | type | 3 |  |
| `ReadyStatus` | type | 4 |  |
| `DependencyCheck` | interface | 6 |  |
| `ReadyResponse` | interface | 15 |  |
| `parseReadyResponse` | function | 28 | `(raw: unknown): ReadyResponse` |
| `fetchReadiness` | function | 52 | `(signal?: AbortSignal)` |
| `CHECK_LABELS` | const | 62 |  |
| `CHECK_HINTS` | const | 73 |  |

#### `apps/web/src/lib/api/settings.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `InstalledModel` | interface | 4 |  |
| `ModelSettings` | interface | 14 |  |
| `ValidationCheck` | interface | 25 |  |
| `ValidationResult` | interface | 32 |  |
| `parseModelSettings` | function | 39 | `(raw: unknown): ModelSettings` |
| `parseValidation` | function | 87 | `(raw: unknown): ValidationResult` |
| `Selection` | interface | 105 |  |
| `fetchModelSettings` | async function | 115 | `(signal?: AbortSignal)` |
| `validateModels` | async function | 119 | `(selection: Selection, probeGeneration: boolean)` |
| `saveModels` | async function | 130 | `(selection: Selection, rerankerEnabled: boolean)` |
| `reindexAll` | async function | 150 | `()` |

#### `apps/web/src/lib/api/sql.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `SqlConnection` | interface | 4 |  |
| `SqlColumn` | interface | 15 |  |
| `SqlTable` | interface | 22 |  |
| `GlossaryOption` | interface | 29 |  |
| `GlossaryTerm` | interface | 35 |  |
| `SchemaInfo` | interface | 43 |  |
| `SqlStatus` | type | 50 |  |
| `SqlAnswer` | interface | 53 |  |
| `Choice` | interface | 79 |  |
| `parseSchema` | function | 112 | `(raw: unknown): SchemaInfo` |
| `parseAnswer` | function | 147 | `(raw: unknown): SqlAnswer` |
| `fetchConnections` | async function | 183 | `(signal?: AbortSignal)` |
| `fetchSchema` | async function | 194 | `(id: string, signal?: AbortSignal)` |
| `askSql` | async function | 203 | `( …)` |
| `addConnection` | async function | 227 | `(body …)` |
| `removeConnection` | async function | 245 | `(id: string)` |

#### `apps/web/src/lib/api/validate.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `Obj` | type | 6 |  |
| `fail` | function | 8 | `(path: string): never` |
| `obj` | function | 12 | `(raw: unknown, path: string): Obj` |
| `str` | function | 17 | `(o: Obj, key: string, path: string): string` |
| `int` | function | 23 | `(o: Obj, key: string, path: string): number` |
| `bool` | function | 29 | `(o: Obj, key: string, path: string): boolean` |
| `nullableStr` | function | 35 | `(o: Obj, key: string, path: string): string \| null` |
| `nullableInt` | function | 39 | `(o: Obj, key: string, path: string): number \| null` |
| `oneOf` | function | 43 | `<T extends string>( …)` |
| `arr` | function | 54 | `<T>(o: Obj, key: string, path: string, item: (raw: unknown, p: string) => T)` |

#### `apps/web/src/lib/api/workspaces.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `Workspace` | interface | 4 |  |
| `WORKSPACE_NAME_MAX` | const | 10 |  |
| `parseWorkspace` | function | 12 | `(raw: unknown): Workspace` |
| `fetchCurrentWorkspace` | async function | 21 | `(signal?: AbortSignal)` |
| `renameWorkspace` | async function | 25 | `(id: string, name: string)` |

#### `apps/web/src/test/fixtures.ts`

| Export | Kind | Line | Signature |
|---|---|---|---|
| `RAW_DOC` | const | 2 |  |
| `RAW_POLICY` | const | 32 |  |

