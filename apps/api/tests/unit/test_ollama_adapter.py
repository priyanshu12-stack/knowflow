"""TRD §4.3: model calls are bounded, validated and fail with actionable, safe messages."""

import math

import httpx
import pytest

from app.modules.models.interfaces import ChatMessage, ModelError
from app.modules.models.ollama import OllamaClient, parse_json_object, validate_vectors
from app.modules.models.registry import task_prefixes
from tests.fake_ollama import DIM, FakeOllama


def client_for(fake: FakeOllama) -> OllamaClient:
    return OllamaClient("http://ollama.test", timeout=5, transport=fake.transport())


def test_embed_returns_one_validated_vector_per_text() -> None:
    fake = FakeOllama()
    vectors = client_for(fake).embed("nomic-embed-text:v1.5", ["a b", "c"])
    assert len(vectors) == 2
    assert validate_vectors(vectors, DIM) == DIM
    assert fake.requests[-1][1]["truncate"] is True


def test_missing_model_names_the_pull_command() -> None:
    with pytest.raises(ModelError) as err:
        client_for(FakeOllama(models=())).embed("nomic-embed-text:v1.5", ["x"])
    assert err.value.code == "model_missing"
    assert "ollama pull nomic-embed-text:v1.5" in err.value.message
    assert err.value.retryable


def test_unreachable_runtime_is_retryable() -> None:
    fake = FakeOllama()
    fake.down = True
    with pytest.raises(ModelError) as err:
        client_for(fake).version()
    assert err.value.code == "ollama_unavailable"
    assert err.value.retryable


def test_timeout_is_reported_as_model_timeout() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = OllamaClient("http://ollama.test", timeout=1, transport=httpx.MockTransport(slow))
    with pytest.raises(ModelError) as err:
        client.embed("m", ["x"])
    assert err.value.code == "model_timeout"


def test_vector_validation_rejects_wrong_dimension_and_non_finite_values() -> None:
    with pytest.raises(ModelError, match="Re-index"):
        validate_vectors([[0.1, 0.2]], 3)
    with pytest.raises(ModelError):
        validate_vectors([[0.1, math.nan]], None)
    with pytest.raises(ModelError):
        validate_vectors([[0.1, 0.2], [0.3]], None)


def test_chat_sends_schema_and_low_temperature_without_thinking() -> None:
    fake = FakeOllama()
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    result = client_for(fake).chat(
        "qwen3:4b", [ChatMessage("user", "hi")], temperature=0.1, json_schema=schema
    )
    sent = fake.requests[-1][1]
    assert sent["format"] == schema
    assert sent["options"]["temperature"] == 0.1
    assert sent["think"] is False
    assert sent["stream"] is False
    assert parse_json_object(result.content) == {"ok": True}
    assert result.completion_tokens == 5


def test_structured_output_must_be_a_json_object() -> None:
    with pytest.raises(ModelError):
        parse_json_object("not json")
    with pytest.raises(ModelError):
        parse_json_object("[1, 2]")


def test_nomic_uses_task_prefixes_other_models_do_not() -> None:
    assert task_prefixes("nomic-embed-text:v1.5") == ("search_document: ", "search_query: ")
    assert task_prefixes("mxbai-embed-large") == ("", "")


def test_server_errors_are_retried_once_then_explained() -> None:
    calls = 0

    def flaky(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, json={"error": "loading model"})
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0]]})

    client = OllamaClient("http://o.test", timeout=1, transport=httpx.MockTransport(flaky))
    client.retry_delay_seconds = 0
    assert client.embed("m", ["x"]) == [[1.0, 0.0]]

    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "model requires more system memory"})

    client = OllamaClient("http://o.test", timeout=1, transport=httpx.MockTransport(broken))
    client.retry_delay_seconds = 0
    with pytest.raises(ModelError, match="more system memory") as err:
        client.embed("m", ["x"])
    assert err.value.retryable
