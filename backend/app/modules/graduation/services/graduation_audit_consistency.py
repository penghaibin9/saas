"""毕业设计关键审计上下文修复。

历史登录上下文的 userId 可能是 ``db-123``，模型默认 ``int(userId)`` 会得到 None。
在 ORM 写入前统一解析稳定数据库用户 ID，并补齐 actor/context/role/permission/batch，
确保关键业务与同事务域审计之间不存在“业务成功、操作者为空”的记录。
"""
from __future__ import annotations

import re

from sqlalchemy import event

from app.core.context import (
    get_current_permission_code,
    get_current_request_context,
    get_current_user_ctx,
)
from app.models import GraduationAuditTrail

_INSTALLED = False


def _db_id(value) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    match = re.fullmatch(r"(?:db[-_:])?(\d+)", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _before_insert(_mapper, _connection, target: GraduationAuditTrail) -> None:
    user = get_current_user_ctx() or {}
    request = get_current_request_context() or {}
    if target.actor_user_id is None:
        target.actor_user_id = _db_id(
            user.get("userId") or user.get("id") or user.get("dbUserId") or user.get("accountId")
        )
    if not target.actor_context_id:
        value = user.get("contextId") or user.get("currentContextId")
        target.actor_context_id = str(value) if value not in (None, "") else None
    if not target.actor_name_snapshot:
        target.actor_name_snapshot = user.get("realName") or user.get("loginName")
    if not target.operator:
        target.operator = target.actor_name_snapshot
    if not target.role_code:
        target.role_code = user.get("currentRoleCode") or user.get("userType")
    if not target.role_name:
        target.role_name = user.get("currentRoleName") or target.role_code
    if not target.permission_code:
        target.permission_code = get_current_permission_code()
    if not target.request_id:
        target.request_id = request.get("traceId") or request.get("requestId")
    if not target.request_path:
        target.request_path = request.get("path")
    if not target.client_ip:
        target.client_ip = request.get("clientIp")
    if target.data_scope_snapshot is None:
        target.data_scope_snapshot = {
            "dataScope": user.get("dataScope"),
            "collegeId": user.get("collegeId"),
            "majorId": user.get("majorId"),
            "orgId": user.get("orgId"),
        }


def install_audit_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    event.listen(GraduationAuditTrail, "before_insert", _before_insert, propagate=True)
