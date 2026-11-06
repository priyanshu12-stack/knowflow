"""ORM models (TRD §7). Every content table is scoped by `workspace_id` (CON-08, SEC-03).

The schema itself is owned by Alembic migrations (`alembic/versions`); the app never calls
`create_all` (TRD §15). `tests/integration/test_migrations.py` fails if the two drift apart.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.documents.status import DOCUMENT_STATUSES, JOB_STAGES, JOB_STATUSES

FILE_TYPES = ("pdf", "docx", "txt", "md")
CHUNK_STRATEGIES = ("fixed", "recursive")
GRANULARITIES = ("page", "section", "document")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 80", name="name_length"),
        # At most one default workspace (local single-user mode, WSP-02).
        Index(
            "uq_workspaces_single_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(_in("status", DOCUMENT_STATUSES), name="status_valid"),
        CheckConstraint(_in("file_type", FILE_TYPES), name="file_type_valid"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="page_count_non_negative"),
        CheckConstraint(
            f"citation_granularity IS NULL OR {_in('citation_granularity', GRANULARITIES)}",
            name="granularity_valid",
        ),
        # Identical content may exist only as explicit versions (ING-12).
        UniqueConstraint("workspace_id", "sha256", "version"),
        Index("ix_documents_workspace_created", "workspace_id", "created_at"),
        Index("ix_documents_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    # Display only. Never used as a filesystem path (TRD §11).
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    page_count: Mapped[int | None] = mapped_column(Integer)
    # Set by the worker after extraction (M2). Granularity tells citations what they can point at.
    extracted_char_count: Mapped[int | None] = mapped_column(Integer)
    citation_granularity: Mapped[str | None] = mapped_column(String(10))

    jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="IngestionJob.created_at.desc()",
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(_in("status", JOB_STATUSES), name="status_valid"),
        CheckConstraint(f"stage IS NULL OR {_in('stage', JOB_STAGES)}", name="stage_valid"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        Index("ix_ingestion_jobs_document_created", "document_id", "created_at"),
        # Worker claim order (M2): oldest queued first.
        Index("ix_ingestion_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    stage: Mapped[str | None] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    # Plain-language, user-safe message. Never raw exception text or document content.
    error_message_safe: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Refreshed by the worker while it runs; a stale heartbeat means the worker died (TRD §12).
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[Document] = relationship(back_populates="jobs")


class DocumentSection(Base):
    """The normalized extracted text, kept for traceability and the extraction preview."""

    __tablename__ = "document_sections"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="page_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class Chunk(Base):
    """A retrievable passage (TRD §7). `search_tsv` is generated by PostgreSQL for FTS."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "strategy", "chunk_index"),
        CheckConstraint(_in("strategy", CHUNK_STRATEGIES), name="strategy_valid"),
        CheckConstraint("chunk_index >= 0", name="index_non_negative"),
        CheckConstraint("char_count > 0 AND token_count > 0", name="counts_positive"),
        CheckConstraint(
            "page_start IS NULL OR (page_start >= 1 AND page_end >= page_start)",
            name="page_range_valid",
        ),
        Index("ix_chunks_workspace_strategy", "workspace_id", "strategy"),
        Index("ix_chunks_search_tsv", "search_tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[str | None] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(section_path, '') || ' ' || text)", persisted=True
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkerHeartbeat(Base):
    """One row per worker process name; lets /health/ready say whether ingestion is running."""

    __tablename__ = "worker_heartbeats"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmbeddingVersion(Base):
    """One embedding space: model tag + digest + measured dimension (TRD §4.2, §7, ADR-002).

    Vectors from different versions are never compared. Changing the embedding model creates a
    new version; documents embedded with an older version must be re-indexed.
    """

    __tablename__ = "embedding_versions"
    __table_args__ = (
        UniqueConstraint("model", "digest", "dimension"),
        CheckConstraint("dimension BETWEEN 1 AND 16000", name="dimension_range"),
        Index(
            "uq_embedding_versions_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    digest: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    # Task prefixes used for this model (nomic: "search_document: " / "search_query: ").
    document_prefix: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    query_prefix: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChunkEmbedding(Base):
    """A chunk's vector in one embedding space. Untyped `vector` so dimensions can differ by
    version; exact (sequential) cosine search is the measured baseline (TRD §3)."""

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        Index("ix_chunk_embeddings_version_workspace", "embedding_version_id", "workspace_id"),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    embedding_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("embedding_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)


class ModelSettings(Base):
    """User-selected local models (PRD §5.6). One row; absent means "use .env defaults"."""

    __tablename__ = "model_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    generation_model: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(200), nullable=False)
    reranker_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Validation evidence captured when the settings were saved.
    validation: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("char_length(btrim(title)) BETWEEN 1 AND 120", name="title_length"),
        Index("ix_conversations_workspace_updated", "workspace_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )


class Message(Base):
    """One chat turn. Assistant messages carry citations and the retrieval trace (TRD §7)."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role_valid"),
        CheckConstraint("char_length(content) BETWEEN 1 AND 20000", name="content_size"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # abstained, retrieval trace, model, prompt_version, latency: no secrets, no prompt text.
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class MessageFeedback(Base):
    """Helpful / not helpful on an answer, kept for error analysis (PRD §5.3)."""

    __tablename__ = "message_feedback"
    __table_args__ = (
        CheckConstraint("rating IN ('helpful', 'not_helpful')", name="rating_valid"),
        CheckConstraint("reason IS NULL OR char_length(reason) <= 1000", name="reason_size"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvaluationDataset(Base):
    """A versioned gold set (TRD §7, §9). Cases are immutable once a run references them."""

    __tablename__ = "evaluation_datasets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", "version"),
        CheckConstraint("task_type IN ('retrieval_qa')", name="task_type_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    task_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="retrieval_qa"
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "external_id"),
        CheckConstraint("split IN ('dev', 'test')", name="split_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(80), nullable=False)
    split: Mapped[str] = mapped_column(String(10), nullable=False, server_default="dev")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str | None] = mapped_column(Text)
    answerable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # Stable matchers {document, quote?, page?} (ADR-000 G-9) and optional raw chunk ids.
    expected_evidence: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    expected_chunk_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    expected_sql: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')", name="status_valid"
        ),
        Index("ix_evaluation_runs_status_created", "status", "created_at"),
        Index("ix_evaluation_runs_dataset_created", "dataset_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    # Everything needed to reproduce the run: retrieval knobs, models + digests, prompt, machine.
    config: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    aggregate_metrics: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (UniqueConstraint("run_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluation_cases.id", ondelete="CASCADE"), nullable=False
    )
    retrieved_ids: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    answer: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    failure_category: Mapped[str | None] = mapped_column(String(40))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class SqlConnection(Base):
    """A read-only database the SQL Analyst may query (TRD §7). The secret is write-only:
    stored encrypted (Fernet) and never returned by the API (ADR-006, ADR-000 G-4)."""

    __tablename__ = "sql_connections"
    __table_args__ = (
        CheckConstraint("db_type IN ('postgresql')", name="db_type_valid"),
        UniqueConstraint("workspace_id", "display_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    db_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="postgresql")
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(63), nullable=False)
    username: Mapped[str] = mapped_column(String(63), nullable=False)
    encrypted_secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_schemas: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SqlGlossaryTerm(Base):
    """Business definitions shown to the user and the model (TRD §10). `ambiguous` terms carry
    2-4 options and always trigger a clarification until the user picks one."""

    __tablename__ = "sql_glossary_terms"
    __table_args__ = (
        UniqueConstraint("connection_id", "term"),
        CheckConstraint("kind IN ('definition', 'ambiguous')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sql_connections.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)
    synonyms: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    options: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )


class SqlQueryLog(Base):
    """Every SQL Analyst turn with its safety decision, for reproducibility (TRD §10). String
    literals in stored SQL are redacted; credentials are never stored here."""

    __tablename__ = "sql_queries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('clarification_required', 'executed', 'rejected', 'failed', 'unsupported')",
            name="status_valid",
        ),
        Index("ix_sql_queries_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sql_connections.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    clarification: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    sql_redacted: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    row_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
