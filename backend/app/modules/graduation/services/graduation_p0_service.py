"""Small, isolated P0 fixes for legacy graduation endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import not_found
from app.models import GraduationAuditTrail, GraduationGuidance, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session


def void_guidance_scoped(guidance_id, reason: str) -> dict:
    """Void a guidance record only after locking it and authorizing its student."""
    with session() as db:
        row = db.scalars(select(GraduationGuidance).where(
            GraduationGuidance.id == int(guidance_id),
            GraduationGuidance.tenant_id == _tid(),
            GraduationGuidance.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("指导记录不存在")
        student = db.get(GraduationStudent, row.gd_student_id)
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("毕设学生不存在或不在当前数据范围内")
        assert_student_access(db, student, "guidance.update")

        row.is_deleted = True
        row.void_reason = reason.strip()
        db.add(GraduationAuditTrail(
            tenant_id=_tid(), biz_type="GUIDANCE", biz_id=str(row.id),
            action="撤销指导记录", detail=reason.strip(),
            before_val="ACTIVE", after_val="VOIDED",
            before_json={"status": "ACTIVE", "gdStudentId": str(student.id)},
            after_json={"status": "VOIDED", "gdStudentId": str(student.id)},
            batch_id=student.batch_id,
            occurred_at=datetime.now(timezone.utc),
        ))
        db.commit()
        return {"id": str(row.id), "gdStudentId": str(student.id), "voided": True}
