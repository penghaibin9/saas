"""Stage C1 formal student-profile lifecycle writes backed by StudentAcademicFact."""
from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException


def void_student(student_id: str, reason: str) -> dict:
    """Void a student without bypassing the temporal academic fact ledger."""
    from app.models import StudentProfile, StudentStageEvent
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
        append_student_academic_fact,
    )
    from app.services import db_service
    from app.services import student_account_link_service as link_svc

    why = str(reason or "").strip()
    if len(why) < 2:
        raise AppException("VALIDATION_ERROR", "请填写作废原因")

    tenant_id = db_service._tid()
    actor = get_current_user_ctx() or {}
    with db_service.session() as db:
        s = db.query(StudentProfile).filter(
            StudentProfile.id == db_service._as_id(student_id),
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        ).with_for_update().first()
        if not s:
            raise AppException("DATA_NOT_FOUND", "学生不存在或已作废")

        from_status = s.student_status or "NORMAL"
        if from_status != "RECYCLED":
            _fact, s = append_student_academic_fact(
                db,
                int(s.id),
                student_status="RECYCLED",
                source_type="PROFILE_VOID",
                expected_student_version=int(s.version or 0),
                created_by=(int(actor.get("userId")) if str(actor.get("userId") or "").isdigit() else None),
            )
        s.is_deleted = True
        s.status = "INACTIVE"
        s.remark = f"VOID:{why}"
        db.add(StudentStageEvent(
            tenant_id=tenant_id,
            student_id=s.id,
            from_stage=s.current_stage,
            to_stage="RECYCLED",
            reason=why,
            source_module="student",
        ))
        link_svc.suspend_by_student_in_session(
            db,
            tenant_id=tenant_id,
            student_id=s.id,
            remark=f"学籍作废：{why}",
        )
        db_service.audit_insert_in_session(
            db,
            "作废学生",
            "student",
            {
                "reason": why,
                "studentNo": s.student_no,
                "fromStudentStatus": from_status,
                "academicFactVersion": int(_fact.version_no) if from_status != "RECYCLED" else None,
                "operator": actor.get("realName") or "",
                "roleCode": actor.get("currentRoleCode") or "",
            },
            "SUCCESS",
            resource_id=str(s.id),
        )
        db.commit()
        return {
            "studentId": str(s.id),
            "studentStatus": "RECYCLED",
            "isDeleted": True,
            "physicalDelete": False,
        }
