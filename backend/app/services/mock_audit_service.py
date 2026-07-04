"""
mock 审计服务（预留）
────────────────────────────────────────────────────────────
内存环形缓冲，演示「操作留痕责任链」。写操作接口显式调用 record()，
GET /audit/logs 读取。审计表 append-only、不可变（DB 冻结册 §16：t_security_audit /
t_operation_audit_log，无 is_deleted）。真实接库后 record() 改为异步落库。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.context import current_tenant_id, get_current_user_ctx, get_trace_id
from app.core.response import paginate

_MAX = 500
_BUFFER: list[dict] = []


def _now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))).isoformat(timespec="seconds")


def record(action: str, *, method: str | None = None, path: str | None = None,
           status_code: int | None = None, target_type: str | None = None,
           target_id: str | None = None, detail: dict | None = None) -> None:
    user = get_current_user_ctx() or {}
    entry = {
        "id": f"aud_{uuid.uuid4().hex[:12]}",
        "traceId": get_trace_id(),
        "tenantId": current_tenant_id(),
        "userId": user.get("userId"),
        "realName": user.get("realName"),
        "roleCode": user.get("currentRoleCode"),
        "action": action,
        "method": method,
        "path": path,
        "targetType": target_type,
        "targetId": target_id,
        "statusCode": status_code,
        "detail": detail,
        "occurredAt": _now_iso(),
    }
    _BUFFER.insert(0, entry)
    del _BUFFER[_MAX:]
    try:
        from app.db.session import db_enabled
        if db_enabled():
            from app.services import db_service
            db_service.audit_insert(action, target_type or (path or ""),
                                    {"method": method, "path": path, "targetId": target_id,
                                     **(detail or {})}, "SUCCESS")
    except Exception:  # noqa: BLE001 — 审计落库失败不阻塞主业务
        pass


def _seed() -> None:
    if _BUFFER:
        return
    samples = [
        {"action": "登录", "method": "POST", "path": "/api/v1/auth/mock-login", "targetType": "auth"},
        {"action": "切换身份", "method": "POST", "path": "/api/v1/auth/switch-role", "targetType": "authz"},
        {"action": "导出学生名单", "method": "POST", "path": "/api/v1/export/create-placeholder", "targetType": "export"},
    ]
    for i, s in enumerate(samples):
        _BUFFER.append({
            "id": f"aud_seed_{i}", "traceId": f"req-seed{i:04d}", "tenantId": "1000000000000000001",
            "userId": "u_admin_001", "realName": "教务处·赵敏", "roleCode": "SCHOOL_ADMIN",
            "action": s["action"], "method": s["method"], "path": s["path"],
            "targetType": s["targetType"], "targetId": None, "statusCode": 200, "detail": None,
            "occurredAt": _now_iso(),
        })


def list_logs(action: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    _seed()
    rows = _BUFFER
    if action:
        rows = [r for r in rows if action in (r.get("action") or "")]
    total = len(rows)
    start = (page - 1) * page_size
    return paginate(rows[start:start + page_size], total, page, page_size)
