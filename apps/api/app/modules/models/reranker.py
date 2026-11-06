"""Optional local CrossEncoder reranker (TRD §4.2, ADR-004). Off by default.

`sentence-transformers` and the model weights are optional (`pip install -e "apps/api[reranker]"`).
The model is loaded lazily, once per process, and only when a request or evaluation run asks for
reranking. Without it, basic and hybrid retrieval are unaffected.
"""

import importlib.util
import logging
import threading
from typing import Any, Protocol

from app.modules.models.interfaces import ModelError
from app.modules.retrieval.types import Candidate

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    name: str

    def score(self, query: str, passages: list[str]) -> list[float]: ...


def available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        self.name = model_name
        self._model: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                if not available():
                    raise ModelError(
                        "reranker_unavailable",
                        'The reranker is not installed. Run: pip install -e "apps/api[reranker]"',
                    )
                from sentence_transformers import CrossEncoder

                logger.info("reranker_loading", extra={"model": self.name})
                self._model = CrossEncoder(self.name, device="cpu")
        return self._model

    def score(self, query: str, passages: list[str]) -> list[float]:
        model = self._load()
        return [float(s) for s in model.predict([(query, p) for p in passages])]


_instances: dict[str, CrossEncoderReranker] = {}


def get_reranker(model_name: str) -> CrossEncoderReranker:
    if model_name not in _instances:
        _instances[model_name] = CrossEncoderReranker(model_name)
    return _instances[model_name]


def rerank(reranker: Reranker, query: str, candidates: list[Candidate]) -> list[Candidate]:
    if not candidates:
        return []
    scores = reranker.score(query, [c.text for c in candidates])
    ordered = sorted(zip(candidates, scores, strict=True), key=lambda x: -x[1])
    out = []
    for rank, (c, s) in enumerate(ordered, start=1):
        c.score = s
        c.ranks["rerank"] = rank
        out.append(c)
    return out
