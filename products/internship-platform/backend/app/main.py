from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.core.context import set_current_user, set_tenant
from app.core.exceptions import register_exception_handlers
from app.core.security import decode_token
from app.db.session import get_engine

app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0-w2",
    description="跃科岗位实习管理平台 Standalone。W2 开始挂载独立岗位实习生产路由。",
)

register_exception_handlers(app)


@app.middleware("http")
async def signed_bearer_context(request: Request, call_next):
    """Install signed tenant/user context before sync dependencies/endpoints enter threadpools.

    FastAPI sync dependencies may run in worker threads. ContextVar mutations made inside one
    dependency are not a reliable request-wide authority source for later sync services. Installing
    the already-signed JWT context at the ASGI boundary makes tenant scope available consistently;
    the normal auth dependency still performs account/credential-version validation.
    """
    set_tenant(None)
    set_current_user(None)
    raw = str(request.headers.get("Authorization") or "").strip()
    if raw.lower().startswith("bearer "):
        token = raw.split(None, 1)[1].strip()
        if token:
            try:
                claims = decode_token(token)
                tenant_id = claims.get("tenantId") or claims.get("tenant_id")
                if tenant_id:
                    set_tenant({
                        "tenantId": str(tenant_id),
                        "tenantCode": str(claims.get("tenantCode") or ""),
                        "schoolName": str(claims.get("tenantName") or ""),
                    })
                    set_current_user(dict(claims))
            except Exception:
                # Authentication dependencies remain the canonical error surface.
                set_tenant(None)
                set_current_user(None)
    try:
        return await call_next(request)
    finally:
        set_tenant(None)
        set_current_user(None)


app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {
        "status": "ok",
        "product": "internship-standalone",
        "sourceBaseline": settings.SOURCE_BASELINE_SHA,
        "phase": "W2",
    }


@app.get("/health/ready", tags=["ops"])
def readiness() -> dict:
    checks: dict[str, object] = {
        "database": "NOT_CONFIGURED",
        "schemaRevision": None,
        "schemaExpected": settings.EXPECTED_ALEMBIC_REVISION or None,
        "redis": "NOT_CONFIGURED",
        "fileStorage": "UNKNOWN",
    }
    ready = True

    try:
        if not (settings.DATABASE_URL or "").strip():
            ready = False
        else:
            with get_engine().connect() as db:
                db.execute(text("SELECT 1")).scalar_one()
                revision = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one()
            checks["database"] = "READY"
            checks["schemaRevision"] = str(revision)
            expected = (settings.EXPECTED_ALEMBIC_REVISION or "").strip()
            if expected and str(revision) != expected:
                checks["database"] = "SCHEMA_MISMATCH"
                ready = False
    except Exception:
        checks["database"] = "UNAVAILABLE"
        ready = False

    redis_url = (settings.REDIS_URL or "").strip()
    if redis_url:
        try:
            from redis import Redis

            client = Redis.from_url(
                redis_url,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
            checks["redis"] = "READY" if client.ping() else "UNAVAILABLE"
            if checks["redis"] != "READY":
                ready = False
        except Exception:
            checks["redis"] = "UNAVAILABLE"
            ready = False

    try:
        file_root = Path(settings.FILE_STORAGE_DIR).expanduser().resolve()
        file_root.mkdir(parents=True, exist_ok=True)
        writable = file_root.is_dir() and os.access(file_root, os.R_OK | os.W_OK | os.X_OK)
        checks["fileStorage"] = "READY" if writable else "UNAVAILABLE"
        if not writable:
            ready = False
    except Exception:
        checks["fileStorage"] = "UNAVAILABLE"
        ready = False

    payload = {
        "status": "READY" if ready else "NOT_READY",
        "product": "internship-standalone",
        "checks": checks,
    }
    if not ready:
        raise HTTPException(status_code=503, detail=payload)
    return payload
