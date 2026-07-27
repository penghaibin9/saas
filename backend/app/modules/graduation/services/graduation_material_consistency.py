"""开题/成果材料链剩余事务一致性。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.models import GraduationFinal, GraduationProposal, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session

_INSTALLED = False


def hold_proposal_defense(proposal_id, result, comment=None) -> dict:
    from app.modules.graduation.services import graduation_service as svc

    result = str(result or "").upper()
    if result not in ("PASS", "FAIL"):
        raise AppException("VALIDATION_ERROR", "开题答辩结果必须是 PASS/FAIL")
    if result == "FAIL" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "开题答辩不通过时评语必填且不少于 5 字")
    with session() as db:
        proposal = db.scalars(select(GraduationProposal).where(
            GraduationProposal.id == int(proposal_id),
            GraduationProposal.tenant_id == _tid(),
            GraduationProposal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not proposal:
            raise not_found("开题材料不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == proposal.gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, student, "proposal.defense")
        if proposal.status != "APPROVED":
            raise AppException("DATA_CONFLICT", "仅书面开题审核通过后方可进行开题答辩")
        if proposal.defense_result:
            raise AppException("DATA_CONFLICT", "开题答辩结果已录入，请使用更正流程而不是覆盖")
        proposal.defense_result = result
        proposal.defense_comment = str(comment or "").strip() or None
        proposal.defense_at = datetime.now(timezone.utc)
        svc._audit(db, "PROPOSAL", proposal.id,
                   "开题答辩-" + ("通过" if result == "PASS" else "不通过"),
                   str(comment or "").strip(), "", result)
        db.commit()
        return {"id": str(proposal.id), "defenseResult": result}


def remind_final(gd_student_id, channel="站内消息") -> dict:
    from app.modules.graduation.services import graduation_service as svc

    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生档案不存在")
        assert_student_access(db, student, "final.remind")
        done = int(db.scalar(select(func.count()).select_from(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == student.id,
            GraduationFinal.is_deleted.is_(False),
        )) or 0)
        if done:
            raise AppException("DATA_CONFLICT", "该生已提交成果，无需催交")
        message = svc._deliver_student_reminder(
            db, student, task_name="毕业设计成果",
            action_key="graduation.final.submit", channel=channel,
        )
        svc._audit(db, "FINAL", f"remind-{student.id}", "成果催交",
                   f"已向学生账号 {message.receiver_user_id} 创建真实站内消息，消息ID={message.id}")
        db.commit()
        return {
            "gdStudentId": str(student.id), "studentName": student.name,
            "reminded": True, "deliveryStatus": "DELIVERED",
            "messageId": str(message.id), "todoId": None,
        }


def install_material_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    from app.modules.graduation.services import graduation_service as svc
    svc.hold_proposal_defense = hold_proposal_defense
    svc.remind_final = remind_final
