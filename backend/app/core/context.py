"""
请求级上下文（contextvars）
────────────────────────────────────────────────────────────
承载一次请求内的 traceId、当前租户、当前用户，供响应体、日志、
审计、数据范围等处随时读取，无需层层透传参数。
- traceId  → 统一响应 traceId / 审计 request_id（对齐冻结契约 §二）
- tenant   → 多租户行级隔离（单库单 schema + tenant_id，对齐 DB 冻结册 §10）
- user     → 当前登录用户 + 当前身份 active_context
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
_tenant: ContextVar[Optional[dict]] = ContextVar("tenant", default=None)
_user: ContextVar[Optional[dict]] = ContextVar("current_user", default=None)


# ── traceId ──
def set_trace_id(value: str) -> None:
    _trace_id.set(value)


def get_trace_id() -> str:
    return _trace_id.get()


# ── 当前租户 ──
def set_tenant(tenant: Optional[dict]) -> None:
    _tenant.set(tenant)


def get_tenant() -> Optional[dict]:
    return _tenant.get()


def current_tenant_id() -> Optional[str]:
    t = _tenant.get()
    return t.get("tenantId") if t else None


# ── 当前用户 ──
def set_current_user(user: Optional[dict]) -> None:
    _user.set(user)


def get_current_user_ctx() -> Optional[dict]:
    return _user.get()


# ── 请求元信息（P4 审计增强：ip / userAgent / method / path）──
_request_meta: ContextVar[Optional[dict]] = ContextVar("request_meta", default=None)


def set_request_meta(meta: Optional[dict]) -> None:
    _request_meta.set(meta)


def get_request_meta() -> dict:
    return _request_meta.get() or {}
