from __future__ import annotations
from datetime import datetime
from app.core.context import current_tenant_id as _current
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
def current_tenant_id():return _current()
def _tid():
    value=int(_current() or 0)
    if not value:raise AppException("TENANT_CONTEXT_REQUIRED","缺少租户上下文",http_status=403)
    return value
def _as_id(value):
    try:return int(value)
    except Exception:
        from app.core.exceptions import not_found
        raise not_found("资源不存在或标识不合法")
def _iso(value):
    from app.core.timeutil import iso_utc
    return iso_utc(value) if isinstance(value,datetime) else str(value) if value else None
def session():return get_sessionmaker()()

from app.core.context import get_current_user_ctx, get_request_meta, get_trace_id
from app.core.audit_payload import sanitize_audit_payload
from app.models.audit import SecurityAuditLog


def audit_insert_in_session(db, action: str, resource: str, detail: dict | None, result: str,
                            *, tenant_id: int | None = None, resource_id: str | None = None,
                            operator_name_override: str | None = None,
                            actor_override: dict | None = None,
                            request_meta_override: dict | None = None,
                            source_event_id: str | None = None) -> None:
    """Add only: caller owns flush/commit. Worker identity never replaces the event actor."""
    user = (get_current_user_ctx() or {}) if actor_override is None else actor_override
    meta = get_request_meta() if request_meta_override is None else request_meta_override
    raw_uid = str(user.get("userId") or "").removeprefix("db-")
    operator_id = int(raw_uid) if raw_uid.isascii() and raw_uid.isdigit() else None
    if operator_id is not None and not 0 < operator_id < 2**63:
        operator_id = None
    tid = int(tenant_id) if tenant_id is not None else _tid()
    if tid <= 0:
        raise ValueError("A trusted positive audit tenant is required")
    safe_meta = sanitize_audit_payload(meta)
    db.add(SecurityAuditLog(
        tenant_id=tid, source_event_id=source_event_id,
        operator_id=operator_id,
        operator_name=operator_name_override if operator_name_override is not None else user.get("realName"),
        current_role=user.get("currentRoleCode"), action=action, resource=resource,
        resource_id=resource_id, ip=safe_meta.get("ip"), user_agent=safe_meta.get("userAgent"),
        request_method=safe_meta.get("method"), request_path=safe_meta.get("path"),
        trace_id=meta.get("traceId") if request_meta_override is not None else get_trace_id(),
        result=result, detail_json=sanitize_audit_payload(detail or {}),
    ))
