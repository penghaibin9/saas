"""Student-owned read model for one returned AA-003 status-change resubmission.

The main `/mobile/academic/status/my` projection intentionally stays compact.  A returned
card that is about to be edited needs its exact optimistic-lock version and original
reason; expose those only for the owning student and only for RETURNED cases.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid, session
from app.services.mobile_student_service import _require_student, resolve_student


def get_my(user, change_id) -> dict:
    try:
        cid = int(change_id)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "changeId 非法") from exc

    from app.models import AaStatusChange

    with session() as db:
        student = resolve_student(db, _require_student(user))
        if not student:
            raise no_permission("尚未建立你的学生档案")
        row = db.scalars(select(AaStatusChange).where(
            AaStatusChange.id == cid,
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("异动单不存在")
        if int(row.student_id) != int(student.id):
            raise no_permission("该异动不属于当前学生本人")
        if str(row.status or "").upper() != "RETURNED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已退回的异动可修改重交", http_status=409)
        return {
            "changeId": str(row.id),
            "changeType": row.change_type,
            "reason": row.reason or "",
            "status": row.status,
            "currentNode": row.current_node or "",
            "version": int(row.version or 0),
            "decisionVersion": int(row.decision_version or 0),
            "toMajorId": str(row.to_major_id or ""),
            "toClassId": str(row.to_class_id or ""),
        }
