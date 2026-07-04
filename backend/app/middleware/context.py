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
    except Exception:  # noqa: BLE001 — 非法令牌交由 get_current_user 统一处理
        return
