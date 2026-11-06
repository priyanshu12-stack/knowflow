"""Evaluation datasets and runs: CRUD, import, sample loading and export (PRD §5.4)."""

import csv
import io
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    Document,
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    Workspace,
)
from app.modules.documents import service as documents
from app.modules.documents.storage import FileStorage
from app.modules.evaluation.importer import CaseIn, RowError, parse_cases
from app.schemas.evaluation import (
    CaseOut,
    DatasetDetail,
    DatasetIn,
    DatasetOut,
    ResultOut,
    RunDetail,
    RunOut,
)

SAMPLE_DATASET = ("Northwind gold set", "v1")


def _dataset(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID) -> EvaluationDataset:
    ds = session.scalar(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id, EvaluationDataset.workspace_id == workspace_id
        )
    )
    if ds is None:
        raise AppError("dataset_not_found", "This evaluation dataset doesn't exist.", 404)
    return ds


def create_dataset(session: Session, workspace_id: uuid.UUID, body: DatasetIn) -> EvaluationDataset:
    ds = EvaluationDataset(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name=body.name.strip(),
        version=body.version.strip(),
        description=body.description,
    )
    session.add(ds)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "dataset_exists",
            f"A dataset named “{body.name}” version {body.version} already exists. "
            "Use a new version.",
            409,
        ) from exc
    return ds


def _missing_documents(
    session: Session, workspace_id: uuid.UUID, cases: list[EvaluationCase]
) -> list[str]:
    names = {
        str(ev.get("document"))
        for c in cases
        for ev in c.expected_evidence
        if isinstance(ev, dict) and ev.get("document")
    }
    if not names:
        return []
    ready = set(
        session.scalars(
            select(Document.original_name).where(
                Document.workspace_id == workspace_id, Document.status == "ready"
            )
        )
    )
    return sorted(names - ready)


def dataset_out(session: Session, ds: EvaluationDataset, with_cases: bool = False) -> DatasetOut:
    cases = list(
        session.scalars(
            select(EvaluationCase)
            .where(EvaluationCase.dataset_id == ds.id)
            .order_by(EvaluationCase.external_id)
        )
    )
    runs = session.scalar(
        select(func.count()).select_from(EvaluationRun).where(EvaluationRun.dataset_id == ds.id)
    )
    base: dict[str, Any] = {
        "id": ds.id,
        "name": ds.name,
        "version": ds.version,
        "description": ds.description,
        "created_at": ds.created_at,
        "cases": len(cases),
        "dev_cases": sum(c.split == "dev" for c in cases),
        "test_cases": sum(c.split == "test" for c in cases),
        "runs": runs or 0,
        "missing_documents": _missing_documents(session, ds.workspace_id, cases),
    }
    if not with_cases:
        return DatasetOut(**base)
    return DatasetDetail(
        **base,
        case_list=[
            CaseOut(
                id=c.id,
                external_id=c.external_id,
                split=c.split,
                question=c.question,
                reference_answer=c.reference_answer,
                answerable=c.answerable,
                expected_evidence=c.expected_evidence,
                tags=c.tags,
            )
            for c in cases
        ],
    )


def list_datasets(session: Session, workspace_id: uuid.UUID) -> list[DatasetOut]:
    rows = session.scalars(
        select(EvaluationDataset)
        .where(EvaluationDataset.workspace_id == workspace_id)
        .order_by(EvaluationDataset.created_at.desc())
    ).all()
    return [dataset_out(session, ds) for ds in rows]


def get_dataset(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID) -> DatasetOut:
    return dataset_out(session, _dataset(session, workspace_id, dataset_id), with_cases=True)


def delete_dataset(session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID) -> None:
    try:
        ds = _dataset(session, workspace_id, dataset_id)
    except AppError:
        return
    session.delete(ds)
    session.commit()


def add_cases(session: Session, ds: EvaluationDataset, cases: list[CaseIn]) -> int:
    session.add_all(
        EvaluationCase(
            dataset_id=ds.id,
            external_id=c.id or uuid.uuid4().hex[:8],
            split=c.split,
            question=c.question,
            reference_answer=c.reference_answer,
            answerable=c.answerable,
            expected_evidence=[e.model_dump(exclude_none=True) for e in c.expected_evidence],
            expected_chunk_ids=c.expected_chunk_ids,
            expected_sql=c.expected_sql,
            tags=c.tags,
        )
        for c in cases
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError(
            "duplicate_case_ids",
            "Some case ids already exist in this dataset. Import into a new dataset version.",
            409,
        ) from exc
    return len(cases)


def import_cases(
    session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID, filename: str, content: bytes
) -> tuple[int, list[RowError]]:
    ds = _dataset(session, workspace_id, dataset_id)
    has_runs = session.scalar(
        select(func.count()).select_from(EvaluationRun).where(EvaluationRun.dataset_id == ds.id)
    )
    if has_runs:
        raise AppError(
            "dataset_locked",
            "This dataset already has evaluation runs, so its cases can't change. "
            "Create a new version to keep results comparable.",
            409,
        )
    cases, errors = parse_cases(filename, content)
    if errors and not cases:
        return 0, errors
    return add_cases(session, ds, cases), errors


def load_sample(
    session: Session,
    storage: FileStorage,
    workspace: Workspace,
    samples_root: Path,
    max_bytes: int,
) -> tuple[uuid.UUID, int, int]:
    """Upload the synthetic sample corpus (skipping identical files) and its gold set."""
    queued = existing = 0
    doc_dir = samples_root / "documents"
    if not doc_dir.is_dir():
        raise AppError("samples_missing", "The sample files aren't available in this install.", 404)
    for path in sorted(doc_dir.iterdir()):
        if path.suffix.lower() not in (".md", ".txt", ".pdf", ".docx"):
            continue
        mime = "text/markdown" if path.suffix == ".md" else "text/plain"
        with path.open("rb") as f:
            out = documents.upload_document(
                session,
                storage,
                workspace,
                filename=path.name,
                declared_mime=mime,
                source=f,
                max_bytes=max_bytes,
                on_duplicate="skip",
            )
        if out.outcome == "skipped":
            existing += 1
        else:
            queued += 1

    name, version = SAMPLE_DATASET
    ds = session.scalar(
        select(EvaluationDataset).where(
            EvaluationDataset.workspace_id == workspace.id,
            EvaluationDataset.name == name,
            EvaluationDataset.version == version,
        )
    )
    if ds is None:
        ds = create_dataset(
            session,
            workspace.id,
            DatasetIn(
                name=name,
                version=version,
                description="50 synthetic questions over the Northwind sample documents "
                "(factual, exact identifiers, multi-hop, dated conflicts, unanswerable and a "
                "prompt-injection document). Labels were written by the coding agent and "
                "checked mechanically against the text; not yet reviewed by a person.",
            ),
        )
        content = (samples_root / "evaluation" / "northwind-gold-v1.jsonl").read_bytes()
        cases, errors = parse_cases("northwind-gold-v1.jsonl", content)
        if errors:
            raise AppError(
                "sample_invalid", f"The bundled sample set is invalid: {errors[0].message}", 500
            )
        add_cases(session, ds, cases)
    return ds.id, queued, existing


# --- Runs ---


def run_out(run: EvaluationRun) -> RunOut:
    return RunOut.model_validate(run, from_attributes=True)


def list_runs(
    session: Session, workspace_id: uuid.UUID, dataset_id: uuid.UUID | None
) -> list[RunOut]:
    stmt = select(EvaluationRun).where(EvaluationRun.workspace_id == workspace_id)
    if dataset_id is not None:
        stmt = stmt.where(EvaluationRun.dataset_id == dataset_id)
    return [
        run_out(r)
        for r in session.scalars(stmt.order_by(EvaluationRun.created_at.desc()).limit(200))
    ]


def _run(session: Session, workspace_id: uuid.UUID, run_id: uuid.UUID) -> EvaluationRun:
    run = session.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id, EvaluationRun.workspace_id == workspace_id
        )
    )
    if run is None:
        raise AppError("run_not_found", "This evaluation run doesn't exist.", 404)
    return run


def get_run(session: Session, workspace_id: uuid.UUID, run_id: uuid.UUID) -> RunDetail:
    run = _run(session, workspace_id, run_id)
    rows = session.execute(
        select(EvaluationResult, EvaluationCase)
        .join(EvaluationCase, EvaluationCase.id == EvaluationResult.case_id)
        .where(EvaluationResult.run_id == run.id)
        .order_by(EvaluationCase.external_id)
    ).all()
    return RunDetail(
        **run_out(run).model_dump(),
        results=[
            ResultOut(
                case_id=c.id,
                external_id=c.external_id,
                split=c.split,
                question=c.question,
                reference_answer=c.reference_answer,
                answerable=c.answerable,
                expected_evidence=c.expected_evidence,
                tags=c.tags,
                retrieved=r.retrieved_ids,
                answer=r.answer,
                metrics=r.metrics,
                failure_category=r.failure_category,
                latency_ms=r.latency_ms,
                error=r.error,
            )
            for r, c in rows
        ],
    )


def delete_run(session: Session, workspace_id: uuid.UUID, run_id: uuid.UUID) -> None:
    try:
        run = _run(session, workspace_id, run_id)
    except AppError:
        return
    if run.status == "running":
        raise AppError("run_in_progress", "This run is still in progress.", 409)
    session.delete(run)
    session.commit()


CSV_METRICS = (
    "recall_at_k",
    "precision_at_k",
    "mrr",
    "ndcg_at_k",
    "hit_at_k",
    "abstained",
    "abstention_correct",
    "citation_precision",
    "injection_resisted",
    "retrieval_ms",
)


def export_run(detail: RunDetail, fmt: str) -> tuple[str, str]:
    """(content, media type). JSON includes the full config; CSV is one row per case."""
    if fmt == "json":
        return json.dumps(
            detail.model_dump(mode="json"), indent=2, ensure_ascii=False
        ), "application/json"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "# run",
            detail.label,
            "dataset",
            detail.config.get("dataset"),
            "config",
            json.dumps({k: v for k, v in detail.config.items() if k not in ("dataset", "machine")}),
        ]
    )
    writer.writerow(
        ["case_id", "split", "question", "answerable", "failure_category", *CSV_METRICS, "answer"]
    )
    for r in detail.results:
        writer.writerow(
            [r.external_id, r.split, r.question, r.answerable, r.failure_category or ""]
            + [r.metrics.get(k, "") for k in CSV_METRICS]
            + [r.answer or ""]
        )
    return buf.getvalue(), "text/csv"
