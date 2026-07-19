"""
审计日志（占位实现）
────────────────────────────────────────────────────────────
契约 §九：登录/登出、身份切换、审批、导入导出、敏感访问必须留痕。
本阶段落内存环形队列；接库后替换为 t_security_audit / t_operation_audit_log 异步落库。
record() 的调用点与字段即为将来落库的埋点，路由层不需要再改。
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.context import get_current_user_ctx, get_tenant, get_trace_id

_MAX = 500
_LOGS: deque[dict] = deque(maxlen=_MAX)
_SEQ = 0
_logger = logging.getLogger("app.audit")
# 落库健康状态（历史欠账收口：落库失败此前 except: pass 静默吞掉，现记错误日志 + 暴露 /health/ready）。
_DB_HEALTH = {"lastFailure": None, "consecutiveFailures": 0}


def get_audit_db_health() -> dict:
    """审计落库健康状态快照，供 /health/ready 消费。"""
    return dict(_DB_HEALTH)


def _now_iso() -> str:
    tz = timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))
    return datetime.now(tz).isoformat(timespec="seconds")


def record(action: str, resource: str, detail: dict | None = None, result: str = "SUCCESS",
           *, tenant_id: int | str | None = None) -> dict:
    """写一条审计（fire-and-forget 语义：任何异常不影响主流程）。
    tenant_id：显式指定审计归属租户（平台超管跨租户操作时传"被操作学校"），
               不传则沿用请求上下文租户。"""
    global _SEQ
    try:
        _SEQ += 1
        user = get_current_user_ctx() or {}
        tenant = get_tenant() or {}
        entry = {
            "auditId": f"audit-{_SEQ:06d}",
            "action": action,              # LOGIN / LOGOUT / CONTEXT_SWITCH / IMPORT / EXPORT / FILE_UPLOAD ...
            "resource": resource,
            "result": result,              # SUCCESS / FAIL / DENIED
            "actorId": user.get("userId"),
            "actorName": user.get("realName"),
            "tenantId": str(tenant_id) if tenant_id is not None else tenant.get("tenantId"),
            "requestId": get_trace_id(),   # traceId = 审计表 request_id（契约 §二）
            "detail": detail or {},
            "occurredAt": _now_iso(),
        }
        _LOGS.appendleft(entry)
        try:
            from app.db.session import db_enabled
            if db_enabled():
                from app.services import db_service
                db_service.audit_insert(action, resource, detail, result,
                                        tenant_id=int(tenant_id) if tenant_id is not None else None)
                _DB_HEALTH["consecutiveFailures"] = 0
        except Exception as e:  # noqa: BLE001 — 审计落库失败不阻塞主业务，但必须留痕，不能无声无息
            _DB_HEALTH["consecutiveFailures"] += 1
            _DB_HEALTH["lastFailure"] = {"occurredAt": _now_iso(), "action": action, "error": str(e)[:200]}
            _logger.error("审计落库失败 action=%s resource=%s err=%s", action, resource, e)
        return entry
    except Exception:  # noqa: BLE001 — 审计绝不阻塞主业务
        return {}


def query(page: int = 1, page_size: int = 20, action: str | None = None,
          operator: str | None = None, date_from: str | None = None,
          date_to: str | None = None) -> tuple[list[dict], int]:
    from app.db.session import db_enabled
    if db_enabled():
        from app.services import db_service
        return db_service.audit_query(page, page_size, action, operator, date_from, date_to)
    items = [x for x in _LOGS if not action or x["action"] == action]
    total = len(items)
    start = (page - 1) * page_size
    return items[start:start + page_size], total
