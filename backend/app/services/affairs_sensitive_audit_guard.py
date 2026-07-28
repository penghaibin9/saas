"""心理明细强敏感访问的 fail-closed 审计与权限门禁。

公共 audit_log.record() 为全局 fire-and-forget 设计，会吞掉落库异常；心理原文属于强敏感数据，
必须同时满足显式明细权限、逐生范围、查看原因与审计成功，任一失败都不得返回原文。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.core.permissions import has_permission


def strict_sensitive_view_audit(student_id, reason: str, resource: str) -> None:
    from app.services import audit_log

    before = audit_log.get_audit_db_health()
    entry = audit_log.record(
        "SENSITIVE_VIEW",
        resource,
        detail={
            "domain": "MENTAL",
            "studentId": str(student_id),
            "reason": str(reason)[:200],
        },
        result="SUCCESS",
    )
    after = audit_log.get_audit_db_health()
    failed_this_call = (
        not entry
        or int(after.get("consecutiveFailures") or 0) > int(before.get("consecutiveFailures") or 0)
    )
    if failed_this_call:
        raise AppException(
            "SERVER_ERROR",
            "敏感信息访问审计暂不可用，已拒绝返回心理明细",
            http_status=503,
        )


# 明细角色与逐生范围由 affairs_mental_service._can_view_detail 正式实现；
# 本守卫只负责把审计改为 fail-closed，禁止再次覆盖角色边界。

def install() -> None:
    from app.services import affairs_mental_service as mental
    mental._sensitive_view_audit = strict_sensitive_view_audit
    mental._can_view_detail = explicit_detail_permission
