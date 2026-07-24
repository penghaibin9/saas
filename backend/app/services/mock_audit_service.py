"""
审计服务
────────────────────────────────────────────────────────────
普通运行留痕：record() fire-and-forget，失败不阻断主业务。
高危审计：record_critical() / audit_insert_in_session() 必须成功，
与业务同事务或独立提交失败即抛错。
"""
from __future__ import annotations

import uuid

from app.core.context import current_tenant_id, get_current_user_ctx, get_trace_id
from app.core.response import paginate

_MAX = 500
_BUFFER: list[dict] = []

# 高危动作：必须落库成功
CRITICAL_ACTIONS = {
    "角色授权", "权限变更", "修改角色权限", "分配角色",
    "敏感导出", "SENSITIVE_EXPORT", "明文查看",
    "处分决定", "处分下达", "成绩发布", "成绩终审",
    "密码重置", "强制下线", "作废学生", "删除学生",
    "审批通过", "审批驳回", "资助发放", "发放确认",
}


def _now_iso() -> str:
    from app.core.timeutil import iso_utc, utc_now
    return iso_utc(utc_now()) or ""


def _is_critical(action: str) -> bool:
    a = (action or "").strip()
    if a in CRITICAL_ACTIONS:
        return True
    return any(k in a for k in ("授权", "敏感导出", "密码重置", "作废学生", "成绩发布", "资助发放"))


def record(action: str, *, method: str | None = None, path: str | None = None,
           status_code: int | None = None, target_type: str | None = None,
           target_id: str | None = None, detail: dict | None = None) -> None:
    """普通审计：失败不阻断。命中高危关键字时尽力强写；仍失败只告警（同事务请用 record_critical(db=...)）。"""
    if _is_critical(action):
        try:
            record_critical(action, method=method, path=path, status_code=status_code,
                            target_type=target_type, target_id=target_id, detail=detail)
            return
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger("app.audit").error(
                "CRITICAL_AUDIT_MISSING action=%s target=%s", action, target_id)
            _record_memory(action, method=method, path=path, status_code=status_code,
                           target_type=target_type, target_id=target_id, detail=detail)
            return
    _record_soft(action, method=method, path=path, status_code=status_code,
                 target_type=target_type, target_id=target_id, detail=detail)


def record_critical(action: str, *, method: str | None = None, path: str | None = None,
                    status_code: int | None = None, target_type: str | None = None,
                    target_id: str | None = None, detail: dict | None = None,
                    db=None) -> None:
    """高危审计：必须写入成功。可传入业务 db 会话实现同事务。"""
    _record_memory(action, method=method, path=path, status_code=status_code,
                   target_type=target_type, target_id=target_id, detail=detail)
    from app.db.session import db_enabled
    if not db_enabled():
        return
    from app.services import db_service
    payload = {"method": method, "path": path, "targetId": target_id, **(detail or {})}
    if db is not None:
        db_service.audit_insert_in_session(
            db, action, target_type or (path or ""), payload, "SUCCESS",
            resource_id=target_id)
        return
    db_service.audit_insert(action, target_type or (path or ""), payload, "SUCCESS",
                            resource_id=target_id)


def _record_memory(action, *, method=None, path=None, status_code=None,
                   target_type=None, target_id=None, detail=None) -> None:
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


def _record_soft(action: str, *, method=None, path=None, status_code=None,
                 target_type=None, target_id=None, detail=None) -> None:
    _record_memory(action, method=method, path=path, status_code=status_code,
                    target_type=target_type, target_id=target_id, detail=detail)
    try:
        from app.db.session import db_enabled
        if db_enabled():
            from app.services import db_service
            db_service.audit_insert(action, target_type or (path or ""),
                                    {"method": method, "path": path, "targetId": target_id,
                                     **(detail or {})}, "SUCCESS")
    except Exception:  # noqa: BLE001
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
