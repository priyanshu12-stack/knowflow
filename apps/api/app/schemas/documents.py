"""Document and ingestion-job API contracts (TRD §8)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.documents.status import DocumentStatus, JobStage, JobStatus
from app.modules.documents.validation import FileType

DuplicateAction = Literal["skip", "reindex", "new_version"]
UploadOutcome = Literal["created", "new_version", "reindexed", "skipped"]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: JobStatus
    stage: JobStage | None
    attempts: int
    error_code: str | None
    error_message_safe: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class SafeError(BaseModel):
    code: str
    message: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    original_name: str
    file_type: FileType
    mime_type: str
    size_bytes: int
    sha256: str
    version: int
    status: DocumentStatus
    page_count: int | None
    # Chunks arrive with the ingestion pipeline (M2); null means "not chunked yet", not zero.
    chunk_count: int | None
    last_error: SafeError | None
    latest_job: JobOut | None
    created_at: datetime
    updated_at: datetime


class UploadResult(BaseModel):
    """`202` for created / new_version / reindexed, `200` for skipped (nothing new queued)."""

    outcome: UploadOutcome
    document_id: uuid.UUID
    job_id: uuid.UUID | None
    status: DocumentStatus
    document: DocumentOut


class SupportedFormatOut(BaseModel):
    file_type: FileType
    label: str
    mime_type: str
    extensions: list[str]


class UploadPolicyOut(BaseModel):
    max_bytes: int
    formats: list[SupportedFormatOut]
