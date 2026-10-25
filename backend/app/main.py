"""Application entrypoint. ``app`` is the ASGI callable used by uvicorn and Vercel."""

from fastapi import FastAPI

from app.api.v1.router import api_router


def create_app() -> FastAPI:
    application = FastAPI(title="Wind Forecast Monitor API", version="0.1.0")
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
