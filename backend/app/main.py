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

    @app.on_event("startup")
    async def _sandbox_midnight_reset():
        """可选的体验沙箱每晚 0 点自动重置（默认关闭；单实例进程内定时；多实例部署请改用 cron 跑
        scripts/reset_sandbox_school.py --confirm 并置 SANDBOX_AUTO_RESET=false）。"""
        import asyncio

        from app.db.session import db_enabled
        if not (settings.sandbox_auto_reset and db_enabled()):
            return

        async def _loop():
            from anyio import to_thread

            from app.services.sandbox_service import reset_sandbox, seconds_until_next_midnight
            while True:
                try:
                    await asyncio.sleep(seconds_until_next_midnight())
                    from app.db.session import get_sessionmaker
                    db = get_sessionmaker()()
                    try:
                        await to_thread.run_sync(lambda: reset_sandbox(db, dry_run=False))
                    finally:
                        db.close()
                except asyncio.CancelledError:
                    return
                except Exception:  # noqa: BLE001 — 单次失败不终止调度，次日再试
                    logging.getLogger("app.sandbox").exception("sandbox midnight reset failed")

        asyncio.create_task(_loop())

    @app.on_event("startup")
    async def _internship_overdue_scan():
        """Run the idempotent leave-overdue scan for every active tenant without an HTTP caller."""
        import asyncio

        from app.db.session import db_enabled
        if not (settings.INTERNSHIP_OVERDUE_AUTO_SCAN and db_enabled()):
            return

        def _run_once():
            from sqlalchemy import select

            from app.core.context import set_tenant
            from app.db.session import get_sessionmaker
            from app.models import Tenant
            from app.modules.internship.services import internship_leave_service as leave_service
            db = get_sessionmaker()()
            try:
                tenant_ids = list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
            finally:
                db.close()
            for tenant_id in tenant_ids:
                try:
                    set_tenant({"tenantId": str(tenant_id)})
                    leave_service.refresh_overdue(system=True)  # 系统定时扫描：绕过人工触发的校级守卫
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.internship").exception("internship overdue scan failed tenant=%s", tenant_id)
                finally:
                    set_tenant(None)

        async def _loop():
            from anyio import to_thread

            while True:
                try:
                    await to_thread.run_sync(_run_once)
                    await asyncio.sleep(6 * 60 * 60)
                except asyncio.CancelledError:
                    return
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.internship").exception("internship overdue scheduler failed")
                    await asyncio.sleep(5 * 60)

        asyncio.create_task(_loop())

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

    @app.get("/health/ready", tags=["00·基础"], summary="就绪检查（DB/上传/导出目录）")
    def health_ready():
        import os

        checks = {}
        # 数据库连通
        if settings.DB_ENABLED:
            try:
                from sqlalchemy import text

                from app.db.session import get_engine
                with get_engine().connect() as conn:
                    conn.execute(text("SELECT 1"))
                checks["database"] = {"ok": True}
            except Exception as e:  # noqa: BLE001
                checks["database"] = {"ok": False, "error": str(e)[:120]}
        else:
            checks["database"] = {"ok": True, "note": "DB_ENABLED=false（mock 模式）"}
        # 上传目录可写
        for key, path in (("uploadDir", settings.UPLOAD_DIR), ("exportDir", "./exports")):
            try:
                os.makedirs(path, exist_ok=True)
                probe = os.path.join(path, ".write_probe")
                with open(probe, "w") as f:
                    f.write("ok")
                os.remove(probe)
                checks[key] = {"ok": True, "path": path}
            except Exception as e:  # noqa: BLE001
                checks[key] = {"ok": False, "path": path, "error": str(e)[:120]}
        all_ok = all(c.get("ok") for c in checks.values())
        return success({"status": "READY" if all_ok else "DEGRADED", "checks": checks})

    @app.get("/", include_in_schema=False)
    def index():
        if _is_prod:
            return success({"status": "UP"})
        return RedirectResponse(url="/docs")

    return app


app = create_app()
