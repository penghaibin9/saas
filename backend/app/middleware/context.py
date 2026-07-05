"""
请求上下文中间件
────────────────────────────────────────────────────────────
为每个请求分配/透传 traceId，解析当前租户写入上下文，回写 X-Trace-Id 响应头，
并记录一行访问日志。traceId 复用入站 X-Request-Id / X-Trace-Id（便于跨系统串联）。
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import set_current_user, set_request_meta, set_trace_id
from app.core.tenant_context import resolve_tenant

logger = logging.getLogger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id") or request.headers.get("x-trace-id")
        trace_id = (incoming or f"req-{uuid.uuid4().hex[:16]}")[:64]
        set_trace_id(trace_id)
        set_current_user(None)
        resolve_tenant(request)  # 多租户：解析并写入上下文（single 模式恒为默认租户）
        _bind_token_tenant(request)  # 令牌带 tenantId 时覆盖（demo 账号只见 demo-school 数据）
        set_request_meta({
            "ip": (request.client.host if request.client else "") or request.headers.get("x-forwarded-for", ""),
            "userAgent": request.headers.get("user-agent", "")[:400],
            "method": request.method,
            "path": request.url.path,
        })  # P4：审计落库补全 ip/ua/method/path

        deny = _expired_tenant_readonly_deny(request)  # P6：到期租户只读（写操作 403）
        if deny is None:
            deny = _demo_tenant_readonly_deny(request)  # P12：正式演示租户只读锁
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
        return response


def _bind_token_tenant(request: Request) -> None:
    """从 Authorization 令牌解出 tenantId 并覆盖上下文租户（在 async 上下文中 set，
    确保 contextvar 传播到所有 threadpool 依赖与端点；失败静默，走默认租户）。"""
    try:
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return
        from app.core.context import set_tenant
        from app.core.security import decode_token
        claims = decode_token(auth[7:].strip())
        if claims.get("tenantId"):
            set_tenant({"tenantId": str(claims["tenantId"]),
                        "tenantCode": claims.get("tid") or "",
                        "tenantName": claims.get("tenantName") or "",
                        "status": "ACTIVE"})
        elif claims.get("tid"):
            # 兼容旧令牌（只有租户码无 tenantId）：按令牌租户码绑定，
            # 确保已登录请求的数据租户只由令牌决定，X-Tenant 头无法越权切换。
            from app.core.tenant_context import get_mock_tenant
            t = get_mock_tenant(str(claims["tid"]).strip())
            if t:
                set_tenant(dict(t))
    except Exception:  # noqa: BLE001 — 非法令牌交由 get_current_user 统一处理
        return


# ── P6：到期租户只读控制 ──
_READONLY_EXEMPT_PREFIXES = (
    "/api/v1/auth", "/api/v1/platform", "/health", "/docs", "/openapi", "/redoc",
)

# ── P12：正式演示租户（demo-school）只读锁 ──
_DEMO_READONLY_TENANT_ID = "1000000000000000003"


def _demo_tenant_readonly_deny(request: Request):
    """正式演示租户数据不许改动：登录后的所有写操作（POST/PUT/PATCH/DELETE）返回 403，
    引导参观者去体验沙箱（sandbox-school）随意操作。auth/登录/登出/刷新不受限。"""
    try:
        from app.core.config import settings
        if not settings.demo_tenant_readonly:
            return None
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(_READONLY_EXEMPT_PREFIXES):
            return None
        from app.core.context import get_tenant
        tenant = get_tenant() or {}
        if str(tenant.get("tenantId") or "") != _DEMO_READONLY_TENANT_ID:
            return None
        from starlette.responses import JSONResponse
        from app.core.response import fail
        from app.services import audit_log
        audit_log.record("DEMO_READONLY_DENY", path,
                         detail={"method": request.method}, result="DENIED")
        return JSONResponse(status_code=403, content=fail(
            "NO_PERMISSION",
            "正式演示环境为只读，数据不可修改。想动手体验请用沙箱账号登录"
            "（学生 student2 / 教师 teacher2 / 管理员 admin2，密码 123456，每晚 0 点自动重置）"))
    except Exception:  # noqa: BLE001 — 只读锁自身故障不阻断业务
        return None


def _expired_tenant_readonly_deny(request: Request):
    """租户到期（trial/active 已过 expireAt 或被标记 expired）后：
    可登录、可查看（GET），所有写操作（POST/PUT/PATCH/DELETE）返回 403 MODULE_EXPIRED_READONLY。
    平台超管不受限；配置缺失/异常一律放行，绝不阻断正常业务。"""
    try:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        path = request.url.path
        if not path.startswith("/api/") or path.startswith(_READONLY_EXEMPT_PREFIXES):
            return None
        from app.core.context import get_current_user_ctx, get_tenant
        user = get_current_user_ctx() or {}
        if user.get("userType") == "PLATFORM_SUPER_ADMIN":
            return None
        tenant = get_tenant() or {}
        tid = tenant.get("tenantId")
        if not tid:
            return None
        from app.db.session import db_enabled
        if not db_enabled():
            return None
        from app.services.platform_service import tenant_status
        if tenant_status(int(tid)) != "expired":
            return None
        from starlette.responses import JSONResponse
        from app.core.response import fail
        from app.services import audit_log
        audit_log.record("WRITE_DENIED_EXPIRED", path,
                         detail={"method": request.method, "tenantId": str(tid)}, result="DENIED")
        return JSONResponse(status_code=403, content=fail(
            "MODULE_EXPIRED_READONLY",
            "服务已到期，当前为只读模式：可查看数据，无法新增或修改。续费请联系平台方 13549666867"))
    except Exception:  # noqa: BLE001 — 只读控制自身故障不阻断业务
        return None
