"""心理明细强敏感访问的 fail-closed 审计门禁。

公共 audit_log.record() 为全局 fire-and-forget 设计，会吞掉落库异常；心理原文属于强敏感数据，
必须额外核验本次审计落库健康，失败时返回 503 而不是继续泄露明文。
"""
from __future__ import annotations

from app.core.exceptions import AppException


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
    # record 外层失败会返回空字典；本次数据库写失败会增加连续失败计数并记录 lastFailure。
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


def install() -> None:
    from app.services import affairs_mental_service as mental
    mental._sensitive_view_audit = strict_sensitive_view_audit
