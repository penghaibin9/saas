"""
应用入口 —— 高校学生全生命周期管理平台 · SaaS 后台骨架
────────────────────────────────────────────────────────────
启动：
    cd backend
    uvicorn app.main:app --reload --port 8000
验收：
    http://localhost:8000/health   健康检查（统一响应结构）
    http://localhost:8000/docs     Swagger 文档
契约来源：docs/api/00-API契约冻结总册.md。
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
from app.core.security import assert_cors_safe, assert_prod_flags_safe, assert_secret_safe
from app.middleware.context import RequestContextMiddleware

APP_VERSION = "0.1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    # 安全底线：生产环境弱/默认 JWT 密钥拒绝启动（防伪造令牌绕过权限）。
    assert_secret_safe()
    # 生产环境禁止 CORS 通配符（* + credentials 不安全），强制显式白名单。
    assert_cors_safe()
    # 生产环境 DEBUG 必须关闭；mock-login 不得显式开启。
    assert_prod_flags_safe()
    # 生产环境关闭 /docs、/redoc、/openapi.json，不把接口蓝图暴露公网。
    _is_prod = settings.APP_ENV.strip().lower() in ("prod", "production")
    app = FastAPI(
        title=settings.APP_NAME,
        version=APP_VERSION,
        description="SaaS 后台。统一响应：code / message / data / traceId / timestamp。",
        docs_url=None if _is_prod else "/docs",
        redoc_url=None if _is_prod else "/redoc",
        openapi_url=None if _is_prod else "/openapi.json",
    )

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
        if _is_prod:
            return success({"status": "UP"})
        return success({
            "status": "UP",
            "app": settings.APP_NAME,
            "version": APP_VERSION,
            "env": settings.APP_ENV,
            "dbEnabled": settings.DB_ENABLED,
        })

    @app.get("/", include_in_schema=False)
    def index():
        if _is_prod:
            return success({"status": "UP"})
        return RedirectResponse(url="/docs")

    return app


app = create_app()
