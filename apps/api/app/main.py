"""FastAPI application factory. Run: uvicorn app.main:app --port 8000"""

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_request_middleware
from app.core.upload_limit import UploadSizeLimitMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="KnowFlow API",
        version="0.1.0",
        description="Local-first knowledge intelligence. No paid inference APIs.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    register_error_handlers(app)
    # Added before the request middleware so it runs inside it (request_id is already set).
    app.add_middleware(
        UploadSizeLimitMiddleware,
        path="/api/v1/documents",
        max_file_bytes=settings.upload_max_bytes,
    )
    register_request_middleware(app)
    app.include_router(v1_router)
    return app


app = create_app()
