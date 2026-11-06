from fastapi import APIRouter

from app.api.v1 import documents, health, jobs, workspaces

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(workspaces.router)
router.include_router(documents.router)
router.include_router(jobs.router)
