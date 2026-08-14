"""
审计日志
────────────────────────────────────────────────────────────
契约 §九：登录/登出、身份切换、审批、导入导出、敏感访问必须留痕。
DB 模式下 record() 写 t_security_audit_log；内存环形队列仅作为最近 N 条的快速视图，
不是事实源（进程重启即失，查询在 DB 模式下一律走库）。

两档语义：
- 普通动作：fire-and-forget，落库失败记 error + 计入 /health/ready，不阻塞业务；
- CRITICAL_ACTIONS 高危动作：落库失败抛 AuditPersistenceError，业务必须一起失败。

认证入口是 tenant-neutral：middleware 不再用 DEFAULT_TENANT_CODE 给登录请求伪造学校上下文。
LOGIN_* 事件在能够唯一识别真实账号/tenantCode 时由审计层解析真实 tenant_id；歧义账号不猜测。
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
_DB_HEALTH = {"lastFailure": None, "consecutiveFailures": 0}

CRITICAL_ACTIONS = frozenset({
    "TENANT_SUSPEND", "TENANT_RESUME", "TENANT_DELETE",
    "TENANT_PLAN_CHANGE", "TENANT_QUOTA_CHANGE",
    "ROLE_PERMISSION_CHANGE", "ROLE_DELETE", "ROLE_ASSIGN",
    "SENSITIVE_REVEAL", "BULK_EXPORT",
    "ADMIN_PASSWORD_RESET", "ACCOUNT_UNLOCK", "BREAK_GLASS",
    "PLATFORM_TENANT_ENABLE", "PLATFORM_TENANT_DISABLE",
    "PLATFORM_TENANT_EXTEND_TRIAL", "PLATFORM_TENANT_CONVERT_PAID",
    "PLATFORM_TENANT_EXPIRE", "PLATFORM_TENANT_CHANGE_PACKAGE",
    "PLATFORM_TENANT_QUOTA", "PLATFORM_PACKAGE_UPDATE",
    "PLATFORM_FEATURES_UPDATE", "PLATFORM_RULES_UPDATE",
    "PLATFORM_WORKFLOW_UPDATE", "PLATFORM_USER_ENABLE",
    "PLATFORM_USER_DISABLE", "PLATFORM_USER_RESET_PWD",
    "ROLE_PERMISSION_SAVE", "USER_ROLE_ASSIGN", "RESET_PASSWORD",
    "SENSITIVE_VIEW", "EXPORT",
    "ROLE_ASSIGNMENT_REVOKE", "ROLE_ASSIGNMENT_TRANSFER",
    "ROLE_ASSIGNMENT_REVIEW", "ROLE_ASSIGNMENT_EXPIRE",
    "ROLE_ASSIGNMENT_GRANT",
})


class AuditPersistenceError(RuntimeError):
    """高危审计未能落库。调用方必须让整个业务操作失败，不得吞掉。"""


def get_audit_db_health() -> dict:
    """审计落库健康状态快照，供 /health/ready 消费。"""
    return dict(_DB_HEALTH)


def _now_iso() -> str:
    tz = timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))
    return datetime.now(tz).isoformat(timespec="seconds")


def _resolve_login_event_tenant_id(action: str, resource: str, detail: dict) -> int | None:
    """Resolve a tenant for tenant-neutral LOGIN_* audit events without guessing.

    This deliberately mirrors the real password-login subject lookup: only active, non-deleted
    accounts in an active/trial tenant may establish audit ownership. Historical disabled copies
    must not make an otherwise unique live login appear ambiguous.

    - tenantCode present: require a login-eligible tenant, then match the active login_name there.
    - no tenantCode: only accept exactly one active account across all tenants.
    - ambiguous/missing account: return None; callers must not silently attach a random default school.
    """
    if not action.startswith("LOGIN_") or not str(resource or "").strip():
        return None
    try:
        from sqlalchemy import select
        from app.db.session import db_enabled, get_sessionmaker
        if not db_enabled():
            return None
        from app.models import Tenant, User

        db = get_sessionmaker()()
        try:
            login_name = str(resource).strip()
            tenant_code = str((detail or {}).get("tenantCode") or "").strip()
            stmt = select(User).where(
                User.login_name == login_name,
                User.is_deleted.is_(False),
                User.status == "ACTIVE",
            )
            if tenant_code:
                tenant = db.scalars(select(Tenant).where(
                    Tenant.tenant_code == tenant_code,
                    Tenant.status.in_(("ACTIVE", "TRIAL", "active", "trial")),
                )).first()
                if tenant is None:
                    return None
                user = db.scalars(stmt.where(User.tenant_id == tenant.id).limit(1)).first()
                return int(user.tenant_id) if user is not None else int(tenant.id)
            users = db.scalars(stmt.order_by(User.id).limit(2)).all()
            return int(users[0].tenant_id) if len(users) == 1 else None
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — audit caller applies critical/non-critical policy
        return None


def _effective_tenant_id(action: str, resource: str, detail: dict,
                         explicit_tenant_id: int | str | None) -> int | str | None:
    if explicit_tenant_id is not None:
        return explicit_tenant_id
    tenant = get_tenant() or {}
    context_tid = tenant.get("tenantId")
    if str(context_tid or "").isdigit():
        return context_tid
    return _resolve_login_event_tenant_id(action, resource, detail)


def record_critical_in_session(
    db, action: str, resource: str, *, detail: dict | None = None, result: str = "SUCCESS",
    tenant_id: int | str | None = None, resource_id: str | None = None,
    operator_name_override: str | None = None,
) -> dict:
    """把 critical audit 加入调用方 DB session；本函数绝不 commit、绝不吞错。"""
    if action not in CRITICAL_ACTIONS:
        raise ValueError(f"{action} 不是 CRITICAL_ACTIONS，禁止误用 critical in-session API")
    safe_detail = detail or {}
    effective_tid = _effective_tenant_id(action, resource, safe_detail, tenant_id)
    if effective_tid is None:
        raise AuditPersistenceError(f"高危动作 {action} 缺少可验证租户上下文")
    try:
        from app.services import db_service
        db_service.audit_insert_in_session(
            db, action, resource, safe_detail, result,
            tenant_id=int(effective_tid), resource_id=resource_id,
            operator_name_override=operator_name_override,
        )
        _DB_HEALTH["consecutiveFailures"] = 0
    except Exception as exc:  # noqa: BLE001 — critical audit 必须 fail-closed
        _DB_HEALTH["consecutiveFailures"] += 1
        _DB_HEALTH["lastFailure"] = {
            "occurredAt": _now_iso(), "action": action, "error": str(exc)[:200],
        }
        _logger.error(
            "同事务高危审计写入失败 action=%s resource=%s err=%s", action, resource, exc
        )
        raise AuditPersistenceError(
            f"高危动作 {action} 审计写入失败，业务事务必须回滚：{exc}"
        ) from exc
    return {
        "action": action, "resource": resource, "result": result,
        "tenantId": str(effective_tid), "detail": safe_detail,
    }


def record(action: str, resource: str, detail: dict | None = None, result: str = "SUCCESS",
           *, tenant_id: int | str | None = None) -> dict:
    """写一条审计。

    普通动作：fire-and-forget（任何异常不影响主流程）。
    CRITICAL_ACTIONS 中的高危动作：落库失败抛 AuditPersistenceError（fail-closed），
    调用方必须让业务一起失败——没有审计就不许留下这条业务事实。
    tenant_id：显式指定审计归属租户（平台超管跨租户操作时传"被操作学校"），
               不传则沿用请求上下文；tenant-neutral LOGIN_* 会按真实账号唯一解析。
    """
    global _SEQ
    critical = action in CRITICAL_ACTIONS
    safe_detail = detail or {}
    try:
        _SEQ += 1
        user = get_current_user_ctx() or {}
        effective_tid = _effective_tenant_id(action, resource, safe_detail, tenant_id)
        entry = {
            "auditId": f"audit-{_SEQ:06d}",
            "action": action,
            "resource": resource,
            "result": result,
            "actorId": user.get("userId"),
            "actorName": user.get("realName"),
            "tenantId": str(effective_tid) if effective_tid is not None else None,
            "requestId": get_trace_id(),
            "detail": safe_detail,
            "occurredAt": _now_iso(),
        }
        _LOGS.appendleft(entry)
        try:
            from app.db.session import db_enabled
            if db_enabled():
                if effective_tid is None:
                    raise RuntimeError("缺少可验证租户上下文，拒绝数据库审计写入")
                from app.services import db_service
                db_service.audit_insert(
                    action, resource, safe_detail, result, tenant_id=int(effective_tid)
                )
                _DB_HEALTH["consecutiveFailures"] = 0
            elif critical and settings.is_prod:
                raise AuditPersistenceError(f"高危动作 {action} 无可用审计落库通道")
        except Exception as e:  # noqa: BLE001
            _DB_HEALTH["consecutiveFailures"] += 1
            _DB_HEALTH["lastFailure"] = {
                "occurredAt": _now_iso(), "action": action, "error": str(e)[:200]
            }
            _logger.error("审计落库失败 action=%s resource=%s err=%s critical=%s",
                          action, resource, e, critical)
            if critical:
                raise AuditPersistenceError(
                    f"高危动作 {action} 审计落库失败，操作已拒绝：{e}") from e
        return entry
    except AuditPersistenceError:
        raise
    except Exception:  # noqa: BLE001
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
