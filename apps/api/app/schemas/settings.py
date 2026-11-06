"""Models & Settings API contracts (TRD §8, PRD §5.6). No provider keys exist by design."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InstalledModelOut(BaseModel):
    name: str
    digest: str
    size_bytes: int
    family: str | None
    parameter_size: str | None
    quantization: str | None
    kind: Literal["generation", "embedding", "unknown"]


class EmbeddingVersionOut(BaseModel):
    model: str
    digest: str
    dimension: int
    created_at: datetime


class RerankerOut(BaseModel):
    enabled: bool
    available: bool
    model: str
    note: str


class RuntimeOut(BaseModel):
    reachable: bool
    version: str | None
    base_url: str
    error: str | None = None


class ModelSettingsOut(BaseModel):
    runtime: RuntimeOut
    installed: list[InstalledModelOut]
    generation_model: str
    embedding_model: str
    reranker: RerankerOut
    active_embedding: EmbeddingVersionOut | None
    documents_needing_reindex: int
    setup_commands: list[str]


ModelName = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:/-]+$")


class ModelSelection(BaseModel):
    generation_model: str = ModelName
    embedding_model: str = ModelName


class ValidateRequest(ModelSelection):
    # The generation probe loads the LLM, which can take a while on CPU; allow skipping it.
    probe_generation: bool = True


class ValidationCheck(BaseModel):
    name: str
    state: Literal["ok", "failed", "skipped"]
    detail: str
    latency_ms: int | None = None


class ValidateResponse(BaseModel):
    ok: bool
    checks: list[ValidationCheck]
    embedding_dimension: int | None
    embedding_model_changed: bool


class SaveRequest(ModelSelection):
    reranker_enabled: bool = False


class SaveResponse(BaseModel):
    settings: ModelSettingsOut
    reembed_required: bool


class ReindexResponse(BaseModel):
    queued: int
