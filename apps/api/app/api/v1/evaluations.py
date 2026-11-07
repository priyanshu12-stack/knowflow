"""Evaluation Lab endpoints (TRD §8, PRD §5.4)."""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import SessionDep, SettingsDep, StorageDep, WorkspaceDep
from app.core.config import REPO_ROOT
from app.core.errors import ErrorResponse
from app.modules.audit import audit_commit
from app.modules.evaluation import runner, service
from app.modules.evaluation.importer import MAX_BYTES
from app.schemas.evaluation import (
    DatasetDetail,
    DatasetIn,
    DatasetOut,
    ImportRowError,
    ImportSummary,
    RunDetail,
    RunIn,
    RunOut,
    SampleLoaded,
)

router = APIRouter(prefix="/evaluations", tags=["evaluation"])
_404: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}}


@router.post(
    "/datasets",
    response_model=DatasetOut,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
def create_dataset(body: DatasetIn, session: SessionDep, workspace: WorkspaceDep) -> DatasetOut:
    ds = service.create_dataset(session, workspace.id, body)
    audit_commit(session, workspace.id, "evaluation.dataset_created", "dataset", ds.id)
    return service.dataset_out(session, ds)


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(session: SessionDep, workspace: WorkspaceDep) -> list[DatasetOut]:
    return service.list_datasets(session, workspace.id)


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail, responses=_404)
def get_dataset(dataset_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> DatasetOut:
    return service.get_dataset(session, workspace.id, dataset_id)


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> Response:
    service.delete_dataset(session, workspace.id, dataset_id)
    audit_commit(session, workspace.id, "evaluation.dataset_deleted", "dataset", dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/datasets/{dataset_id}/cases/import",
    response_model=ImportSummary,
    responses={**_404, 409: {"model": ErrorResponse}},
)
async def import_cases(
    dataset_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="CSV or JSONL evaluation cases")],
    session: SessionDep,
    workspace: WorkspaceDep,
) -> ImportSummary:
    content = await file.read(MAX_BYTES + 1)
    imported, errors = service.import_cases(
        session, workspace.id, dataset_id, file.filename or "cases", content
    )
    audit_commit(
        session,
        workspace.id,
        "evaluation.cases_imported",
        "dataset",
        dataset_id,
        imported=imported,
        rejected=len(errors),
    )
    return ImportSummary(
        imported=imported, errors=[ImportRowError(row=e.row, message=e.message) for e in errors]
    )


@router.post("/sample", response_model=SampleLoaded, status_code=202)
def load_sample(
    session: SessionDep, storage: StorageDep, workspace: WorkspaceDep, settings: SettingsDep
) -> SampleLoaded:
    """Upload the synthetic sample documents and create the bundled gold set (PRD §5.1)."""
    dataset_id, queued, existing = service.load_sample(
        session, storage, workspace, REPO_ROOT / "samples", settings.upload_max_bytes
    )
    audit_commit(
        session,
        workspace.id,
        "evaluation.sample_loaded",
        "dataset",
        dataset_id,
        documents_queued=queued,
    )
    return SampleLoaded(dataset_id=dataset_id, documents_queued=queued, documents_existing=existing)


@router.post(
    "/runs",
    response_model=RunOut,
    status_code=202,
    responses={**_404, 409: {"model": ErrorResponse}},
)
def create_run(
    body: RunIn, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> RunOut:
    """Queue a run; the worker executes it in the background."""
    run = runner.create_run(session, settings, workspace.id, body.dataset_id, body.config)
    audit_commit(
        session,
        workspace.id,
        "evaluation.run_queued",
        "evaluation_run",
        run.id,
        strategy=run.strategy,
        cases=run.total,
    )
    return service.run_out(run)


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    session: SessionDep, workspace: WorkspaceDep, dataset_id: uuid.UUID | None = None
) -> list[RunOut]:
    return service.list_runs(session, workspace.id, dataset_id)


@router.get("/runs/{run_id}", response_model=RunDetail, responses=_404)
def get_run(run_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> RunDetail:
    return service.get_run(session, workspace.id, run_id)


@router.get("/runs/{run_id}/export", responses=_404)
def export_run(
    run_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
    format: Annotated[Literal["json", "csv"], Query()] = "json",
) -> Response:
    detail = service.get_run(session, workspace.id, run_id)
    content, media = service.export_run(detail, format)
    filename = f"knowflow-eval-{detail.strategy}-{str(run_id)[:8]}.{format}".replace("/", "-")
    return Response(
        content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"model": ErrorResponse}},
)
def delete_run(run_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> Response:
    service.delete_run(session, workspace.id, run_id)
    audit_commit(session, workspace.id, "evaluation.run_deleted", "evaluation_run", run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
