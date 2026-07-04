"""
应用入口 —— 高校学生全生命周期管理平台 · SaaS 后台骨架
────────────────────────────────────────────────────────────
启动：
    cd backend
    python -m venv .venv
    .venv\\Scripts\\activate        （Windows；Linux/macOS 用 source .venv/bin/activate）
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

验收：
    http://localhost:8000/health   健康检查（统一响应结构）
    http://localhost:8000/docs     Swagger 文档

当前阶段：可运行 mock 骨架。不连库（DB_ENABLED=False）、不改 frontend/src、不改 miniapp。
契约来源：docs/api/00-API契约冻结总册.md（响应/错误码/分页/租户/角色/数据范围/审计/文件）。
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.response import success
from app.middleware.context import RequestContextMiddleware

APP_VERSION = "0.1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=APP_VERSION,
        description=(
            "SaaS 后台骨架（mock 数据，未连库）。统一响应：code / message / data / traceId / timestamp。\n\n"
            "**mock 账号**（任意非空密码）：`student01` 学生 · `teacher01` 教师(3 身份) · `admin01` 校级管理员。\n\n"
            "登录 `POST /api/v1/authz/login` 拿 accessToken，右上角 Authorize 填 `Bearer <token>` 后可调其余接口。"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 中间件（后加先执行：CORS 最外层 → 请求上下文/traceId/租户）
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["00·基础"], summary="健康检查")
    def health():
        return success({
            "status": "UP",
            "app": settings.APP_NAME,
            "version": APP_VERSION,
            "env": settings.APP_ENV,
            "dbEnabled": settings.DB_ENABLED,  # 骨架阶段恒 False：未连库
        })

    @app.get("/", include_in_schema=False)
    def index():
        return RedirectResponse(url="/docs")

    return app


app = create_app()
