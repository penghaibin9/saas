"""
请求上下文中间件
────────────────────────────────────────────────────────────
为每个请求分配/透传 traceId，解析当前租户写入上下文，回写 X-Trace-Id 响应头，
并记录一行访问日志。学生岗位实习请求可通过 X-Internship-Batch-Id 显式绑定
当前批次，后端所有本人业务共享同一事实源。
"""
from __future__ import annotations

import logging
import time
import uuid
from functools import lru_cache

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import (
    set_current_internship_batch_id,
    set_current_user,
    set_request_meta,
    set_trace_id,
)
from app.core.config import settings
from app.core.tenant_context import resolve_tenant

logger = logging.getLogger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id") or request.headers.get("x-trace-id")
        trace_id = (incoming or f"req-{uuid.uuid4().hex[:16]}")[:64]
        set_trace_id(trace_id)
        set_current_user(None)
        set_current_internship_batch_id(_resolve_internship_batch_id(request))
        resolve_tenant(request)
        _bind_token_tenant(request)
        set_request_meta({
            "ip": _resolve_client_ip(request),
            "userAgent": request.headers.get("user-agent", "")[:400],
            "method": request.method,
            "path": request.url.path,
            "internshipBatchId": _resolve_internship_batch_id(request) or "",
        })

        deny = _expired_tenant_readonly_deny(request)
        if deny is None:
            deny = _demo_tenant_readonly_deny(request)
        if deny is not None:
            deny.headers["X-Trace-Id"] = trace_id
            return deny

        start = time.perf_counter()
        response = await call_next(request)
        cost_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "http_access",
            extra={"trace_id": trace_id, "method": request.method,
                   "path": request.url.path, "status": response.status_code, "ms": cost_ms},
        )
        from app.core.runtime_metrics import record_request
        record_request(request.url.path, response.status_code, cost_ms, settings.HTTP_SLOW_REQUEST_MS)
        if cost_ms >= settings.HTTP_SLOW_REQUEST_MS:
            logger.warning("slow_http trace_id=%s method=%s path=%s status=%s ms=%s",
                           trace_id, request.method, request.url.path, response.status_code, cost_ms)
        return response


def _resolve_internship_batch_id(request: Request) -> str | None:
    """只接受学生岗位实习域的显式批次头，避免其它域或教师接口误绑定。"""
    path = request.url.path
    if not (
        path.startswith("/api/v1/mobile/internship") or
        path.startswith("/api/v1/portal/internship")
    ):
        return None
    raw = (request.headers.get("x-internship-batch-id") or "").strip()
    if not raw:
        return None
    if len(raw) > 32 or not raw.isdigit():
        return None
    return raw


@lru_cache(maxsize=8)
def _trusted_networks(spec: str) -> tuple:
    import ipaddress
    nets = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return tuple(nets)


def _is_trusted_proxy(direct: str, spec: str) -> bool:
    import ipaddress
    try:
        addr = ipaddress.ip_address(direct)
    except ValueError:
        return False
    return any(addr in net for net in _trusted_networks(spec))


def _resolve_client_ip(request: Request) -> str:
    direct = request.client.host if request.client else ""
    try:
        from app.core.config import settings
        if direct and _is_trusted_proxy(direct, settings.TRUSTED_PROXY_IPS):
            fwd = request.headers.get("x-forwarded-for", "")
            if fwd:
                first = fwd.split(",")[0].strip()
                if first:
                    return first[:64]
            real = request.headers.get("x-real-ip", "").strip()
            if real:
                return real[:64]
    except Exception:
        pass
    return direct


def _bind_token_tenant(request: Request) -> None:
    try:
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return
        from app.core.context import set_tenant
        from app.core.security import decode_token
        claims = decode_token(auth[7:].strip())
        set_current_user({
            "userId": claims.get("userId"), "realName": claims.get("realName"),
            "userType": claims.get("userType"), "tenantCode": claims.get("tid"),
            "tenantId": claims.get("tenantId"),
            "activeContextId": claims.get("activeContextId"),
            "currentRoleCode": claims.get("currentRoleCode"),
            "permissionVersion": claims.get("permissionVersion"),
            "loginName": claims.get("loginName") or claims.get("username"),
            "studentNo": claims.get("studentNo"),
            "collegeId": claims.get("collegeId"),
            "collegeIds": claims.get("collegeIds"),
            "majorId": claims.get("majorId"),
            "majorIds": claims.get("majorIds"),
            "tokenJti": claims.get("jti"), "tokenExp": claims.get("exp"),
        })
        if claims.get("tenantId"):
            set_tenant({"tenantId": str(claims["tenantId"]),
                        "tenantCode": claims.get("tid") or "",
                        "tenantName": claims.get("tenantName") or "",
                        "status": "ACTIVE"})
        elif claims.get("tid"):
            from app.core.tenant_context import get_mock_tenant
            t = get_mock_tenant(str(claims["tid"]).strip())
            if t:
                set_tenant(dict(t))
    except Exception:
        return


_READONLY_EXEMPT_PREFIXES = (
    "/api/v1/auth", "/api/v1/platform", "/health", "/docs", "/openapi", "/redoc",
)
_DEMO_READONLY_TENANT_ID = "1000000000000000003"


def is_readonly_tenant(tenant: dict | None = None) -> bool:
    try:
        from app.core.config import settings
        if not settings.demo_tenant_readonly:
            return False
        if tenant is None:
            from app.core.context import get_tenant
            tenant = get_tenant() or {}
        return str((tenant or {}).get("tenantId") or "") == _DEMO_READONLY_TENANT_ID
    except Exception:
        return False


def _demo_tenant_readonly_deny(request: Request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    path = request.url.path
    if not path.startswith("/api/") or path.startswith(_READONLY_EXEMPT_PREFIXES):
        return None
    try:
        from app.core.config import settings
        if not settings.demo_tenant_readonly:
            return None
        from app.core.context import get_tenant
        tenant = get_tenant() or {}
        if str(tenant.get("tenantId") or "") != _DEMO_READONLY_TENANT_ID:
            return None
    except Exception:
        from starlette.responses import JSONResponse
        from app.core.response import fail
        return JSONResponse(status_code=503, content=fail(
            "TENANT_GUARD_UNAVAILABLE", "租户只读守卫暂时不可用，请稍后重试"))
    try:
        from starlette.responses import JSONResponse
        from app.core.response import fail
        from app.services import audit_log
        try:
            audit_log.record("DEMO_READONLY_DENY", path,
                             detail={"method": request.method}, result="DENIED")
        except Exception:
            pass
        return JSONResponse(status_code=403, content=fail(
            "NO_PERMISSION",
            "正式演示环境为只读，数据不可修改。想动手体验请使用沙箱环境"))
    except Exception:
        from starlette.responses import JSONResponse
        from app.core.response import fail
        return JSONResponse(status_code=503, content=fail(
            "TENANT_GUARD_UNAVAILABLE", "租户只读守卫暂时不可用，请稍后重试"))


def _expired_tenant_readonly_deny(request: Request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    path = request.url.path
    if not path.startswith("/api/") or path.startswith(_READONLY_EXEMPT_PREFIXES):
        return None
    try:
        from app.core.context import get_current_user_ctx, get_tenant
        from app.core.permissions import is_super_admin
        user = get_current_user_ctx() or {}
        if is_super_admin(user) and user.get("userId"):
            return None
        tenant = get_tenant() or {}
        tid = tenant.get("tenantId")
        if not tid:
            return None
        from app.db.session import db_enabled
        if not db_enabled():
            return None
        from app.services.platform_service import tenant_status
        status = tenant_status(int(tid), strict=True)
        if status != "expired":
            return None
    except Exception:
        from starlette.responses import JSONResponse
        from app.core.response import fail
        return JSONResponse(status_code=503, content=fail(
            "TENANT_GUARD_UNAVAILABLE", "租户状态守卫暂时不可用，请稍后重试"))
    try:
        from starlette.responses import JSONResponse
        from app.core.response import fail
        from app.services import audit_log
        try:
            audit_log.record("WRITE_DENIED_EXPIRED", path,
                             detail={"method": request.method, "tenantId": str(tid)}, result="DENIED")
        except Exception:
            pass
        return JSONResponse(status_code=403, content=fail(
            "MODULE_EXPIRED_READONLY",
            "服务已到期，当前为只读模式：可查看数据，无法新增或修改。请联系平台运营续费"))
    except Exception:
        from starlette.responses import JSONResponse
        from app.core.response import fail
        return JSONResponse(status_code=503, content=fail(
            "TENANT_GUARD_UNAVAILABLE", "租户状态守卫暂时不可用，请稍后重试"))
