"""优秀成果认定与延期答辩独立状态机。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    GraduationAuditTrail, GraduationDefenseGroup, GraduationFinal, GraduationGrade,
    GraduationStudent,
)
from app.models.graduation_extension import GraduationDefenseDelay, GraduationExcellentOutcome
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access
from app.services.db_service import _iso, _tid, session

EXCELLENT_LABEL = {
    "PENDING_MAJOR": "待专业复核", "PENDING_COLLEGE": "待学院终审",
    "PUBLISHED": "已认定并发布", "REJECTED": "已驳回", "WITHDRAWN": "已撤回",
}
DELAY_LABEL = {
    "PENDING_ADVISOR": "待导师审核", "PENDING_MAJOR": "待专业复核",
    "PENDING_COLLEGE": "待学院审批", "APPROVED": "已批准待排期",
    "SCHEDULED": "已重新排期", "REJECTED": "已驳回", "CANCELLED": "已撤回",
}
_HIGH_ADMIN = {"PLATFORM_SUPER_ADMIN", "SAAS_ADMIN", "SCHOOL_ADMIN", "GRADUATION_ADMIN", "GD_ADMIN"}
_MAJOR_ROLES = _HIGH_ADMIN | {"GD_MAJOR_ADMIN", "MAJOR_ADMIN", "PROFESSIONAL_LEADER", "MAJOR_LEADER"}
_COLLEGE_ROLES = _HIGH_ADMIN | {"GD_COLLEGE_ADMIN", "COLLEGE_ADMIN"}


def _user() -> dict:
    return get_current_user_ctx() or {}


def _role() -> str:
    u = _user()
    return str(u.get("currentRoleCode") or u.get("userType") or "").strip().upper()


def _operator() -> str:
    u = _user()
    return str(u.get("realName") or u.get("loginName") or "系统")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _audit(db, biz_type: str, biz_id, action: str, detail: str, *, batch_id=None):
    db.add(GraduationAuditTrail(
        tenant_id=_tid(), biz_type=biz_type, biz_id=str(biz_id), action=action,
        operator=_operator(), role_name=_role(), detail=detail, batch_id=batch_id,
        occurred_at=_now(),
    ))


def _student(db, student_id) -> GraduationStudent:
    row = db.get(GraduationStudent, int(student_id))
    if not row or row.is_deleted or row.tenant_id != _tid():
        raise not_found("毕设学生不存在")
    return assert_student_access(db, row, "graduation.extension")


def _require_advisor(db, student: GraduationStudent):
    if _role() in _HIGH_ADMIN:
        return
    from app.modules.graduation.services import graduation_identity as gid
    mentor = gid.current_user_mentor(db)
    if not mentor or not student.mentor_id or int(mentor.id) != int(student.mentor_id):
        raise no_permission("仅该学生的稳定绑定指导教师可执行此操作")


def _require_major():
    if _role() not in _MAJOR_ROLES:
        raise no_permission("仅专业负责人可完成专业复核")


def _require_college():
    if _role() not in _COLLEGE_ROLES:
        raise no_permission("仅学院管理员可完成学院终审或延期排期")


def _excellent_row(row: GraduationExcellentOutcome, student=None) -> dict:
    return {
        "id": str(row.id), "gdStudentId": str(row.gd_student_id),
        "batchId": str(row.batch_id), "studentName": student.name if student else "",
        "studentNo": student.student_no if student else "", "className": student.class_name if student else "",
        "topicTitle": student.topic_title if student else "", "advisorName": student.advisor_name if student else "",
        "status": row.status, "statusLabel": EXCELLENT_LABEL.get(row.status, row.status),
        "nominationReason": row.nomination_reason, "evidence": row.evidence_json or [],
        "gradeSnapshot": row.grade_snapshot_json or {}, "nominatedBy": row.nominated_by or "",
        "nominatedAt": _iso(row.nominated_at), "majorReviewComment": row.major_review_comment or "",
        "majorReviewedBy": row.major_reviewed_by or "", "collegeReviewComment": row.college_review_comment or "",
        "collegeReviewedBy": row.college_reviewed_by or "", "publishedAt": _iso(row.published_at),
    }


def _delay_row(row: GraduationDefenseDelay, student=None, group=None) -> dict:
    return {
        "id": str(row.id), "gdStudentId": str(row.gd_student_id), "batchId": str(row.batch_id),
        "studentName": student.name if student else "", "studentNo": student.student_no if student else "",
        "className": student.class_name if student else "", "topicTitle": student.topic_title if student else "",
        "advisorName": student.advisor_name if student else "", "status": row.status,
        "statusLabel": DELAY_LABEL.get(row.status, row.status), "reason": row.reason,
        "evidence": row.evidence_json or [], "requestedAt": _iso(row.requested_at),
        "advisorComment": row.advisor_comment or "", "advisorReviewedBy": row.advisor_reviewed_by or "",
        "majorComment": row.major_comment or "", "majorReviewedBy": row.major_reviewed_by or "",
        "collegeComment": row.college_comment or "", "collegeReviewedBy": row.college_reviewed_by or "",
        "plannedDefenseDate": row.planned_defense_date or "",
        "defenseGroupId": str(row.defense_group_id) if row.defense_group_id else "",
        "defenseGroupName": group.group_name if group else "", "scheduledAt": _iso(row.scheduled_at),
    }


def list_excellent_outcomes(*, batch_id: int, status: str | None = None, page: int = 1, page_size: int = 20):
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        q = select(GraduationExcellentOutcome).where(
            GraduationExcellentOutcome.tenant_id == _tid(),
            GraduationExcellentOutcome.batch_id == int(batch_id),
            GraduationExcellentOutcome.gd_student_id.in_(scope_ids or [-1]),
            GraduationExcellentOutcome.is_deleted.is_(False),
        )
        if status:
            q = q.where(GraduationExcellentOutcome.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationExcellentOutcome.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_excellent_row(row, db.get(GraduationStudent, row.gd_student_id)) for row in rows], total


def nominate_excellent(gd_student_id, reason: str, evidence: list | None = None) -> dict:
    if len((reason or "").strip()) < 10:
        raise AppException("VALIDATION_ERROR", "优秀成果提名理由不少于 10 字")
    with session() as db:
        student = _student(db, gd_student_id)
        _require_advisor(db, student)
        grade = db.scalars(select(GraduationGrade).where(
            GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == student.id,
            GraduationGrade.is_deleted.is_(False), GraduationGrade.status == "PUBLISHED",
        ).with_for_update()).first()
        if not grade or grade.grade_level != "优秀":
            raise AppException("DATA_CONFLICT", "仅成绩已发布且等级为“优秀”的成果可提名")
        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == student.id,
            GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).limit(1)).first()
        if not final:
            raise AppException("DATA_CONFLICT", "缺少已通过的正式定稿，不能提名优秀成果")
        row = db.scalars(select(GraduationExcellentOutcome).where(
            GraduationExcellentOutcome.tenant_id == _tid(),
            GraduationExcellentOutcome.gd_student_id == student.id,
            GraduationExcellentOutcome.is_deleted.is_(False),
        ).with_for_update()).first()
        if row and row.status not in ("REJECTED", "WITHDRAWN"):
            raise AppException("DATA_CONFLICT", f"该生已有进行中的优秀成果记录（{EXCELLENT_LABEL.get(row.status, row.status)}）")
        snapshot = {
            "gradeId": str(grade.id), "advisorScore": grade.advisor_score,
            "reviewerScore": grade.reviewer_score, "defenseScore": grade.defense_score,
            "totalScore": grade.total_score, "gradeLevel": grade.grade_level,
            "finalId": str(final.id), "finalVersion": final.version,
        }
        if not row:
            row = GraduationExcellentOutcome(
                tenant_id=_tid(), gd_student_id=student.id, batch_id=int(student.batch_id),
                status="PENDING_MAJOR", nomination_reason=reason.strip(), evidence_json=evidence or [],
                grade_snapshot_json=snapshot, nominated_by=_operator(), nominated_at=_now(),
            )
            db.add(row)
        else:
            row.status = "PENDING_MAJOR"; row.nomination_reason = reason.strip()
            row.evidence_json = evidence or []; row.grade_snapshot_json = snapshot
            row.nominated_by = _operator(); row.nominated_at = _now()
            row.major_review_comment = None; row.major_reviewed_by = None; row.major_reviewed_at = None
            row.college_review_comment = None; row.college_reviewed_by = None; row.college_reviewed_at = None
            row.published_at = None; row.version = int(row.version or 0) + 1
        db.flush()
        _audit(db, "EXCELLENT_OUTCOME", row.id, "NOMINATE", reason.strip(), batch_id=student.batch_id)
        db.commit()
        return _excellent_row(row, student)


def major_review_excellent(record_id, action: str, comment: str) -> dict:
    _require_major()
    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回理由不少于 5 字")
    with session() as db:
        row = db.get(GraduationExcellentOutcome, int(record_id), with_for_update=True)
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("优秀成果提名不存在")
        _student(db, row.gd_student_id)
        if row.status != "PENDING_MAJOR":
            raise AppException("DATA_CONFLICT", "仅待专业复核记录可处理")
        row.status = "PENDING_COLLEGE" if action == "APPROVE" else "REJECTED"
        row.major_review_comment = (comment or "").strip(); row.major_reviewed_by = _operator(); row.major_reviewed_at = _now()
        row.version = int(row.version or 0) + 1
        _audit(db, "EXCELLENT_OUTCOME", row.id, f"MAJOR_{action}", comment or "", batch_id=row.batch_id)
        db.commit()
        return _excellent_row(row, db.get(GraduationStudent, row.gd_student_id))


def college_review_excellent(record_id, action: str, comment: str) -> dict:
    _require_college()
    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回理由不少于 5 字")
    with session() as db:
        row = db.get(GraduationExcellentOutcome, int(record_id), with_for_update=True)
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("优秀成果提名不存在")
        _student(db, row.gd_student_id)
        if row.status != "PENDING_COLLEGE":
            raise AppException("DATA_CONFLICT", "仅待学院终审记录可处理")
        row.status = "PUBLISHED" if action == "APPROVE" else "REJECTED"
        row.college_review_comment = (comment or "").strip(); row.college_reviewed_by = _operator(); row.college_reviewed_at = _now()
        row.published_at = _now() if action == "APPROVE" else None
        row.version = int(row.version or 0) + 1
        _audit(db, "EXCELLENT_OUTCOME", row.id, f"COLLEGE_{action}", comment or "", batch_id=row.batch_id)
        db.commit()
        return _excellent_row(row, db.get(GraduationStudent, row.gd_student_id))


def my_extensions(user: dict) -> dict:
    with session() as db:
        student = resolve_current_gd_student(db, user)
        if not student:
            return {"hasData": False, "excellentOutcome": None, "defenseDelay": None}
        excellent = db.scalars(select(GraduationExcellentOutcome).where(
            GraduationExcellentOutcome.tenant_id == _tid(), GraduationExcellentOutcome.gd_student_id == student.id,
            GraduationExcellentOutcome.is_deleted.is_(False),
        ).order_by(GraduationExcellentOutcome.id.desc())).first()
        delay = db.scalars(select(GraduationDefenseDelay).where(
            GraduationDefenseDelay.tenant_id == _tid(), GraduationDefenseDelay.gd_student_id == student.id,
            GraduationDefenseDelay.is_deleted.is_(False),
        ).order_by(GraduationDefenseDelay.id.desc())).first()
        group = db.get(GraduationDefenseGroup, delay.defense_group_id) if delay and delay.defense_group_id else None
        return {
            "hasData": True, "gdStudentId": str(student.id), "batchId": str(student.batch_id or ""),
            "excellentOutcome": _excellent_row(excellent, student) if excellent else None,
            "defenseDelay": _delay_row(delay, student, group) if delay else None,
            "canApplyDelay": student.stage in ("FINAL_CHECK", "DEFENSE") and not delay,
        }


def apply_delay(user: dict, reason: str, evidence: list | None = None) -> dict:
    if len((reason or "").strip()) < 10:
        raise AppException("VALIDATION_ERROR", "延期答辩理由不少于 10 字")
    with session() as db:
        student = resolve_current_gd_student(db, user)
        if not student:
            raise not_found("当前没有可申请延期的毕业设计档案")
        if student.stage not in ("FINAL_CHECK", "DEFENSE"):
            raise AppException("DATA_CONFLICT", "仅进入成果检查或答辩阶段后可申请延期答辩")
        published_grade = db.scalars(select(GraduationGrade.id).where(
            GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == student.id,
            GraduationGrade.status == "PUBLISHED", GraduationGrade.is_deleted.is_(False),
        ).limit(1)).first()
        if published_grade:
            raise AppException("DATA_CONFLICT", "成绩已发布，不能再申请延期答辩")
        active = db.scalars(select(GraduationDefenseDelay).where(
            GraduationDefenseDelay.tenant_id == _tid(), GraduationDefenseDelay.active_key == f"active:{student.id}",
            GraduationDefenseDelay.is_deleted.is_(False),
        ).with_for_update()).first()
        if active:
            raise AppException("DATA_CONFLICT", f"已有延期答辩申请（{DELAY_LABEL.get(active.status, active.status)}）")
        row = GraduationDefenseDelay(
            tenant_id=_tid(), gd_student_id=student.id, batch_id=int(student.batch_id),
            active_key=f"active:{student.id}", status="PENDING_ADVISOR",
            reason=reason.strip(), evidence_json=evidence or [], requested_at=_now(),
        )
        db.add(row); db.flush()
        _audit(db, "DEFENSE_DELAY", row.id, "APPLY", reason.strip(), batch_id=student.batch_id)
        db.commit()
        return _delay_row(row, student)


def list_delays(*, batch_id: int, status: str | None = None, page: int = 1, page_size: int = 20):
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        q = select(GraduationDefenseDelay).where(
            GraduationDefenseDelay.tenant_id == _tid(), GraduationDefenseDelay.batch_id == int(batch_id),
            GraduationDefenseDelay.gd_student_id.in_(scope_ids or [-1]),
            GraduationDefenseDelay.is_deleted.is_(False),
        )
        if status:
            q = q.where(GraduationDefenseDelay.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationDefenseDelay.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        result = []
        for row in rows:
            result.append(_delay_row(row, db.get(GraduationStudent, row.gd_student_id),
                                     db.get(GraduationDefenseGroup, row.defense_group_id) if row.defense_group_id else None))
        return result, total


def advisor_review_delay(record_id, action: str, comment: str) -> dict:
    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回理由不少于 5 字")
    with session() as db:
        row = db.get(GraduationDefenseDelay, int(record_id), with_for_update=True)
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("延期答辩申请不存在")
        student = _student(db, row.gd_student_id); _require_advisor(db, student)
        if row.status != "PENDING_ADVISOR":
            raise AppException("DATA_CONFLICT", "仅待导师审核申请可处理")
        row.status = "PENDING_MAJOR" if action == "APPROVE" else "REJECTED"
        row.advisor_comment = (comment or "").strip(); row.advisor_reviewed_by = _operator(); row.advisor_reviewed_at = _now()
        if action == "REJECT": row.active_key = None
        row.version = int(row.version or 0) + 1
        _audit(db, "DEFENSE_DELAY", row.id, f"ADVISOR_{action}", comment or "", batch_id=row.batch_id)
        db.commit(); return _delay_row(row, student)


def major_review_delay(record_id, action: str, comment: str) -> dict:
    _require_major(); action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回理由不少于 5 字")
    with session() as db:
        row = db.get(GraduationDefenseDelay, int(record_id), with_for_update=True)
        if not row or row.is_deleted or row.tenant_id != _tid(): raise not_found("延期答辩申请不存在")
        student = _student(db, row.gd_student_id)
        if row.status != "PENDING_MAJOR": raise AppException("DATA_CONFLICT", "仅待专业复核申请可处理")
        row.status = "PENDING_COLLEGE" if action == "APPROVE" else "REJECTED"
        row.major_comment = (comment or "").strip(); row.major_reviewed_by = _operator(); row.major_reviewed_at = _now()
        if action == "REJECT": row.active_key = None
        row.version = int(row.version or 0) + 1
        _audit(db, "DEFENSE_DELAY", row.id, f"MAJOR_{action}", comment or "", batch_id=row.batch_id)
        db.commit(); return _delay_row(row, student)


def college_review_delay(record_id, action: str, comment: str) -> dict:
    _require_college(); action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须为 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回理由不少于 5 字")
    with session() as db:
        row = db.get(GraduationDefenseDelay, int(record_id), with_for_update=True)
        if not row or row.is_deleted or row.tenant_id != _tid(): raise not_found("延期答辩申请不存在")
        student = _student(db, row.gd_student_id)
        if row.status != "PENDING_COLLEGE": raise AppException("DATA_CONFLICT", "仅待学院审批申请可处理")
        row.status = "APPROVED" if action == "APPROVE" else "REJECTED"
        row.college_comment = (comment or "").strip(); row.college_reviewed_by = _operator(); row.college_reviewed_at = _now()
        if action == "REJECT": row.active_key = None
        row.version = int(row.version or 0) + 1
        _audit(db, "DEFENSE_DELAY", row.id, f"COLLEGE_{action}", comment or "", batch_id=row.batch_id)
        db.commit(); return _delay_row(row, student)


def schedule_delay(record_id, defense_group_id, planned_date: str) -> dict:
    _require_college()
    if not str(planned_date or "").strip():
        raise AppException("VALIDATION_ERROR", "延期答辩日期必填")
    with session() as db:
        row = db.get(GraduationDefenseDelay, int(record_id), with_for_update=True)
        if not row or row.is_deleted or row.tenant_id != _tid(): raise not_found("延期答辩申请不存在")
        student = _student(db, row.gd_student_id)
        if row.status != "APPROVED": raise AppException("DATA_CONFLICT", "仅学院已批准申请可重新排期")
        group = db.get(GraduationDefenseGroup, int(defense_group_id), with_for_update=True)
        if not group or group.is_deleted or group.tenant_id != _tid() or int(group.batch_id or 0) != int(row.batch_id):
            raise AppException("DATA_CONFLICT", "延期答辩组不存在或与学生批次不一致")
        if group.defense_date and str(group.defense_date) != str(planned_date):
            raise AppException("DATA_CONFLICT", "所选答辩组日期与延期日期不一致，请新建独立延期答辩组")
        group.defense_date = str(planned_date); group.published = False
        student.defense_group_id = group.id; student.defense_group = group.group_name
        student.stage = "DEFENSE"; student.version = int(student.version or 0) + 1
        row.status = "SCHEDULED"; row.planned_defense_date = str(planned_date)
        row.defense_group_id = group.id; row.scheduled_at = _now(); row.version = int(row.version or 0) + 1
        from app.modules.graduation.services import graduation_service as graduation_svc
        graduation_svc._recompute_defense(db, group)
        _audit(db, "DEFENSE_DELAY", row.id, "SCHEDULE", f"{group.group_name}/{planned_date}", batch_id=row.batch_id)
        db.commit(); return _delay_row(row, student, group)
