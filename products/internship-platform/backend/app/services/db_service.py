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
