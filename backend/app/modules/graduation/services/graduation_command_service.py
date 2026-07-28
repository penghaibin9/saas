"""毕业设计事务命令与并发冲突边界。

正式领域 Service 静态引用这里的高风险命令实现：
- 开题批阅必须锁定开题行；
- 成果提交必须先锁定学生，再锁定该生全部成果；
- 选题志愿退选锁定轮次、学生与志愿，缺失轮次返回 404；
- 选题变更锁定学生、申请与题目容量；
- 答辩组编排与通知锁定组和学生；
- 关键审计补齐稳定 actor；
- 数据库唯一约束竞争统一转换为 409，而不是裸 500。
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.models import (
    GraduationFinal,
    GraduationMidterm,
    GraduationProposal,
    GraduationStudent,
    GraduationTaskBook,
    GraduationTopicChoice,
    GraduationTopicRound,
)
from app.modules.graduation.services.graduation_scope_service import assert_student_access
from app.services.db_service import _tid, session

from app.modules.graduation.services.graduation_archive_terminal_guard import (
    register_graduation_archive_guard,
)
from app.modules.graduation.services.graduation_audit_consistency import (
    register_graduation_audit_listener,
)

register_graduation_audit_listener()
register_graduation_archive_guard()

def _conflict_guard(fn):
    if getattr(fn, "_gd_conflict_guard", False):
        return fn

    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except IntegrityError as exc:
            raise AppException(
                "DATA_CONFLICT",
                "数据已被其他操作抢先处理，请刷新后重试；系统未生成重复记录",
            ) from exc

    wrapped._gd_conflict_guard = True
    return wrapped


def _locked_review_proposal(pid, action, comment=None) -> dict:
    from app.modules.graduation.services import graduation_service as gd

    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        proposal = db.scalars(select(GraduationProposal).where(
            GraduationProposal.id == int(pid),
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
        assert_student_access(db, student, "proposal.review")
        if proposal.status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该开题已被处理，请刷新")
        before = proposal.status
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
        operator, _ = gd._op()
        proposal.status = target
        proposal.active_key = None
        proposal.reviewer = operator
        proposal.review_comment = (comment or "").strip()
        proposal.review_time = datetime.now(timezone.utc)
        proposal.version = proposal.version or "v1"
        gd._audit(
            db, "PROPOSAL", proposal.id,
            "批阅开题-" + ("通过" if action == "APPROVE" else "驳回"),
            (comment or "").strip(), before, target,
        )
        from app.modules.graduation.services import graduation_todo_helper as gd_todo
        gd_todo.todo_done(db, biz_id=proposal.id, todo_type=gd_todo.TODO_PROPOSAL)
        if action == "APPROVE" and student.stage in ("TOPIC_SELECTING", "TASKBOOK_CONFIRM"):
            taskbook = db.scalars(select(GraduationTaskBook).where(
                GraduationTaskBook.tenant_id == _tid(),
                GraduationTaskBook.gd_student_id == student.id,
                GraduationTaskBook.is_deleted.is_(False),
                GraduationTaskBook.status == "CONFIRMED",
            ).limit(1)).first()
            student.stage = "GUIDING" if taskbook else "TASKBOOK_CONFIRM"
        db.commit()
        return {"id": str(proposal.id), "status": target, "statusLabel": gd.L_MAT.get(target, target)}


def _locked_submit_final(gd_student_id, final_type, attachments=None) -> dict:
    from app.modules.graduation.services import graduation_service as gd

    attachment_ids = gd._validate_final_attachments(attachments)
    if final_type not in gd.FINAL_TYPES:
        raise AppException("VALIDATION_ERROR", "成果类型必须是 初稿/定稿")
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生档案不存在")
        assert_student_access(db, student, "final.submit")
        if student.stage not in ("FINAL_CHECK", "DEFENSE"):
            raise AppException("DATA_CONFLICT", "当前阶段不可提交成果（须进入成果检查阶段）")
        if not student.topic_id:
            raise AppException("DATA_CONFLICT", "请先完成选题确认后再提交成果")
        if (getattr(student, "eligibility_status", None) or "PENDING") == "UNQUALIFIED":
            raise AppException("DATA_CONFLICT", "资格不合格，不能提交成果")
        midterm = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == _tid(),
            GraduationMidterm.gd_student_id == student.id,
            GraduationMidterm.is_deleted.is_(False),
        ).order_by(GraduationMidterm.id.desc()).with_for_update()).first()
        if not gd.midterm_allows_final_submit(midterm):
            raise AppException("DATA_CONFLICT", "中期检查未通过或尚未完成，不能提交成果")

        existing = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.gd_student_id == student.id,
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).with_for_update()).all()
        pending = next((row for row in existing if row.status == "PENDING_REVIEW"), None)
        if pending:
            same = pending.final_type == final_type and (pending.attachments_json or []) == attachment_ids
            if same:
                return {
                    "id": str(pending.id), "finalType": pending.final_type,
                    "version": pending.version, "status": pending.status,
                }
            raise AppException("DATA_CONFLICT", "已有待审阅的成果，请等待指导教师批阅")
        if final_type == "定稿":
            if not any(row.final_type == "初稿" and row.status == "APPROVED" for row in existing):
                raise AppException("DATA_CONFLICT", "请先提交初稿并通过后再提交定稿")
            if any(row.final_type == "定稿" and row.status == "APPROVED" for row in existing):
                raise AppException("DATA_CONFLICT", "定稿已通过，无需重复提交")

        gd._mark_material_files(db, attachment_ids)
        same_type = [row for row in existing if row.final_type == final_type]
        version = f"v{len(same_type) + 1}"
        final = GraduationFinal(
            tenant_id=_tid(), gd_student_id=student.id, final_type=final_type,
            version=version, submit_at=datetime.now(timezone.utc),
            plagiarism_rate=None, plagiarism_status="未检测",
            attachments_json=attachment_ids, status="PENDING_REVIEW",
            active_key=f"pending:{student.id}",
        )
        db.add(final)
        db.flush()
        gd._audit(
            db, "FINAL", final.id, f"提交成果-{final_type}",
            f"{student.name} {final_type} {version}", "", "PENDING_REVIEW",
        )
        from app.modules.graduation.services import graduation_todo_helper as gd_todo
        gd_todo.push_final_todo(db, final, student)
        db.commit()
        return {"id": str(final.id), "finalType": final_type, "version": version, "status": "PENDING_REVIEW"}


def _locked_withdraw_choices(round_id, gd_student_id) -> dict:
    """学生退选：缺失轮次返回 404，状态与批次在同一事务核验。"""
    from app.modules.graduation.services import graduation_topic_round_service as rounds

    with session() as db:
        round_row = db.scalars(select(GraduationTopicRound).where(
            GraduationTopicRound.id == int(round_id),
            GraduationTopicRound.tenant_id == _tid(),
            GraduationTopicRound.is_deleted.is_(False),
        ).with_for_update()).first()
        if not round_row:
            raise not_found("选题轮次不存在")
        if round_row.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅进行中的轮次可退选")

        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id),
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student:
            raise not_found("毕设学生不存在")
        assert_student_access(db, student, "topic.choice.withdraw")
        if int(student.batch_id or 0) != int(round_row.batch_id or 0):
            raise AppException("DATA_CONFLICT", "学生批次与选题轮次不一致，无法退选")

        rows = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.tenant_id == _tid(),
            GraduationTopicChoice.round_id == round_row.id,
            GraduationTopicChoice.gd_student_id == student.id,
            GraduationTopicChoice.is_deleted.is_(False),
        ).order_by(GraduationTopicChoice.id).with_for_update()).all()
        if not rows:
            raise not_found("当前没有可退选的志愿")
        if any(row.status in ("CONFIRMED", "MATCHED") for row in rows):
            raise AppException("DATA_CONFLICT", "已被确认/匹配的选题不可自助退选，请走课题变更流程")
        active = [row for row in rows if row.status != "WITHDRAWN"]
        if not active:
            raise not_found("当前没有可退选的志愿")
        for row in active:
            row.status = "WITHDRAWN"
            row.is_deleted = True
            row.submission_version = int(row.submission_version or 0) + 1
        rounds._audit(
            db, round_row.id, "WITHDRAW_CHOICES",
            f"学生 {student.name or student.id} 退选 {len(active)} 个志愿",
        )
        db.commit()
        return {"withdrawn": len(active), "alreadyWithdrawn": False}


review_proposal = _conflict_guard(_locked_review_proposal)
submit_final = _conflict_guard(_locked_submit_final)
withdraw_choices = _conflict_guard(_locked_withdraw_choices)
