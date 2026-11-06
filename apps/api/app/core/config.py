"""Application configuration, validated once at startup (TRD §15: no hardcoded secrets)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """All runtime configuration. Values come from the environment or the repo-root `.env`."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # PostgreSQL: the same variables drive Docker Compose and scripts/db.ps1.
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_user: str = "knowflow"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "knowflow"

    # Local model runtime (TRD §4). Tags are pinned; models are never pulled by the app.
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_generation_model: str = "qwen3:4b"
    ollama_embedding_model: str = "nomic-embed-text:v1.5"

    health_check_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    # Model calls (TRD §4.3): bounded timeouts and batch sizes; CPU inference can be slow.
    embedding_batch_size: int = Field(default=16, ge=1, le=256)
    embedding_timeout_seconds: float = Field(default=120, gt=0, le=1800)
    generation_timeout_seconds: float = Field(default=300, gt=0, le=3600)
    generation_num_ctx: int = Field(default=4096, ge=1024, le=131_072)
    # RAG (TRD §6.2). min score is a provisional cosine threshold for dense retrieval; it is
    # re-calibrated on the evaluation set (M5) and can be disabled with a negative value.
    rag_top_k: int = Field(default=6, ge=1, le=20)
    rag_candidates: int = Field(default=20, ge=1, le=100)
    rag_context_chars: int = Field(default=6000, ge=500, le=60_000)
    rag_min_dense_score: float = Field(default=0.45, ge=-1, le=1)
    rag_temperature: float = Field(default=0.1, ge=0, le=1)
    # Local generation is CPU-bound: queue at most this many at once (TRD §11 DoS).
    max_concurrent_generations: int = Field(default=1, ge=1, le=8)
    generation_queue_wait_seconds: float = Field(default=10, ge=0, le=600)

    # Optional CPU-heavy second stage (TRD §4.2); off unless measured to help.
    enable_reranker: bool = False
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Uploaded files (TRD §6.1, §11): a non-public directory, never served statically.
    storage_root: Path = REPO_ROOT / "data" / "storage"
    upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)

    # Ingestion pipeline (TRD §6.1, §12): every long step is bounded.
    max_pdf_pages: int = Field(default=500, ge=1, le=5000)
    max_extracted_chars: int = Field(default=2_000_000, ge=1000, le=20_000_000)
    extraction_timeout_seconds: float = Field(default=120, gt=0, le=1800)
    chunk_size_chars: int = Field(default=1200, ge=200, le=8000)
    chunk_overlap_chars: int = Field(default=200, ge=0, le=2000)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    job_retry_base_seconds: float = Field(default=30, ge=0, le=3600)
    job_stale_seconds: float = Field(default=300, ge=10, le=86_400)
    worker_poll_seconds: float = Field(default=2.0, gt=0, le=60)

    @property
    def database_url(self) -> URL:
        """SQLAlchemy URL built from parts so the password is never string-formatted into logs."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value() or None,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
