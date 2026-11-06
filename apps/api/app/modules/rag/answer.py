"""Grounded answer generation (TRD §6.2): pack evidence, abstain on weak evidence, generate with
a JSON schema, then *verify* citations before anything reaches the user.

Citation policy (TRD §17 "only valid citations or explicitly abstains"):
- Inline markers [n] in the answer are the source of truth. Markers that point at no supplied
  source are removed. Remaining markers are renumbered 1..m in order of first use.
- A non-abstained answer with no valid citation is not shown as an answer: it becomes an
  abstention ("unsupported"), because nothing ties its claims to evidence.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.modules.models.interfaces import ChatMessage, ChatModel, ModelError
from app.modules.models.ollama import parse_json_object
from app.modules.rag.prompts import ANSWER_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.modules.retrieval.types import Candidate

AbstainReason = Literal["no_sources", "weak_evidence", "model_abstained", "unsupported"]


class ModelAnswer(BaseModel):
    answer: str = Field(max_length=8000)
    citations: list[int] = Field(default_factory=list, max_length=50)
    abstained: bool
    missing: str | None = Field(default=None, max_length=1000)


@dataclass
class Citation:
    number: int
    candidate: Candidate


@dataclass
class GroundedAnswer:
    text: str
    citations: list[Citation]
    abstained: bool
    abstain_reason: AbstainReason | None
    sources_considered: int
    sources_supplied: int
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    generation_ms: int | None = None
    tokens: dict[str, int | None] = field(default_factory=dict)


def pack_context(candidates: list[Candidate], max_chars: int) -> list[Candidate]:
    """Deduplicate overlapping passages and stay inside the context budget, keeping rank order."""
    packed: list[Candidate] = []
    used = 0
    for c in candidates:
        text = c.text.strip()
        if any(
            p.chunk_id == c.chunk_id
            or (p.document_id == c.document_id and (text in p.text or p.text in text))
            for p in packed
        ):
            continue
        if packed and used + len(text) > max_chars:
            break
        packed.append(c)
        used += len(text)
    return packed


_MARKER = re.compile(r"\[(\d{1,3})\]")


def verify_citations(text: str, listed: list[int], n_sources: int) -> tuple[str, list[int]]:
    """Drop invalid markers and renumber. Returns (text, original source numbers in new order)."""
    order: list[int] = []

    def keep(match: re.Match[str]) -> str:
        n = int(match.group(1))
        if not 1 <= n <= n_sources:
            return ""
        if n not in order:
            order.append(n)
        return f"[{order.index(n) + 1}]"

    cleaned = _MARKER.sub(keep, text)
    if not order:
        # The model listed citations but forgot inline markers: attach them at the end.
        valid = [n for n in dict.fromkeys(listed) if 1 <= n <= n_sources]
        if valid:
            order = valid
            cleaned = cleaned.rstrip() + " " + "".join(f"[{i + 1}]" for i in range(len(valid)))
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip(), order


ABSTAIN_TEXT = {
    "no_sources": "No supporting source found. None of the indexed documents matched this "
    "question. Try different wording, or upload a document that covers it.",
    "weak_evidence": "No supporting source found. The closest passages don't look relevant "
    "enough to answer from. Try a more specific question.",
    "unsupported": "I couldn't produce an answer that is backed by the retrieved passages, so "
    "none is shown. Try narrowing the question to one topic or document.",
}


def answer_question(
    question: str,
    candidates: list[Candidate],
    chat: ChatModel,
    *,
    max_context_chars: int,
    min_score: float | None,
    temperature: float,
) -> GroundedAnswer:
    if not candidates:
        return GroundedAnswer(ABSTAIN_TEXT["no_sources"], [], True, "no_sources", 0, 0)
    if min_score is not None and max(c.score for c in candidates) < min_score:
        return GroundedAnswer(
            ABSTAIN_TEXT["weak_evidence"], [], True, "weak_evidence", len(candidates), 0
        )

    sources = pack_context(candidates, max_context_chars)
    result = chat.complete(
        [
            ChatMessage("system", SYSTEM_PROMPT),
            ChatMessage("user", build_user_prompt(question, sources)),
        ],
        temperature=temperature,
        json_schema=ANSWER_SCHEMA,
        num_predict=700,
    )
    try:
        parsed = ModelAnswer.model_validate(parse_json_object(result.content))
    except ValidationError as exc:
        raise ModelError(
            "model_invalid_output",
            "The model's answer didn't match the expected format. Try asking again.",
            retryable=True,
        ) from exc
    except ModelError as exc:
        if result.done_reason == "length":
            raise ModelError(
                "model_output_truncated",
                "The answer was cut off before it finished. Try a narrower question.",
                retryable=True,
            ) from exc
        raise ModelError(
            "model_invalid_output",
            "The model's answer wasn't valid JSON. Try asking again.",
            retryable=True,
        ) from exc

    base = GroundedAnswer(
        text="",
        citations=[],
        abstained=False,
        abstain_reason=None,
        sources_considered=len(candidates),
        sources_supplied=len(sources),
        model=result.model,
        generation_ms=result.latency_ms,
        tokens={"prompt": result.prompt_tokens, "completion": result.completion_tokens},
    )
    if parsed.abstained:
        missing = (parsed.missing or parsed.answer).strip()
        base.text = "No supporting source found. " + (
            missing if missing else "The retrieved passages don't answer this question."
        )
        base.abstained, base.abstain_reason = True, "model_abstained"
        return base

    text, order = verify_citations(parsed.answer, parsed.citations, len(sources))
    if not order or not text:
        base.text = ABSTAIN_TEXT["unsupported"]
        base.abstained, base.abstain_reason = True, "unsupported"
        return base
    base.text = text
    base.citations = [Citation(i + 1, sources[n - 1]) for i, n in enumerate(order)]
    return base
