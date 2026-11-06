"""Ingestion job progress (TRD §8)."""

import uuid

from fastapi import APIRouter

from app.api.deps import SessionDep, WorkspaceDep
from app.core.errors import AppError, ErrorResponse
from app.modules.documents import repository
from app.schemas.documents import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut, responses={404: {"model": ErrorResponse}})
def get_job(job_id: uuid.UUID, session: SessionDep, workspace: WorkspaceDep) -> JobOut:
    job = repository.get_job(session, workspace.id, job_id)
    if job is None:
        raise AppError("job_not_found", "This job doesn't exist.", 404)
    return JobOut.model_validate(job)
