from __future__ import annotations

from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings
from app.core.exceptions import register_exception_handlers

app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0-w2",
    description="跃科岗位实习管理平台 Standalone。W2 开始挂载独立岗位实习生产路由。",
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {
        "status": "ok",
        "product": "internship-standalone",
        "sourceBaseline": settings.SOURCE_BASELINE_SHA,
        "phase": "W2",
    }
