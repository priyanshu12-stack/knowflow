"""One process-wide cap on concurrent local generations (TRD §11 DoS, §12).

Both Ask KnowFlow and the SQL Analyst generate with the same CPU-bound model, so they share one
gate. While a generation holds it, Ollama can be too busy to answer the 3-second readiness probe;
`busy()` lets the health check say "busy" instead of wrongly reporting the runtime as down.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import Settings
from app.core.errors import AppError

_lock = threading.Lock()
_gate: threading.BoundedSemaphore | None = None
_active = 0


def _semaphore(settings: Settings) -> threading.BoundedSemaphore:
    global _gate
    with _lock:
        if _gate is None:
            _gate = threading.BoundedSemaphore(settings.max_concurrent_generations)
        return _gate


@contextmanager
def generation_slot(settings: Settings) -> Iterator[None]:
    global _active
    gate = _semaphore(settings)
    if not gate.acquire(timeout=settings.generation_queue_wait_seconds):
        raise AppError(
            "generation_busy",
            "Another answer is being generated on this machine. Try again in a moment.",
            429,
        )
    with _lock:
        _active += 1
    try:
        yield
    finally:
        with _lock:
            _active -= 1
        gate.release()


def busy() -> bool:
    return _active > 0
