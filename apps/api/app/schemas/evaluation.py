"""Evaluation Lab API contracts (TRD §8)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.evaluation.runner import RunConfigIn


class DatasetIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(default="v1", min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=2000)


class DatasetOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: str | None
    created_at: datetime
    cases: int
    dev_cases: int
    test_cases: int
    runs: int
    # Documents named in evidence that aren't ready in the workspace (results would be zero).
    missing_documents: list[str]


class CaseOut(BaseModel):
    id: uuid.UUID
    external_id: str
    split: str
    question: str
    reference_answer: str | None
    answerable: bool
    expected_evidence: list[dict[str, Any]]
    tags: list[str]


class DatasetDetail(DatasetOut):
    case_list: list[CaseOut]


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportSummary(BaseModel):
    imported: int
    errors: list[ImportRowError]


class SampleLoaded(BaseModel):
    dataset_id: uuid.UUID
    documents_queued: int
    documents_existing: int


class RunIn(BaseModel):
    dataset_id: uuid.UUID
    config: RunConfigIn = Field(default_factory=RunConfigIn)


class RunOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    label: str
    strategy: str
    model_id: str | None
    status: str
    progress: int
    total: int
    config: dict[str, Any]
    aggregate_metrics: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ResultOut(BaseModel):
    case_id: uuid.UUID
    external_id: str
    split: str
    question: str
    reference_answer: str | None
    answerable: bool
    expected_evidence: list[dict[str, Any]]
    tags: list[str]
    retrieved: list[dict[str, Any]]
    answer: str | None
    metrics: dict[str, Any]
    failure_category: str | None
    latency_ms: int | None
    error: str | None


class RunDetail(RunOut):
    results: list[ResultOut]
