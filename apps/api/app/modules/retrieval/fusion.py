"""Reciprocal Rank Fusion (TRD §6.2, ADR-004): score(d) = Σ 1 / (k + rank_r(d)).

Rank-based, so dense cosine scores and FTS ranks never need to share a scale. k=60 is the value
from Cormack et al. (2009); it is a setting, recorded with every evaluation run.
"""

from app.modules.retrieval.types import Candidate


def rrf(ranked_lists: dict[str, list[Candidate]], k: int = 60) -> list[Candidate]:
    fused: dict[object, Candidate] = {}
    scores: dict[object, float] = {}
    for name, items in ranked_lists.items():
        for rank, cand in enumerate(items, start=1):
            key = cand.chunk_id
            if key not in fused:
                fused[key] = Candidate(**{**cand.__dict__, "ranks": {}})
            fused[key].ranks[name] = rank
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    out = sorted(fused.values(), key=lambda c: (-scores[c.chunk_id], str(c.chunk_id)))
    for c in out:
        c.score = scores[c.chunk_id]
    return out
