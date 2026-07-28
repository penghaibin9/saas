"""成绩申诉复核的一致性状态机与真实消息通知。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import GraduationGrade, GraduationGradeAppeal, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session
from app.services.message_event_outbox_service import emit_message_event

def review_appeal(appeal_id, action, comment=None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    note = str(comment or "").strip()
    if action == "REJECT" and len(note) < 5:
        raise AppException("VALIDATION_ERROR", "驳回申诉理由必填且不少于 5 字")

    from app.modules.graduation.services import graduation_more_service as service

    with session() as db:
        appeal = db.scalars(select(GraduationGradeAppeal).where(
            GraduationGradeAppeal.id == int(appeal_id),
            GraduationGradeAppeal.tenant_id == _tid(),
            GraduationGradeAppeal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not appeal:
            raise not_found("申诉不存在")
        if appeal.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该申诉已复核，请刷新")

        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == appeal.gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise not_found("申诉对应的毕业设计学生不存在")
        assert_student_access(db, student, "grade.appeal.review")

        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == _tid(),
            GraduationGrade.gd_student_id == student.id,
            GraduationGrade.is_deleted.is_(False),
        ).with_for_update()).first()
        if action == "APPROVE" and (not grade or grade.status != "PUBLISHED"):
            raise AppException("DATA_CONFLICT", "成绩状态已变化，无法按原申诉直接撤回，请重新核对")

        operator, _ = service._op()
        now = datetime.now(timezone.utc)
        appeal.status = "APPROVED" if action == "APPROVE" else "REJECTED"
        appeal.active_key = None
        appeal.review_comment = note or None
        appeal.reviewed_by = operator
        appeal.reviewed_at = now

        if action == "APPROVE":
            reason = f"成绩申诉受理：{note or appeal.reason}"[:500]
            before_grade = grade.status
            grade.status = "WITHDRAWN"
            grade.withdraw_reason = reason
            grade.reviewed_at = None
            grade.version = int(grade.version or 0) + 1
            if student.stage == "COMPLETED":
                student.stage = "DEFENSE"
                student.version = int(student.version or 0) + 1
            service._audit(
                db, "GRADE", grade.id, "申诉受理后撤回成绩", reason,
            )
            from app.modules.graduation.services.graduation_risk_service import notify_risk_rescan
            notify_risk_rescan(db, student.id)
            result_text = "成绩申诉已受理，原成绩已撤回并进入重新核算流程"
            grade_transition = f"{before_grade}->WITHDRAWN"
        else:
            result_text = f"成绩申诉未通过：{note}"
            grade_transition = "UNCHANGED"

        outbox_id = None
        if student.student_id:
            outbox = emit_message_event(
                db,
                event_code="GRADUATION_DESIGN.GRADE_APPEAL_REVIEWED",
                source_module="graduation",
                source_biz_type="grade_appeal",
                source_biz_id=int(appeal.id),
                recipient_refs=[{"studentId": int(student.student_id)}],
                title="毕业设计成绩申诉处理结果",
                content=result_text,
                action_key="graduation.grade.view",
                action_params={"gdStudentId": str(student.id), "batchId": str(student.batch_id)},
                dedup_key=f"GRADUATION_DESIGN.GRADE_APPEAL_REVIEWED:{appeal.id}:{appeal.status}",
            )
            outbox_id = str(outbox.id)

        service._audit(
            db, "GRADE_APPEAL", appeal.id,
            "复核申诉-" + ("受理" if action == "APPROVE" else "驳回"),
            f"{note};grade={grade_transition};outbox={outbox_id or 'SKIPPED_NO_STUDENT_LINK'}",
        )
        db.commit()
        result = service._appeal_row(db, appeal)
        result.update({
            "gradeStatus": grade.status if grade else None,
            "studentStage": student.stage,
            "notificationQueued": bool(outbox_id),
            "outboxId": outbox_id,
        })
        return result
