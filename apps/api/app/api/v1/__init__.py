from fastapi import APIRouter

from app.api.v1 import (
    chat,
    documents,
    evaluations,
    health,
    jobs,
    search,
    settings,
    workspaces,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(workspaces.router)
router.include_router(documents.router)
router.include_router(jobs.router)
router.include_router(search.router)
router.include_router(settings.router)
router.include_router(chat.router)
router.include_router(evaluations.router)
