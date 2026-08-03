"""Proposal/final compatibility contracts backed by the sole material command path."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import (
    GraduationAuditTrail,
    GraduationFinal,
    GraduationMidterm,
    GraduationPlagiarismCheck,
    GraduationProposal,
    GraduationStudent,
    GraduationTaskBook,
)
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services import file_service
from app.services.db_service import _tid, session
from app.services.file_access_service import require_file_access
from app.services.file_scan_service import assert_file_ready_for_business
from app.services.message_identity import resolve_message_user_id

from .command_service import review_material_in_session, submit_material_in_session
from .query_service import final_detail, proposal_detail
from .snapshot_service import render_fields_pdf


def _actor_id(user: dict | None) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _actor_name(user: dict | None) -> str:
    actor = user or {}
    return str(actor.get("realName") or actor.get("loginName") or actor.get("username") or "系统")[:100]


def _require_student(user: dict) -> None:
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise not_found("毕业设计材料不存在")


def _expected(body: dict) -> int:
    value = (body or {}).get("expectedVersion")
    if not str(value if value is not None else "").isdigit():
        raise AppException("VALIDATION_ERROR", "expectedVersion 不能为空")
    return int(value)


def _one_attachment(body: dict, *, required: bool) -> int | None:
    values = list((body or {}).get("attachments") or [])
    ids = []
    for raw in values:
        value = raw.get("fileId") if isinstance(raw, dict) else raw
        if str(value or "").isdigit():
            ids.append(int(value))
    ids = list(dict.fromkeys(ids))
    if len(ids) > 1:
        raise AppException("VALIDATION_ERROR", "兼容提交一次仅接收一个主文档；其他成果请按材料代码分别提交")
    if required and not ids:
        raise AppException("VALIDATION_ERROR", "成果主文档附件不能为空")
    return ids[0] if ids else None


def _authorize_file(file_id: int, user: dict) -> None:
    require_file_access(str(file_id), user=user, action="bind")
    assert_file_ready_for_business(str(file_id), user=user)


def _audit(db, biz_type: str, biz_id: int, action: str, user: dict, *, before: str = "", after: str = "", detail: str = ""):
    db.add(GraduationAuditTrail(
        tenant_id=_tid(), biz_type=biz_type, biz_id=str(biz_id), action=action,
        operator=_actor_name(user), before_val=before, after_val=after, detail=detail,
        occurred_at=datetime.utcnow(), created_by=_actor_id(user),
    ))


def _student_snapshot(user: dict) -> dict:
    with session() as db:
        student = resolve_current_gd_student(db, user)
        if not student:
            raise not_found("未找到你的毕业设计档案")
        return {
            "id": int(student.id), "name": student.name, "studentNo": student.student_no or "",
            "topicTitle": student.topic_title or "",
        }


def submit_proposal(user: dict, body: dict) -> dict:
    _require_student(user)
    expected = _expected(body)
    background = str((body or {}).get("background") or "").strip()
    plan = str((body or {}).get("plan") or "").strip()
    outcome = str((body or {}).get("outcome") or "").strip()
    if not background or not plan:
        raise AppException("VALIDATION_ERROR", "选题背景、研究方案与进度不能为空")
    student_snapshot = _student_snapshot(user)
    file_id = _one_attachment(body, required=False)
    if file_id:
        _authorize_file(file_id, user)
    else:
        data = render_fields_pdf("毕业设计开题报告", (
            ("学生", student_snapshot["name"]), ("学号", student_snapshot["studentNo"]),
            ("题目", student_snapshot["topicTitle"]), ("选题背景", background),
            ("研究方案与进度", plan), ("预期成果", outcome),
        ))
        meta = file_service.store_bytes(
            data, f"{student_snapshot['studentNo']}_PROPOSAL_REPORT.pdf",
            biz_type="GRADUATION_SNAPSHOT_STAGING", biz_id=str(student_snapshot["id"]),
            mime_type="application/pdf", user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE",
        )
        file_id = int(meta["fileId"])
        _authorize_file(file_id, user)
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == student_snapshot["id"],
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("未找到你的毕业设计档案")
        assert_student_access(db, student, "proposal.submit")
        if not student.topic_id:
            raise AppException("DATA_CONFLICT", "请先完成选题确认后再提交开题报告")
        if (student.eligibility_status or "PENDING") == "UNQUALIFIED":
            raise AppException("DATA_CONFLICT", "资格不合格，不能提交开题报告")
        taskbook = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == int(student.id),
            GraduationTaskBook.status == "CONFIRMED", GraduationTaskBook.is_deleted.is_(False),
        )).first()
        if not taskbook:
            raise AppException("DATA_CONFLICT", "请先确认任务书后再提交开题报告")
        existing = list(db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == int(student.id),
            GraduationProposal.is_deleted.is_(False),
        ).order_by(GraduationProposal.id.desc()).with_for_update()).all())
        if any(row.status == "PENDING_REVIEW" for row in existing):
            raise AppException("DATA_CONFLICT", "已有待审核的开题报告")
        if any(row.status == "APPROVED" for row in existing):
            raise AppException("DATA_CONFLICT", "开题报告已通过，无需重复提交")
        proposal = GraduationProposal(
            tenant_id=_tid(), gd_student_id=int(student.id), version=f"v{len(existing) + 1}",
            is_resubmit=bool(existing), submit_at=datetime.now(timezone.utc), background=background,
            plan=plan, outcome=outcome, attachments_json=[int(file_id)], status="PENDING_REVIEW",
            active_key=f"pending:{student.id}", created_by=_actor_id(user),
        )
        db.add(proposal)
        db.flush()
        material = submit_material_in_session(
            db, user, int(student.id), "PROPOSAL_REPORT", int(file_id),
            expected_version=expected, source_channel="STUDENT_SUBMISSION",
            source_record_type="PROPOSAL", source_record_id=str(proposal.id),
            comment="开题报告兼容入口提交",
        )
        _audit(db, "PROPOSAL", int(proposal.id), "提交开题报告", user, after="PENDING_REVIEW")
        from app.modules.graduation.services import graduation_todo_helper as todo

        todo.push_proposal_todo(db, proposal, student)
        db.commit()
        return {
            "id": str(proposal.id), "version": proposal.version, "isResubmit": bool(existing),
            "status": proposal.status, "material": material,
            "fileVersionCount": 1, "currentSafeVersions": [],
        }


def submit_final(user: dict, body: dict) -> dict:
    _require_student(user)
    expected = _expected(body)
    final_type = str((body or {}).get("finalType") or "初稿")
    if final_type not in {"初稿", "定稿"}:
        raise AppException("VALIDATION_ERROR", "成果类型必须是初稿/定稿")
    file_id = _one_attachment(body, required=True)
    _authorize_file(int(file_id), user)
    with session() as db:
        resolved = resolve_current_gd_student(db, user)
        if not resolved:
            raise not_found("未找到你的毕业设计档案")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(resolved.id),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, student, "final.submit")
        if student.stage not in {"FINAL_CHECK", "DEFENSE"}:
            raise AppException("DATA_CONFLICT", "当前阶段不可提交成果")
        if not student.topic_id or (student.eligibility_status or "PENDING") == "UNQUALIFIED":
            raise AppException("DATA_CONFLICT", "当前学生不满足成果提交条件")
        midterm = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == int(student.id),
            GraduationMidterm.status.in_(("CHECKED_PASS", "RECTIFIED_PASS")),
            GraduationMidterm.is_deleted.is_(False),
        ).order_by(GraduationMidterm.id.desc())).first()
        if not midterm:
            raise AppException("DATA_CONFLICT", "中期检查未通过，不能提交成果")
        existing = list(db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == int(student.id),
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).with_for_update()).all())
        if any(row.status == "PENDING_REVIEW" for row in existing):
            raise AppException("DATA_CONFLICT", "已有待审核的成果")
        if final_type == "定稿" and not any(row.final_type == "初稿" and row.status == "APPROVED" for row in existing):
            raise AppException("DATA_CONFLICT", "请先提交初稿并审核通过")
        if any(row.final_type == final_type and row.status == "APPROVED" for row in existing):
            raise AppException("DATA_CONFLICT", f"{final_type}已审核通过")
        same_type = [row for row in existing if row.final_type == final_type]
        final = GraduationFinal(
            tenant_id=_tid(), gd_student_id=int(student.id), final_type=final_type,
            version=f"v{len(same_type) + 1}", submit_at=datetime.now(timezone.utc),
            plagiarism_rate=None, plagiarism_status="未检测", attachments_json=[int(file_id)],
            status="PENDING_REVIEW", active_key=f"pending:{student.id}", created_by=_actor_id(user),
        )
        db.add(final)
        db.flush()
        material_code = "THESIS_FINAL" if final_type == "定稿" else "THESIS_DRAFT"
        material = submit_material_in_session(
            db, user, int(student.id), material_code, int(file_id),
            expected_version=expected, source_channel="STUDENT_SUBMISSION",
            source_record_type="FINAL", source_record_id=str(final.id),
            comment=f"成果{final_type}兼容入口提交",
        )
        _audit(db, "FINAL", int(final.id), f"提交成果-{final_type}", user, after="PENDING_REVIEW")
        from app.modules.graduation.services import graduation_todo_helper as todo

        todo.push_final_todo(db, final, student)
        db.commit()
        return {
            "id": str(final.id), "finalType": final_type, "version": final.version,
            "status": final.status, "material": material,
            "fileVersionCount": 1, "currentSafeVersions": [],
        }


def _record_material(db, student_id: int, material_code: str, record_type: str, record_id: int):
    row = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.gd_student_id == int(student_id),
        GraduationStudentMaterial.material_code == material_code,
        GraduationStudentMaterial.source_record_type == record_type,
        GraduationStudentMaterial.source_record_id == str(record_id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise AppException("DATA_CONFLICT", "业务记录尚未绑定权威材料版本")
    return row


def review_proposal(proposal_id: int, action: str, comment: str | None, user: dict,
                    *, expected_version: int | None, expected_file_version_id: int | None) -> dict:
    if expected_version is None or expected_file_version_id is None:
        raise AppException("VALIDATION_ERROR", "expectedVersion 和 fileVersionId 不能为空")
    with session() as db:
        proposal = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.id == int(proposal_id),
            GraduationProposal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not proposal:
            raise not_found("开题材料不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(proposal.gd_student_id),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, student, "proposal.review")
        if proposal.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "该开题报告已被处理")
        material = _record_material(db, int(student.id), "PROPOSAL_REPORT", "PROPOSAL", int(proposal.id))
        reviewed = review_material_in_session(
            db, int(material.id), int(expected_file_version_id), action, comment, user,
            expected_version=int(expected_version),
        )
        target = "APPROVED" if str(action).upper() == "APPROVE" else "REJECTED"
        before = proposal.status
        proposal.status = target
        proposal.active_key = None
        proposal.reviewer = _actor_name(user)
        proposal.review_comment = str(comment or "").strip()
        proposal.review_time = datetime.now(timezone.utc)
        _audit(db, "PROPOSAL", int(proposal.id), "审核开题报告", user, before=before, after=target)
        from app.modules.graduation.services import graduation_todo_helper as todo

        todo.todo_done(db, biz_id=proposal.id, todo_type=todo.TODO_PROPOSAL)
        if target == "APPROVED" and student.stage in {"TOPIC_SELECTING", "TASKBOOK_CONFIRM"}:
            student.stage = "GUIDING"
            student.version = int(student.version or 0) + 1
        db.commit()
        return {"id": str(proposal.id), "status": target, "material": reviewed}


def review_final(final_id: int, action: str, comment: str | None, user: dict,
                 *, expected_version: int | None, expected_file_version_id: int | None) -> dict:
    if expected_version is None or expected_file_version_id is None:
        raise AppException("VALIDATION_ERROR", "expectedVersion 和 fileVersionId 不能为空")
    with session() as db:
        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.id == int(final_id),
            GraduationFinal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not final:
            raise not_found("成果不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(final.gd_student_id),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, student, "final.review")
        if final.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "该成果已被处理")
        if str(action).upper() == "APPROVE" and final.final_type == "定稿":
            check = db.scalars(select(GraduationPlagiarismCheck).where(
                GraduationPlagiarismCheck.tenant_id == _tid(),
                GraduationPlagiarismCheck.gd_final_id == int(final.id),
                GraduationPlagiarismCheck.is_deleted.is_(False),
            ).order_by(GraduationPlagiarismCheck.id.desc()).with_for_update()).first()
            if not check or check.status != "DONE":
                raise AppException("DATA_CONFLICT", "查重尚未完成，不能通过定稿审核")
            if check.over_threshold and check.dispute_status != "APPROVED":
                raise AppException("DATA_CONFLICT", "查重超标且未通过特例审批")
        code = "THESIS_FINAL" if final.final_type == "定稿" else "THESIS_DRAFT"
        material = _record_material(db, int(student.id), code, "FINAL", int(final.id))
        reviewed = review_material_in_session(
            db, int(material.id), int(expected_file_version_id), action, comment, user,
            expected_version=int(expected_version),
        )
        target = "APPROVED" if str(action).upper() == "APPROVE" else "REJECTED"
        before = final.status
        final.status = target
        final.active_key = None
        final.reviewer = _actor_name(user)
        final.review_comment = str(comment or "").strip()
        final.review_time = datetime.now(timezone.utc)
        _audit(db, "FINAL", int(final.id), "审核成果", user, before=before, after=target)
        from app.modules.graduation.services import graduation_todo_helper as todo

        todo.todo_done(db, biz_id=final.id, todo_type=todo.TODO_FINAL)
        db.commit()
        return {"id": str(final.id), "status": target, "material": reviewed}


__all__ = [
    "final_detail", "proposal_detail", "review_final", "review_proposal",
    "submit_final", "submit_proposal",
]
