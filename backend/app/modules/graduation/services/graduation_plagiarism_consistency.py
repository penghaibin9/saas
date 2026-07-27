"""查重复查申请的一次性状态机与真实通知。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import GraduationFinal, GraduationPlagiarismCheck, GraduationStudent
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session
from app.services.message_event_outbox_service import emit_message_event

_INSTALLED = False


def dispute_plagiarism(pid, reason: str) -> dict:
    note = str(reason or "").strip()
    if len(note) < 5:
        raise AppException("VALIDATION_ERROR", "复查理由必填且不少于 5 字")
    from app.modules.graduation.services import graduation_review_service as service

    with session() as db:
        check = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.id == int(pid),
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.is_deleted.is_(False),
        ).with_for_update()).first()
        if not check:
            raise not_found("查重记录不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == check.gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        assert_student_access(db, student, "plagiarism.dispute")
        if check.status != "DONE" or not check.over_threshold:
            raise AppException("DATA_CONFLICT", "仅已完成且超标的查重记录可申请复查")
        if check.dispute_status == "PENDING":
            if (check.dispute_reason or "").strip() == note:
                return service._plag_row(check, student)
            raise AppException("DATA_CONFLICT", "该查重记录已有待处理复查申请")
        if check.dispute_status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该查重记录的复查申请已处理；如新的复查结果仍超标，请针对新记录另行申请")
        check.dispute_reason = note
        check.dispute_status = "PENDING"
        check.dispute_comment = None
        service._audit(db, "PLAGIARISM", check.id, "申请复查", note)
        db.commit()
        return service._plag_row(check, student)


def review_dispute(pid, action: str, comment: str | None = None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    note = str(comment or "").strip()
    if action == "REJECT" and len(note) < 5:
        raise AppException("VALIDATION_ERROR", "驳回复查申请须填写不少于 5 字的理由")

    from app.modules.graduation.services import graduation_review_service as service

    with session() as db:
        check = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.id == int(pid),
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.is_deleted.is_(False),
        ).with_for_update()).first()
        if not check:
            raise not_found("查重记录不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == check.gd_student_id,
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        assert_student_access(db, student, "plagiarism.dispute.review")
        if check.dispute_status != "PENDING":
            raise AppException("DATA_CONFLICT", "无待处理的复查申请")

        recheck = None
        if action == "APPROVE":
            if not check.gd_final_id:
                raise AppException("DATA_CONFLICT", "原查重任务未绑定成果，无法创建复查任务")
            final = db.scalars(select(GraduationFinal).where(
                GraduationFinal.id == int(check.gd_final_id),
                GraduationFinal.tenant_id == _tid(),
                GraduationFinal.gd_student_id == student.id,
                GraduationFinal.is_deleted.is_(False),
            ).with_for_update()).first()
            if not final:
                raise AppException("DATA_CONFLICT", "原成果不存在，无法创建复查任务")
            active = db.scalars(select(GraduationPlagiarismCheck).where(
                GraduationPlagiarismCheck.tenant_id == _tid(),
                GraduationPlagiarismCheck.gd_final_id == final.id,
                GraduationPlagiarismCheck.status == "CHECKING",
                GraduationPlagiarismCheck.is_deleted.is_(False),
            ).with_for_update()).first()
            if active:
                raise AppException("DATA_CONFLICT", "该成果已有进行中的查重或复查任务")
            existing_recheck = db.scalars(select(GraduationPlagiarismCheck).where(
                GraduationPlagiarismCheck.tenant_id == _tid(),
                GraduationPlagiarismCheck.recheck_of_id == check.id,
                GraduationPlagiarismCheck.is_deleted.is_(False),
            ).with_for_update()).first()
            if existing_recheck:
                raise AppException("DATA_CONFLICT", "该申请已生成过复查任务，不能重复生成")
            recheck = GraduationPlagiarismCheck(
                tenant_id=_tid(), gd_student_id=student.id, gd_final_id=final.id,
                recheck_of_id=check.id, submit_at=datetime.now(timezone.utc),
                status="CHECKING", active_key=f"checking:{final.id}", threshold=check.threshold,
            )
            db.add(recheck)
            db.flush()
            check.dispute_status = "APPROVED"
            result_text = "查重复查申请已通过，新的复查任务已创建"
        else:
            check.dispute_status = "REJECTED"
            result_text = f"查重复查申请未通过：{note}"
        check.dispute_comment = note

        outbox_id = None
        if student.student_id:
            outbox = emit_message_event(
                db,
                event_code="GRADUATION_DESIGN.PLAGIARISM_DISPUTE_REVIEWED",
                source_module="graduation",
                source_biz_type="plagiarism_dispute",
                source_biz_id=int(check.id),
                recipient_refs=[{"studentId": int(student.student_id)}],
                title="毕业设计查重复查处理结果",
                content=result_text,
                action_key="graduation.final.view",
                action_params={"gdStudentId": str(student.id), "batchId": str(student.batch_id)},
                dedup_key=f"GRADUATION_DESIGN.PLAGIARISM_DISPUTE_REVIEWED:{check.id}:{check.dispute_status}",
            )
            outbox_id = str(outbox.id)

        service._audit(
            db, "PLAGIARISM", check.id,
            "复查审核-" + ("通过" if action == "APPROVE" else "驳回"),
            f"{note};recheckTaskId={recheck.id if recheck else ''};outbox={outbox_id or 'SKIPPED_NO_STUDENT_LINK'}",
        )
        db.commit()
        result = service._plag_row(check, student)
        result.update({
            "recheckTaskId": str(recheck.id) if recheck else None,
            "notificationQueued": bool(outbox_id), "outboxId": outbox_id,
        })
        return result


def install_plagiarism_consistency() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.modules.graduation.services import graduation_review_service as service
    service.dispute_plagiarism = dispute_plagiarism
    service.review_dispute = review_dispute
    _INSTALLED = True
