"""Enterprise E9 collaboration facade over canonical InternshipRecord and InternshipEnterpriseEval.

No second intern/evaluation fact is introduced. All reads/writes use a server-derived
INTERNSHIP_COLLAB context. COMPANY_ADMIN/HR are company-scoped; MENTOR is additionally scoped to
its bound InternshipEnterpriseContact. Student contacts and other sensitive profile facts are not
projected here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipEnterpriseEval, InternshipRecord, StudentProfile
from app.models.employment import InternshipEnterpriseContact
from app.models.internship_enterprise_portal import InternshipEnterpriseMember
from app.services.db_service import _iso

_ACTIVE_RECORD_STATUSES = {"PREPARING", "READY", "ONBOARD", "ASSESSING"}
_SCORE_FIELDS = (
    ("attendanceScore", "attendance_score", "出勤"),
    ("skillScore", "skill_score", "技能"),
    ("attitudeScore", "attitude_score", "态度"),
    ("collaborationScore", "collaboration_score", "协作"),
    ("safetyScore", "safety_score", "安全纪律"),
)


def _member(db, context) -> InternshipEnterpriseMember:
    row = db.scalar(
        select(InternshipEnterpriseMember).where(
            InternshipEnterpriseMember.id == context.member_id,
            InternshipEnterpriseMember.tenant_id == context.tenant_id,
            InternshipEnterpriseMember.company_id == context.company_id,
            InternshipEnterpriseMember.status == "ACTIVE",
            InternshipEnterpriseMember.is_deleted.is_(False),
        )
    )
    if not row:
        raise no_permission("企业成员已失效")
    return row


def _mentor_scope(db, context) -> int | None:
    member = _member(db, context)
    if str(context.member_role or "").upper() != "MENTOR":
        return None
    if not member.contact_id:
        raise no_permission("企业导师账号尚未绑定导师联系人，不能读取学生范围")
    return int(member.contact_id)


def _record_conditions(context, mentor_contact_id: int | None = None):
    conditions = [
        InternshipRecord.tenant_id == context.tenant_id,
        InternshipRecord.enterprise_id == context.company_id,
        InternshipRecord.batch_id == context.batch_id,
        InternshipRecord.position_id.is_not(None),
        InternshipRecord.is_deleted.is_(False),
        StudentProfile.id == InternshipRecord.student_id,
        StudentProfile.tenant_id == context.tenant_id,
        StudentProfile.is_deleted.is_(False),
    ]
    if mentor_contact_id is not None:
        conditions.append(InternshipRecord.mentor_contact_id == mentor_contact_id)
    return conditions


def _filter_record_status(q, status: str | None):
    normalized = str(status or "ALL").upper()
    if normalized in {"", "ALL"}:
        return q
    if normalized == "ACTIVE":
        return q.where(InternshipRecord.status.in_(sorted(_ACTIVE_RECORD_STATUSES)))
    if normalized == "COMPLETED":
        return q.where(InternshipRecord.status == "ARCHIVED")
    return q.where(InternshipRecord.status == normalized)


def _filter_keyword(q, keyword: str | None):
    value = str(keyword or "").strip()
    if not value:
        return q
    pattern = f"%{value}%"
    return q.where(or_(
        StudentProfile.real_name.like(pattern),
        StudentProfile.student_no.like(pattern),
        InternshipRecord.position_name.like(pattern),
        InternshipRecord.enterprise_mentor_name.like(pattern),
    ))


def _latest_eval_map(db, *, context, internship_ids: list[int]) -> dict[int, InternshipEnterpriseEval]:
    if not internship_ids:
        return {}
    rows = db.scalars(
        select(InternshipEnterpriseEval)
        .where(
            InternshipEnterpriseEval.tenant_id == context.tenant_id,
            InternshipEnterpriseEval.internship_id.in_(internship_ids),
            InternshipEnterpriseEval.is_deleted.is_(False),
        )
        .order_by(InternshipEnterpriseEval.id.desc())
    ).all()
    result: dict[int, InternshipEnterpriseEval] = {}
    for row in rows:
        result.setdefault(int(row.internship_id), row)
    return result


def _record_row(record: InternshipRecord, student: StudentProfile, evaluation: InternshipEnterpriseEval | None) -> dict:
    pending_eval = evaluation is None or evaluation.school_review_status == "RETURNED"
    return {
        "id": str(record.id),
        "internshipId": str(record.id),
        "name": student.real_name,
        "positionName": record.position_name or "",
        "advisorName": record.advisor_name or "",
        "mentorName": record.enterprise_mentor_name or "",
        "status": record.status,
        "statusLabel": record.status,
        "riskLevel": record.risk_level,
        "startDate": _iso(record.intern_start_date),
        "endDate": _iso(record.intern_end_date),
        "evaluationTaskId": str(record.id) if pending_eval else None,
        "evaluationStatus": "PENDING" if pending_eval else "COMPLETED",
    }


def list_students_in_tx(db, *, context, page: int, page_size: int, status: str | None = None, keyword: str | None = None) -> dict:
    mentor_contact_id = _mentor_scope(db, context)
    q = (
        select(InternshipRecord, StudentProfile)
        .join(StudentProfile, StudentProfile.id == InternshipRecord.student_id)
        .where(*_record_conditions(context, mentor_contact_id))
    )
    q = _filter_keyword(_filter_record_status(q, status), keyword)
    total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
    pairs = db.execute(
        q.order_by(InternshipRecord.id.desc())
        .offset((max(1, page) - 1) * page_size)
        .limit(page_size)
    ).all()
    ids = [int(record.id) for record, _student in pairs]
    evals = _latest_eval_map(db, context=context, internship_ids=ids)
    return {
        "items": [_record_row(record, student, evals.get(int(record.id))) for record, student in pairs],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasNext": page * page_size < total,
    }


def get_student_in_tx(db, *, context, internship_id: int) -> dict:
    mentor_contact_id = _mentor_scope(db, context)
    pair = db.execute(
        select(InternshipRecord, StudentProfile)
        .join(StudentProfile, StudentProfile.id == InternshipRecord.student_id)
        .where(InternshipRecord.id == int(internship_id), *_record_conditions(context, mentor_contact_id))
    ).first()
    if not pair:
        raise not_found("实习记录不存在或不属于当前企业协同范围")
    record, student = pair
    evaluation = _latest_eval_map(db, context=context, internship_ids=[int(record.id)]).get(int(record.id))
    return _record_row(record, student, evaluation)


def _latest_eval_subquery(context):
    return (
        select(
            InternshipEnterpriseEval.internship_id.label("internship_id"),
            func.max(InternshipEnterpriseEval.id).label("evaluation_id"),
        )
        .where(
            InternshipEnterpriseEval.tenant_id == context.tenant_id,
            InternshipEnterpriseEval.is_deleted.is_(False),
        )
        .group_by(InternshipEnterpriseEval.internship_id)
        .subquery()
    )


def _task_row(record: InternshipRecord, student: StudentProfile, evaluation: InternshipEnterpriseEval | None) -> dict:
    pending = evaluation is None or evaluation.school_review_status == "RETURNED"
    payload = {
        "id": str(record.id),
        "taskId": str(record.id),
        "internshipId": str(record.id),
        "studentName": student.real_name,
        "positionName": record.position_name or "",
        "mentorName": record.enterprise_mentor_name or "",
        "status": "PENDING" if pending else "COMPLETED",
        "statusLabel": "待评价" if pending else "已提交",
        "deadline": _iso(record.intern_end_date),
        "evaluationId": str(evaluation.id) if evaluation else None,
        "evaluationVersion": int(evaluation.version or 0) if evaluation else None,
        "schoolReviewStatus": evaluation.school_review_status if evaluation else None,
    }
    if evaluation and evaluation.school_review_status == "RETURNED":
        payload.update({
            "attendanceScore": evaluation.attendance_score,
            "skillScore": evaluation.skill_score,
            "attitudeScore": evaluation.attitude_score,
            "collaborationScore": evaluation.collaboration_score,
            "safetyScore": evaluation.safety_score,
            "overallComment": evaluation.overall_comment or "",
            "recommendHire": bool(evaluation.recommend_hire),
            "returnReason": evaluation.school_review_comment or "",
        })
    return payload


def list_evaluation_tasks_in_tx(db, *, context, page: int, page_size: int, status: str | None = None) -> dict:
    mentor_contact_id = _mentor_scope(db, context)
    latest = _latest_eval_subquery(context)
    base = (
        select(InternshipRecord, StudentProfile, InternshipEnterpriseEval)
        .join(StudentProfile, StudentProfile.id == InternshipRecord.student_id)
        .outerjoin(latest, latest.c.internship_id == InternshipRecord.id)
        .outerjoin(InternshipEnterpriseEval, InternshipEnterpriseEval.id == latest.c.evaluation_id)
        .where(*_record_conditions(context, mentor_contact_id))
    )
    normalized = str(status or "ALL").upper()
    if normalized == "PENDING":
        base = base.where(or_(
            InternshipEnterpriseEval.id.is_(None),
            InternshipEnterpriseEval.school_review_status == "RETURNED",
        ))
    elif normalized == "COMPLETED":
        base = base.where(
            InternshipEnterpriseEval.id.is_not(None),
            InternshipEnterpriseEval.school_review_status != "RETURNED",
        )
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = db.execute(
        base.order_by(InternshipRecord.id.desc())
        .offset((max(1, page) - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_task_row(record, student, evaluation) for record, student, evaluation in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasNext": page * page_size < total,
    }


def _score_values(payload: dict[str, Any]) -> dict[str, int]:
    values: dict[str, int] = {}
    for json_key, column, label in _SCORE_FIELDS:
        value = payload.get(json_key)
        if value is None or value == "":
            raise AppException("VALIDATION_ERROR", f"{label}评分必填")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", f"{label}评分必须是 0-100 的整数") from exc
        if not 0 <= parsed <= 100:
            raise AppException("VALIDATION_ERROR", f"{label}评分必须在 0-100 之间")
        values[column] = parsed
    return values


def _mentor_identity(db, context) -> tuple[int | None, str]:
    member = _member(db, context)
    contact = None
    if member.contact_id:
        contact = db.scalar(
            select(InternshipEnterpriseContact).where(
                InternshipEnterpriseContact.id == member.contact_id,
                InternshipEnterpriseContact.tenant_id == context.tenant_id,
                InternshipEnterpriseContact.company_id == context.company_id,
                InternshipEnterpriseContact.is_deleted.is_(False),
            )
        )
    return (
        int(member.contact_id) if member.contact_id else None,
        contact.name if contact else f"企业{context.member_role}",
    )


def submit_evaluation_in_tx(db, *, context, internship_id: int, payload: dict[str, Any]) -> dict:
    mentor_contact_id = _mentor_scope(db, context)
    record = db.scalar(
        select(InternshipRecord)
        .join(StudentProfile, StudentProfile.id == InternshipRecord.student_id)
        .where(InternshipRecord.id == int(internship_id), *_record_conditions(context, mentor_contact_id))
        .with_for_update()
    )
    if not record:
        raise not_found("实习记录不存在或不属于当前企业协同范围")

    evaluation = db.scalar(
        select(InternshipEnterpriseEval)
        .where(
            InternshipEnterpriseEval.tenant_id == context.tenant_id,
            InternshipEnterpriseEval.internship_id == record.id,
            InternshipEnterpriseEval.is_deleted.is_(False),
        )
        .order_by(InternshipEnterpriseEval.id.desc())
        .with_for_update()
    )
    if evaluation and evaluation.school_review_status != "RETURNED":
        raise AppException("DATA_CONFLICT", "该学生企业评价已提交，不能重复评价")
    if evaluation:
        expected = payload.get("expectedVersion")
        if expected is None or int(expected) != int(evaluation.version or 0):
            raise AppException("DATA_CONFLICT", "企业评价版本已变化，请刷新后重试")

    comment = str(payload.get("overallComment") or "").strip()
    if not comment:
        raise AppException("VALIDATION_ERROR", "总体评价必填")
    if len(comment) > 2000:
        raise AppException("VALIDATION_ERROR", "总体评价不能超过 2000 字")
    scores = _score_values(payload)
    contact_id, mentor_name = _mentor_identity(db, context)

    if evaluation is None:
        evaluation = InternshipEnterpriseEval(
            tenant_id=context.tenant_id,
            internship_id=record.id,
            student_id=record.student_id,
            batch_id=record.batch_id,
            position_name=record.position_name,
            source="ENTERPRISE",
            source_type="ENTERPRISE_ONLINE",
        )
        db.add(evaluation)
    else:
        evaluation.version = int(evaluation.version or 0) + 1
        evaluation.school_review_comment = None
        evaluation.reviewed_by_name = None
        evaluation.reviewed_at = None

    evaluation.mentor_name = mentor_name
    evaluation.enterprise_contact_id = contact_id
    evaluation.overall_comment = comment
    evaluation.recommend_hire = bool(payload.get("recommendHire"))
    evaluation.recorded_by_user_id = str(context.user_id)
    evaluation.recorded_by_name = mentor_name
    evaluation.recorded_at = datetime.utcnow()
    evaluation.submit_status = "SUBMITTED"
    evaluation.school_review_status = "PENDING"
    for column, value in scores.items():
        setattr(evaluation, column, value)
    db.flush()

    db.add(InternshipAuditTrail(
        tenant_id=context.tenant_id,
        target_id=evaluation.id,
        target_type="ENT_EVAL",
        action="ENTERPRISE_ONLINE_SUBMIT",
        operator_name=mentor_name,
        detail_json={
            "sourceType": "ENTERPRISE_ONLINE",
            "enterpriseMemberId": str(context.member_id),
            "enterpriseUserId": str(context.user_id),
            "companyId": str(context.company_id),
            "internshipId": str(record.id),
            "version": int(evaluation.version or 0),
        },
        occurred_at=datetime.utcnow(),
    ))
    return {
        "id": str(evaluation.id),
        "internshipId": str(record.id),
        "sourceType": "ENTERPRISE_ONLINE",
        "reviewStatus": "PENDING",
        "version": int(evaluation.version or 0),
    }
