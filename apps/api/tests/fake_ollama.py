"""An in-memory Ollama for tests (httpx MockTransport). No network, no model weights.

Embeddings are deterministic bag-of-words hashes, so texts that share words are close in cosine
space; that makes dense retrieval testable. Chat replies come from a queue of canned contents.
"""

import hashlib
import json
import math
from collections import deque
from typing import Any

import httpx

DIM = 16


def fake_vector(text: str, dim: int = DIM) -> list[float]:
    v = [0.0] * dim
    for raw in text.lower().split():
        word = raw.strip(".,:;!?()[]\"'")
        if not word or word in {"search_document", "search_query", "the", "a", "of", "is"}:
            continue
        h = int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16)
        v[h % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


class FakeOllama:
    def __init__(
        self,
        models: tuple[str, ...] = ("qwen3:4b", "nomic-embed-text:v1.5"),
        dim: int = DIM,
    ) -> None:
        self.models = list(models)
        self.dim = dim
        self.down = False
        self.chat_replies: deque[str] = deque()
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        body: dict[str, Any] = json.loads(request.content) if request.content else {}
        self.requests.append((path, body))
        if path == "/api/version":
            return httpx.Response(200, json={"version": "0.0-fake"})
        if path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": m,
                            "digest": hashlib.sha256(m.encode()).hexdigest(),
                            "size": 1000,
                            "details": {
                                "family": "nomic-bert" if "embed" in m else "qwen3",
                                "parameter_size": "1B",
                                "quantization_level": "Q4",
                            },
                        }
                        for m in self.models
                    ]
                },
            )
        model = body.get("model")
        if model not in self.models:
            return httpx.Response(404, json={"error": f"model '{model}' not found"})
        if path == "/api/embed":
            return httpx.Response(
                200, json={"embeddings": [fake_vector(t, self.dim) for t in body["input"]]}
            )
        if path == "/api/chat":
            content = self.chat_replies.popleft() if self.chat_replies else '{"ok": true}'
            return httpx.Response(
                200,
                json={
                    "message": {"role": "assistant", "content": content},
                    "prompt_eval_count": 10,
                    "eval_count": 5,
                    "done_reason": "stop",
                },
            )
        if path == "/api/show":
            return httpx.Response(200, json={"details": {}, "capabilities": []})
        return httpx.Response(404)
