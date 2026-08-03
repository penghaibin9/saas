"""
应用入口 —— 高校学生全生命周期管理平台 · SaaS 后台

启动：
    cd backend
    uvicorn app.main:app --reload --port 8000
验收：
    http://localhost:8000/health
"""
from __future__ import annotations

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.response import fail, success
from app.core.security import (
    assert_cors_safe,
    assert_prod_flags_safe,
    assert_scale_safe,
    assert_scheduler_safe,
    assert_secret_safe,
)
from app.middleware.context import RequestContextMiddleware

APP_VERSION = getattr(settings, "APP_VERSION", None) or "1.0.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("app.startup")


def _ops_authorized(request: Request, x_ops_token: str | None) -> bool:
    """运维探针：INTERNAL_OPS_TOKEN 匹配；非生产允许本机/测试客户端。"""
    expected = (settings.INTERNAL_OPS_TOKEN or "").strip()
    provided = (x_ops_token or "").strip()
    if expected and provided and provided == expected:
        return True
    auth = (request.headers.get("authorization") or "").strip()
    if expected and auth.lower().startswith("bearer "):
        if auth[7:].strip() == expected:
            return True
    if not settings.is_prod:
        # 非生产：无令牌时放开本机与 TestClient；有令牌则上面已匹配
        if not expected:
            return True
        client = request.client.host if request.client else ""
        if client in ("127.0.0.1", "::1", "localhost", "testclient"):
            return True
    return False


def _deny_ops() -> JSONResponse:
    return JSONResponse(status_code=403, content=fail("NO_PERMISSION", "运维探针未授权"))


async def _cancel_tasks(tasks: list) -> None:
    import asyncio

    for t in tasks:
        if t is None or t.done():
            continue
        t.cancel()
    for t in tasks:
        if t is None:
            continue
        try:
            await t
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            _log.exception("scheduler task shutdown error")


# 升级代码但忘记执行数据库迁移，是最容易发生、也最难自查的部署事故。
# 相关功能本身已做降级（表缺失时自动退回旧口径，不会崩），这里只负责把
# 「该跑迁移了」这件事在启动日志里说清楚，不阻止启动、不自动改库结构。
_REQUIRED_TABLES = {
    "t_student_account_link": "学生账号绑定（学号更正后仍能登录/收消息）",
}


def _check_pending_migrations() -> None:
    from app.db.session import db_enabled
    if not db_enabled():
        return
    try:
        from sqlalchemy import inspect as sa_inspect

        from app.db.session import get_engine
        existing = set(sa_inspect(get_engine()).get_table_names())
    except Exception as exc:  # noqa: BLE001 - 探测失败不影响启动
        _log.warning("migration_check_skipped err=%s", type(exc).__name__)
        return
    missing = {t: why for t, why in _REQUIRED_TABLES.items() if t not in existing}
    if not missing:
        return
    for table, why in missing.items():
        _log.warning(
            "PENDING_MIGRATION 缺少数据表 %s（%s）。相关功能已自动降级运行，"
            "请执行：cd backend && alembic upgrade head", table, why)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from app.db.session import db_enabled

    _check_pending_migrations()

    tasks: list = []
    app.state.scheduler_tasks = tasks
    mode = (settings.SCHEDULER_MODE or "web").strip().lower()
    if mode != "web":
        _log.info("scheduler_mode=%s — web process will not start in-process jobs", mode)
        yield
        return

    if settings.sandbox_auto_reset and db_enabled():
        async def _sandbox_loop():
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
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.sandbox").exception("sandbox midnight reset failed")

        tasks.append(asyncio.create_task(_sandbox_loop(), name="sandbox-midnight-reset"))

    if db_enabled():
        def _student_affairs_background_once():
            from sqlalchemy import select

            from app.core.context import set_tenant
            from app.db.session import get_sessionmaker
            from app.models import Tenant
            from app.services import affairs_appeal_repair_service, affairs_leave_export_service

            db = get_sessionmaker()()
            try:
                tenant_ids = list(db.scalars(select(Tenant.id).where(
                    Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")),
                )))
            finally:
                db.close()
            for tenant_id in tenant_ids:
                try:
                    set_tenant({"tenantId": str(tenant_id)})
                    affairs_appeal_repair_service.repair_pending(limit=100)
                    affairs_leave_export_service.run_pending(
                        limit=2, worker_id=f"web-affairs:{tenant_id}",
                    )
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception(
                        "student affairs background job failed tenant=%s", tenant_id,
                    )
                finally:
                    set_tenant(None)

        async def _student_affairs_background_loop():
            from anyio import to_thread
            while True:
                try:
                    await to_thread.run_sync(_student_affairs_background_once)
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    return
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception(
                        "student affairs background scheduler failed",
                    )
                    await asyncio.sleep(60)

        tasks.append(asyncio.create_task(
            _student_affairs_background_loop(), name="student-affairs-background",
        ))

    if settings.INTERNSHIP_OVERDUE_AUTO_SCAN and db_enabled():
        def _internship_once():
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
                    leave_service.refresh_overdue(system=True)
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.internship").exception(
                        "internship overdue scan failed tenant=%s", tenant_id)
                finally:
                    set_tenant(None)

        async def _internship_loop():
            from anyio import to_thread
            while True:
                try:
                    await to_thread.run_sync(_internship_once)
                    await asyncio.sleep(6 * 60 * 60)
                except asyncio.CancelledError:
                    return
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.internship").exception("internship overdue scheduler failed")
                    await asyncio.sleep(5 * 60)

        tasks.append(asyncio.create_task(_internship_loop(), name="internship-overdue-scan"))

    if settings.AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN and db_enabled():
        def _affairs_once():
            from sqlalchemy import select

            from app.core.context import set_tenant
            from app.db.session import get_sessionmaker
            from app.models import Tenant
            from app.services import affairs_leave_service
            db = get_sessionmaker()()
            try:
                tenant_ids = list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
            finally:
                db.close()
            for tenant_id in tenant_ids:
                try:
                    set_tenant({"tenantId": str(tenant_id)})
                    affairs_leave_service.scan_overdue()
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception(
                        "affairs leave overdue scan failed tenant=%s", tenant_id)
                finally:
                    set_tenant(None)

        async def _affairs_loop():
            from anyio import to_thread
            while True:
                try:
                    await to_thread.run_sync(_affairs_once)
                    await asyncio.sleep(6 * 60 * 60)
                except asyncio.CancelledError:
                    return
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception("affairs leave overdue scheduler failed")
                    await asyncio.sleep(5 * 60)

        tasks.append(asyncio.create_task(_affairs_loop(), name="affairs-leave-overdue-scan"))

    if settings.AFFAIRS_RISK_TIMEOUT_AUTO_SCAN and db_enabled():
        def _affairs_risk_once():
            from sqlalchemy import select

            from app.core.context import set_tenant
            from app.db.session import get_sessionmaker
            from app.models import Tenant
            from app.services import affairs_risk_service
            db = get_sessionmaker()()
            try:
                tenant_ids = list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
            finally:
                db.close()
            for tenant_id in tenant_ids:
                try:
                    set_tenant({"tenantId": str(tenant_id)})
                    affairs_risk_service.scan_timeout()
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception(
                        "affairs risk timeout scan failed tenant=%s", tenant_id)
                finally:
                    set_tenant(None)

        async def _affairs_risk_loop():
            from anyio import to_thread
            while True:
                try:
                    await to_thread.run_sync(_affairs_risk_once)
                    await asyncio.sleep(6 * 60 * 60)
                except asyncio.CancelledError:
                    return
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception("affairs risk timeout scheduler failed")
                    await asyncio.sleep(5 * 60)

        tasks.append(asyncio.create_task(_affairs_risk_loop(), name="affairs-risk-timeout-scan"))

    if settings.AFFAIRS_COUNSELOR_TEMP_AUTO_SCAN and db_enabled():
        def _counselor_temp_once():
            from sqlalchemy import select

            from app.core.context import set_tenant
            from app.db.session import get_sessionmaker
            from app.models import Tenant
            from app.services import affairs_counselor_service
            db = get_sessionmaker()()
            try:
                tenant_ids = list(db.scalars(select(Tenant.id).where(Tenant.status == "ACTIVE")))
            finally:
                db.close()
            for tenant_id in tenant_ids:
                try:
                    set_tenant({"tenantId": str(tenant_id)})
                    affairs_counselor_service.scan_expired_temps()
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception(
                        "affairs counselor temp expire scan failed tenant=%s", tenant_id)
                finally:
                    set_tenant(None)

        async def _counselor_temp_loop():
            from anyio import to_thread
            while True:
                try:
                    await to_thread.run_sync(_counselor_temp_once)
                    await asyncio.sleep(6 * 60 * 60)
                except asyncio.CancelledError:
                    return
                except Exception:  # noqa: BLE001
                    logging.getLogger("app.affairs").exception(
                        "affairs counselor temp expire scheduler failed")
                    await asyncio.sleep(5 * 60)

        tasks.append(asyncio.create_task(_counselor_temp_loop(), name="affairs-counselor-temp-scan"))

    try:
        yield
    finally:
        await _cancel_tasks(tasks)
        app.state.scheduler_tasks = []


def create_app() -> FastAPI:
    assert_secret_safe()
    assert_cors_safe()
    assert_prod_flags_safe()
    assert_scale_safe()
    assert_scheduler_safe()

    _is_prod = settings.is_prod
    # 启动日志只输出状态，不输出密钥/密码/完整连接串
    _log.info(
        "deployment=%s app_env=%s is_prod=%s mock_login=%s db_enabled=%s scheduler=%s multi_instance=%s",
        settings.DEPLOYMENT_MODE, settings.APP_ENV, settings.is_prod,
        settings.mock_login_enabled, settings.DB_ENABLED,
        settings.SCHEDULER_MODE, settings.MULTI_INSTANCE,
    )
    if (settings.JWT_SECRET_KEY or "").strip() and not (settings.JWT_SECRET or "").strip():
        _log.warning("JWT_SECRET_KEY is deprecated; prefer JWT_SECRET")
    elif (settings.JWT_SECRET_KEY or "").strip() and (settings.JWT_SECRET or "").strip():
        if settings.JWT_SECRET_KEY.strip() == settings.JWT_SECRET.strip():
            _log.warning("JWT_SECRET_KEY is deprecated; prefer JWT_SECRET only")
    if (settings.ENV or settings.ENVIRONMENT or "").strip():
        _log.warning("ENV/ENVIRONMENT is deprecated; prefer APP_ENV")
    if (settings.JWT_ALGORITHM or "").strip():
        _log.warning("JWT_ALGORITHM is deprecated; prefer JWT_ALG")
    app = FastAPI(
        title=settings.APP_NAME,
        version=APP_VERSION,
        description="SaaS 后台。统一响应：code / message / data / traceId / timestamp。",
        docs_url=None if _is_prod else "/docs",
        redoc_url=None if _is_prod else "/redoc",
        openapi_url=None if _is_prod else "/openapi.json",
        lifespan=lifespan,
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

    @app.get("/health/ready", tags=["00·基础"], summary="就绪检查（运维）")
    def health_ready(
        request: Request,
        x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
    ):
        if not _ops_authorized(request, x_ops_token):
            return _deny_ops()
        return _build_ready_payload(expose_detail=not _is_prod)

    @app.get("/internal/metrics", tags=["00·基础"], summary="进程指标（运维）")
    def internal_metrics(
        request: Request,
        x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
    ):
        if not _ops_authorized(request, x_ops_token):
            return _deny_ops()
        from app.core.runtime_metrics import snapshot
        return success(snapshot())

    @app.get("/health/metrics", include_in_schema=False)
    def health_metrics_compat(
        request: Request,
        x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
    ):
        """兼容旧路径：同样要求运维鉴权，正式文档以 /internal/metrics 为准。"""
        if not _ops_authorized(request, x_ops_token):
            return _deny_ops()
        from app.core.runtime_metrics import snapshot
        return success(snapshot())

    @app.get("/", include_in_schema=False)
    def index():
        if _is_prod:
            return success({"status": "UP"})
        return RedirectResponse(url="/docs")

    return app


def _build_ready_payload(*, expose_detail: bool) -> Any:
    import os

    from sqlalchemy import text

    checks: dict = {}
    if settings.DB_ENABLED:
        try:
            from app.db.session import get_engine
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = {"ok": True}
            if expose_detail:
                pool = engine.pool
                checks["dbPool"] = {
                    "ok": True,
                    "size": pool.size() if hasattr(pool, "size") else None,
                    "checkedOut": pool.checkedout() if hasattr(pool, "checkedout") else None,
                    "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
                }
                from alembic.config import Config
                from alembic.runtime.migration import MigrationContext
                from alembic.script import ScriptDirectory
                config = Config("alembic.ini")
                expected_heads = set(ScriptDirectory.from_config(config).get_heads())
                with engine.connect() as migration_conn:
                    current_heads = set(MigrationContext.configure(migration_conn).get_current_heads())
                checks["schemaMigration"] = {
                    "ok": current_heads == expected_heads,
                    "current": sorted(current_heads),
                    "expected": sorted(expected_heads),
                }
            else:
                # production：只返回迁移是否一致，不暴露 SHA
                try:
                    from alembic.config import Config
                    from alembic.runtime.migration import MigrationContext
                    from alembic.script import ScriptDirectory
                    from app.db.session import get_engine as _ge
                    eng = _ge()
                    config = Config("alembic.ini")
                    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
                    with eng.connect() as migration_conn:
                        current_heads = set(MigrationContext.configure(migration_conn).get_current_heads())
                    checks["schemaMigration"] = {"ok": current_heads == expected_heads}
                except Exception:  # noqa: BLE001
                    checks["schemaMigration"] = {"ok": False}
        except Exception:  # noqa: BLE001
            checks["database"] = {"ok": False} if not expose_detail else {
                "ok": False, "error": "database_unreachable",
            }
    else:
        checks["database"] = {"ok": True, "note": "DB_ENABLED=false"}

    if settings.REDIS_URL:
        try:
            from app.core.redis_client import redis_health
            rh = redis_health()
            if expose_detail:
                checks["redis"] = rh
            else:
                checks["redis"] = {"ok": bool(rh.get("ok"))}
        except Exception:  # noqa: BLE001
            checks["redis"] = {"ok": False}

    if settings.DB_ENABLED:
        try:
            from app.services.audit_log import get_audit_db_health
            audit_state = get_audit_db_health()
            fails = audit_state.get("consecutiveFailures") or 0
            if expose_detail:
                checks["auditLog"] = (
                    {"ok": True} if fails == 0 else
                    {"ok": False, "consecutiveFailures": fails,
                     "lastFailure": audit_state.get("lastFailure")}
                )
            else:
                checks["auditLog"] = {"ok": fails == 0}
        except Exception:  # noqa: BLE001
            checks["auditLog"] = {"ok": False}

    for key, path in (("uploadDir", settings.UPLOAD_DIR), ("exportDir", settings.EXPORT_DIR)):
        probe = None
        try:
            os.makedirs(path, exist_ok=True)
            fd, probe = tempfile.mkstemp(prefix=".write_probe_", dir=path)
            try:
                os.write(fd, b"ok")
            finally:
                os.close(fd)
            checks[key] = {"ok": True} if not expose_detail else {"ok": True, "path": path}
        except Exception as e:  # noqa: BLE001
            checks[key] = {"ok": False} if not expose_detail else {
                "ok": False, "error": str(e)[:80],
            }
        finally:
            if probe:
                try:
                    os.remove(probe)
                except OSError:
                    pass

    all_ok = all(c.get("ok") for c in checks.values())
    payload = success({"status": "READY" if all_ok else "DEGRADED", "checks": checks})
    return payload if all_ok else JSONResponse(status_code=503, content=payload)


app = create_app()
