"""Models & Settings endpoints (TRD §8): local runtime only, no provider keys."""

from fastapi import APIRouter

from app.api.deps import SessionDep, SettingsDep, WorkspaceDep
from app.modules.audit import audit_commit
from app.modules.models import service
from app.schemas.settings import (
    ModelSettingsOut,
    ReindexResponse,
    SaveRequest,
    SaveResponse,
    ValidateRequest,
    ValidateResponse,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/models", response_model=ModelSettingsOut)
def get_models(
    session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> ModelSettingsOut:
    return service.describe(session, settings, workspace.id)


@router.post("/models/validate", response_model=ValidateResponse)
def validate_models(
    body: ValidateRequest, session: SessionDep, settings: SettingsDep
) -> ValidateResponse:
    """Probe availability, structured output and the real embedding dimension."""
    return service.validate(session, settings, body)


@router.put("/models", response_model=SaveResponse)
def save_models(
    body: SaveRequest, session: SessionDep, settings: SettingsDep, workspace: WorkspaceDep
) -> SaveResponse:
    reembed = service.save(session, settings, body)
    audit_commit(
        session,
        workspace.id,
        "settings.models_saved",
        "settings",
        None,
        generation_model=body.generation_model,
        embedding_model=body.embedding_model,
        reranker_enabled=body.reranker_enabled,
        reembed_required=reembed,
    )
    return SaveResponse(
        settings=service.describe(session, settings, workspace.id), reembed_required=reembed
    )


@router.post("/reindex", response_model=ReindexResponse, status_code=202)
def reindex(session: SessionDep, workspace: WorkspaceDep) -> ReindexResponse:
    """Queue all documents for processing again, e.g. after changing the embedding model."""
    queued = service.reindex_all(session, workspace.id)
    audit_commit(session, workspace.id, "settings.reindex", "document", None, queued=queued)
    return ReindexResponse(queued=queued)
