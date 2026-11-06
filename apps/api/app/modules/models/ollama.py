"""Ollama adapters: the only model provider KnowFlow ships (TRD §4, ADR-001, ADR-007).

Business logic depends on the `EmbeddingModel` / `ChatModel` protocols in `interfaces.py`, never
on this module directly. Every call is bounded by a timeout, and every response is validated:
vectors must have the expected dimension and finite values, and structured chat output is parsed
with Pydantic by the caller (TRD §4.3). Errors are raised as `ModelError` with a user-safe message.
"""

import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.modules.models.interfaces import ChatMessage, ChatResult, ModelError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstalledModel:
    name: str
    digest: str
    size_bytes: int
    family: str | None
    parameter_size: str | None
    quantization: str | None


class OllamaClient:
    def __init__(
        self, base_url: str, *, timeout: float, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        # `transport` lets tests substitute a fake Ollama without a network.
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def _post(self, path: str, payload: dict[str, Any], *, timeout: float | None = None) -> Any:
        response = self._send(path, payload, timeout)
        if response.status_code >= 500:
            # Usually transient on small machines (a model loading while another is resident).
            time.sleep(self.retry_delay_seconds)
            response = self._send(path, payload, timeout)
        if response.status_code == 404:
            model = payload.get("model", "the model")
            raise ModelError(
                "model_missing",
                f"{model} is not installed. Run: ollama pull {model}",
                retryable=True,
            )
        if response.status_code >= 400:
            raise ModelError(
                "model_error",
                f"The local model returned an error (HTTP {response.status_code})"
                f"{_runtime_reason(response)}.",
                retryable=response.status_code >= 500,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ModelError("model_bad_response", "The model returned invalid JSON.") from exc

    retry_delay_seconds = 2.0

    def _send(self, path: str, payload: dict[str, Any], timeout: float | None) -> httpx.Response:
        try:
            return self._client.post(
                path, json=payload, timeout=timeout or httpx.USE_CLIENT_DEFAULT
            )
        except httpx.TimeoutException as exc:
            raise ModelError(
                "model_timeout", "The local model took too long to respond.", retryable=True
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelError(
                "ollama_unavailable",
                "Cannot reach the local Ollama runtime. Start it with: ollama serve",
                retryable=True,
            ) from exc

    def version(self) -> str:
        try:
            return str(self._client.get("/api/version").raise_for_status().json()["version"])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ModelError(
                "ollama_unavailable", "Cannot reach the local Ollama runtime.", retryable=True
            ) from exc

    def list_models(self) -> list[InstalledModel]:
        try:
            data = self._client.get("/api/tags").raise_for_status().json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelError(
                "ollama_unavailable", "Cannot reach the local Ollama runtime.", retryable=True
            ) from exc
        models = []
        for m in data.get("models", []):
            details = m.get("details") or {}
            models.append(
                InstalledModel(
                    name=str(m.get("name", "")),
                    digest=str(m.get("digest", "")),
                    size_bytes=int(m.get("size", 0)),
                    family=details.get("family"),
                    parameter_size=details.get("parameter_size"),
                    quantization=details.get("quantization_level"),
                )
            )
        return models

    def show(self, model: str) -> dict[str, Any]:
        data = self._post("/api/show", {"model": model})
        return data if isinstance(data, dict) else {}

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        data = self._post("/api/embed", {"model": model, "input": texts, "truncate": True})
        vectors = data.get("embeddings") if isinstance(data, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ModelError("model_bad_response", "The embedding model returned no vectors.")
        return vectors

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float,
        json_schema: dict[str, Any] | None = None,
        num_ctx: int = 4096,
        num_predict: int = 768,
        timeout: float | None = None,
        think: bool = False,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            # qwen3 is a hybrid reasoning model; structured answers don't need the thinking trace.
            "think": think,
            "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict},
        }
        if json_schema is not None:
            payload["format"] = json_schema
        started = time.perf_counter()
        data = self._post("/api/chat", payload, timeout=timeout)
        content = (data.get("message") or {}).get("content") if isinstance(data, dict) else None
        if not isinstance(content, str):
            raise ModelError("model_bad_response", "The generation model returned no message.")
        return ChatResult(
            content=content,
            model=model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            done_reason=data.get("done_reason"),
        )


def validate_vectors(vectors: list[list[float]], dimension: int | None) -> int:
    """Every vector has the same (expected) dimension and only finite values (TRD §6.1)."""
    if not vectors:
        raise ModelError("model_bad_response", "The embedding model returned no vectors.")
    dim = len(vectors[0])
    if dimension is not None and dim != dimension:
        raise ModelError(
            "embedding_dimension_changed",
            f"The embedding model returned {dim} dimensions; the index expects {dimension}. "
            "Re-index all documents after changing embedding models.",
        )
    for v in vectors:
        if len(v) != dim or not all(isinstance(x, int | float) and math.isfinite(x) for x in v):
            raise ModelError("model_bad_response", "The embedding model returned invalid vectors.")
    return dim


def parse_json_object(content: str) -> dict[str, Any]:
    """Structured output is untrusted until parsed and validated by the caller."""
    try:
        value = json.loads(content)
    except ValueError as exc:
        raise ModelError("model_invalid_output", "The model returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise ModelError("model_invalid_output", "The model returned JSON of the wrong shape.")
    return value


def _runtime_reason(response: httpx.Response) -> str:
    """Ollama's own error text (e.g. "model requires more system memory"), shortened."""
    try:
        reason = response.json().get("error")
    except ValueError:
        return ""
    if not isinstance(reason, str) or not reason.strip():
        return ""
    return f": {reason.strip()[:200]}"
