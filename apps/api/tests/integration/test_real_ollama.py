"""Smoke tests against the real local runtime (KNOWFLOW_RUN_OLLAMA=1). Not run in CI."""

import pytest

from app.core.config import get_settings
from app.modules.models.interfaces import ChatMessage
from app.modules.models.ollama import OllamaClient, parse_json_object, validate_vectors
from app.modules.models.registry import probe_dimension

pytestmark = pytest.mark.ollama


@pytest.fixture(scope="module")
def client() -> OllamaClient:
    return OllamaClient(get_settings().ollama_base_url, timeout=300)


def test_embedding_model_dimension_is_measured(client: OllamaClient) -> None:
    model = get_settings().ollama_embedding_model
    dim = probe_dimension(client, model)
    assert dim > 0
    vectors = client.embed(model, ["search_document: KnowFlow", "search_query: KnowFlow"])
    assert validate_vectors(vectors, dim) == dim


def test_generation_model_returns_schema_valid_json(client: OllamaClient) -> None:
    result = client.chat(
        get_settings().ollama_generation_model,
        [ChatMessage("user", 'Return {"ok": true} as JSON.')],
        temperature=0,
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        num_ctx=1024,
        num_predict=32,
    )
    assert parse_json_object(result.content)["ok"] is True
