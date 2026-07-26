from __future__ import annotations

from collections.abc import Iterable

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import enforce_permission
from app.models import GraduationBatch, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid


def authorize_student_action(
    db,
    student: GraduationStudent | None,
    *,
    action: str,
    permission_code: str,
    allowed_student_states: Iterable[str] | None = None,
    allowed_batch_states: Iterable[str] | None = None,
) -> GraduationStudent:
    """Apply permission, tenant, batch, org scope, role/relation and state checks."""
    user = get_current_user_ctx() or {}
    enforce_permission(user, permission_code)
    if not student or student.is_deleted or student.tenant_id != _tid():
        raise not_found("毕业设计学生档案不存在")
    if (user.get("currentRoleCode") or user.get("userType") or "").upper() == "STUDENT":
        raise no_permission("学生账号不能执行管理端操作")
    batch = db.get(GraduationBatch, student.batch_id) if student.batch_id else None
    if not batch or batch.is_deleted or batch.tenant_id != _tid():
        raise no_permission("学生未关联当前租户的有效毕业设计批次")
    if allowed_batch_states and batch.status not in set(allowed_batch_states):
        raise AppException("DATA_CONFLICT", f"当前批次状态不允许执行{action}")
    if allowed_student_states and student.stage not in set(allowed_student_states):
        raise AppException("DATA_CONFLICT", f"学生当前阶段不允许执行{action}")
    return assert_student_access(db, student, action)
