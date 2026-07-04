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

from app.core.context import set_current_user, set_trace_id
from app.core.tenant_context import resolve_tenant

logger = logging.getLogger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id") or request.headers.get("x-trace-id")
        trace_id = (incoming or f"req-{uuid.uuid4().hex[:16]}")[:64]
        set_trace_id(trace_id)
        set_current_user(None)
        resolve_tenant(request)  # 多租户：解析并写入上下文（single 模式恒为默认租户）

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
