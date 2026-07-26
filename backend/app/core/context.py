"""
请求级上下文（contextvars）
────────────────────────────────────────────────────────────
承载一次请求内的 traceId、当前租户、当前用户、权限和岗位实习批次，供响应体、
日志、审计、数据范围与学生本人业务解析使用，无需层层透传参数。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
_tenant: ContextVar[Optional[dict]] = ContextVar("tenant", default=None)
_user: ContextVar[Optional[dict]] = ContextVar("current_user", default=None)
_permission_code: ContextVar[Optional[str]] = ContextVar("permission_code", default=None)
_internship_batch_id: ContextVar[Optional[str]] = ContextVar(
    "internship_batch_id", default=None)


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


def set_current_permission_code(code: Optional[str]) -> None:
    _permission_code.set(code)


def get_current_permission_code() -> Optional[str]:
    return _permission_code.get()


# ── 学生当前岗位实习批次 ──
def set_current_internship_batch_id(batch_id: Optional[str]) -> None:
    value = str(batch_id or "").strip()
    _internship_batch_id.set(value or None)


def get_current_internship_batch_id() -> Optional[str]:
    return _internship_batch_id.get()


# ── 请求元信息（P4 审计增强：ip / userAgent / method / path）──
_request_meta: ContextVar[Optional[dict]] = ContextVar("request_meta", default=None)


def set_request_meta(meta: Optional[dict]) -> None:
    _request_meta.set(meta)


def get_request_meta() -> dict:
    return _request_meta.get() or {}
