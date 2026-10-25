from fastapi import APIRouter

from app.api.v1 import decision, health, meta

# Every v1 router is included here and mounted under /api/v1 by app.main.
api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(meta.router, tags=["meta"])
api_router.include_router(decision.router, tags=["decision"])
