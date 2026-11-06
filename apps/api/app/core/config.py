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

    # Uploaded files (TRD §6.1, §11): a non-public directory, never served statically.
    storage_root: Path = REPO_ROOT / "data" / "storage"
    upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)

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
