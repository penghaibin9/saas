"""
审计日志
────────────────────────────────────────────────────────────
契约 §九：登录/登出、身份切换、审批、导入导出、敏感访问必须留痕。
DB 模式下 record() 写 t_security_audit_log；内存环形队列仅作为最近 N 条的快速视图，
不是事实源（进程重启即失，查询在 DB 模式下一律走库）。

两档语义：
- 普通动作：fire-and-forget，落库失败记 error + 计入 /health/ready，不阻塞业务；
- CRITICAL_ACTIONS 高危动作：落库失败抛 AuditPersistenceError，业务必须一起失败。
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

# ── 高危动作：审计落库失败必须 fail-closed ──────────────────────────
# 普通动作（看了个页面）丢一条审计可以接受；下列动作不行——
# "业务 COMMIT 成功 + 审计 INSERT 失败 + 接口仍返回成功" 等于销毁了唯一的责任证据。
# 命中时 record() 会把落库异常抛给调用方，由上层回滚/返回失败。
#
# 注意：这里同时保留历史动作名和当前生产路由真正发出的动作名。此前只列了抽象名，
# 实际 PLATFORM_TENANT_DISABLE / ROLE_PERMISSION_SAVE / EXPORT 等完全命不中，导致
# “看起来启用了 fail-closed，真实高危操作仍 fail-open”。
CRITICAL_ACTIONS = frozenset({
    # 历史/兼容动作名
    "TENANT_SUSPEND", "TENANT_RESUME", "TENANT_DELETE",
    "TENANT_PLAN_CHANGE", "TENANT_QUOTA_CHANGE",
    "ROLE_PERMISSION_CHANGE", "ROLE_DELETE", "ROLE_ASSIGN",
    "SENSITIVE_REVEAL", "BULK_EXPORT",
    "ADMIN_PASSWORD_RESET", "ACCOUNT_UNLOCK", "BREAK_GLASS",
    # 平台控制面真实动作名
    "PLATFORM_TENANT_ENABLE", "PLATFORM_TENANT_DISABLE",
    "PLATFORM_TENANT_EXTEND_TRIAL", "PLATFORM_TENANT_CONVERT_PAID",
    "PLATFORM_TENANT_EXPIRE", "PLATFORM_TENANT_CHANGE_PACKAGE",
    "PLATFORM_TENANT_QUOTA", "PLATFORM_PACKAGE_UPDATE",
    "PLATFORM_FEATURES_UPDATE", "PLATFORM_RULES_UPDATE",
    "PLATFORM_WORKFLOW_UPDATE", "PLATFORM_USER_ENABLE",
    "PLATFORM_USER_DISABLE", "PLATFORM_USER_RESET_PWD",
    # 学校端真实动作名
    "ROLE_PERMISSION_SAVE", "USER_ROLE_ASSIGN", "RESET_PASSWORD",
    "SENSITIVE_VIEW", "EXPORT",
})


class AuditPersistenceError(RuntimeError):
    """高危审计未能落库。调用方必须让整个业务操作失败，不得吞掉。"""


def get_audit_db_health() -> dict:
    """审计落库健康状态快照，供 /health/ready 消费。"""
    return dict(_DB_HEALTH)


def _now_iso() -> str:
    tz = timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))
    return datetime.now(tz).isoformat(timespec="seconds")


def record(action: str, resource: str, detail: dict | None = None, result: str = "SUCCESS",
           *, tenant_id: int | str | None = None) -> dict:
    """写一条审计。

    普通动作：fire-and-forget（任何异常不影响主流程）。
    CRITICAL_ACTIONS 中的高危动作：落库失败抛 AuditPersistenceError（fail-closed），
    调用方必须让业务一起失败——没有审计就不许留下这条业务事实。
    tenant_id：显式指定审计归属租户（平台超管跨租户操作时传"被操作学校"），
               不传则沿用请求上下文租户。"""
    global _SEQ
    critical = action in CRITICAL_ACTIONS
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
            elif critical and settings.is_prod:
                # 生产环境高危动作没有持久化审计目的地 = 不许发生。
                raise AuditPersistenceError(f"高危动作 {action} 无可用审计落库通道")
        except Exception as e:  # noqa: BLE001 — 普通动作不阻塞主业务，但必须留痕，不能无声无息
            _DB_HEALTH["consecutiveFailures"] += 1
            _DB_HEALTH["lastFailure"] = {"occurredAt": _now_iso(), "action": action, "error": str(e)[:200]}
            _logger.error("审计落库失败 action=%s resource=%s err=%s critical=%s",
                          action, resource, e, critical)
            if critical:
                raise AuditPersistenceError(
                    f"高危动作 {action} 审计落库失败，操作已拒绝：{e}") from e
        return entry
    except AuditPersistenceError:
        raise  # fail-closed 语义必须穿透最外层兜底
    except Exception:  # noqa: BLE001 — 普通审计绝不阻塞主业务
        if critical:
            raise
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
