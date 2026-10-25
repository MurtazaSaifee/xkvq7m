"""Application entrypoint. ``app`` is the ASGI callable used by uvicorn and Vercel."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.problems import register_problem_handlers
from app.api.v1.router import api_router
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware

STATIC_DIR_ENV = "WIND_STATIC_DIR"


def create_app(static_dir: Path | None = None) -> FastAPI:
    """Build the app. Serves the frontend from ``static_dir`` or ``$WIND_STATIC_DIR`` if set."""
    configure_logging()
    if static_dir is None and os.environ.get(STATIC_DIR_ENV):
        static_dir = Path(os.environ[STATIC_DIR_ENV])

    application = FastAPI(title="Wind Forecast Monitor API", version="0.1.0")
    application.add_middleware(RequestContextMiddleware)
    register_problem_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    if static_dir is not None:
        # Mounted last so every /api route is matched before the frontend catch-all.
        application.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return application


app = create_app()
