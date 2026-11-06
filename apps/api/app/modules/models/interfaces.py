"""Provider-agnostic model interfaces (TRD §4). v1 ships Ollama implementations only."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol


class ModelError(Exception):
    """A user-safe model failure. `retryable` marks transient problems (timeouts, not running)."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    done_reason: str | None = None


class EmbeddingModel(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class ChatModel(Protocol):
    name: str

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        json_schema: dict[str, Any] | None = None,
        num_predict: int = 768,
    ) -> ChatResult: ...
