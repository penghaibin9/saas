from __future__ import annotations

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0-w1",
    description="岗位实习 Standalone 抽离工程。W1 只提供独立运行骨架；业务路由在源码闭包迁入并通过依赖门禁后注册。",
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {
        "status": "ok",
        "product": "internship-standalone",
        "sourceBaseline": settings.SOURCE_BASELINE_SHA,
        "phase": "W1",
    }
