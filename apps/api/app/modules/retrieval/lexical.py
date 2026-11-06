"""PostgreSQL full-text retrieval (TRD §3, §9): `websearch_to_tsquery` + `ts_rank_cd`.

Uses the generated `chunks.search_tsv` column and its GIN index. Only chunks of `ready`
documents in the caller's workspace are searchable.
"""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.modules.retrieval.types import Candidate, Scope


def scoped(stmt: Select[tuple[Chunk, str]], scope: Scope) -> Select[tuple[Chunk, str]]:
    stmt = stmt.where(
        Chunk.workspace_id == scope.workspace_id,
        Chunk.strategy == scope.strategy,
        Document.workspace_id == scope.workspace_id,
        Document.status == "ready",
    )
    if scope.document_ids is not None:
        stmt = stmt.where(Chunk.document_id.in_(scope.document_ids))
    return stmt


def to_candidate(chunk: Chunk, name: str, score: float, retriever: str, rank: int) -> Candidate:
    return Candidate(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_name=name,
        text=chunk.text,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        section_path=chunk.section_path,
        chunk_index=chunk.chunk_index,
        score=score,
        ranks={retriever: rank},
    )


def lexical_search(session: Session, query: str, scope: Scope, limit: int) -> list[Candidate]:
    tsquery = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(Chunk.search_tsv, tsquery, 32)  # 32: normalise by rank / (rank + 1)
    stmt = (
        select(Chunk, Document.original_name, rank.label("score"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.search_tsv.op("@@")(tsquery))
        .order_by(rank.desc(), Chunk.id)
        .limit(limit)
    )
    rows = session.execute(scoped(stmt, scope)).all()
    return [
        to_candidate(chunk, name, float(score), "lexical", i)
        for i, (chunk, name, score) in enumerate(rows, start=1)
    ]
