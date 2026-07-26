from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import is_super_admin
from app.models import (
    InternshipAuditTrail, InternshipRecord, InternshipSpecialFiling,
)
from app.services.db_service import _as_id, _tid, session

_FILING_TYPES = {
    "CROSS_PROVINCE", "CROSS_CITY", "OVERSEAS", "HIGH_RISK", "NIGHT_SHIFT",
    "SPECIAL_TRADE", "MINOR", "REMOTE", "OTHER",
}
_COLLEGE_ROLES = {"COLLEGE_ADMIN", "INTERNSHIP_ADMIN", "INTERN_ADMIN", "COLLEGE_INTERNSHIP_ADMIN"}


def _op(user):
    return (user or {}).get("realName") or "系统"


def _uid(user):
    return str((user or {}).get("userId") or "")


def _role(user):
    return str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or "").upper()


def _audit(db, filing, action, user=None, detail=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=filing.id, target_type="SPECIAL_FILING",
        action=action, operator_name=_op(user), detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _get(db, filing_id, *, lock=False):
    query = select(InternshipSpecialFiling).where(
        InternshipSpecialFiling.id == _as_id(filing_id),
        InternshipSpecialFiling.tenant_id == _tid(),
        InternshipSpecialFiling.is_deleted.is_(False),
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise not_found("特殊备案不存在")
    return row


def evaluate_triggers(position, student=None, school_region=None):
    out = []
    if position and bool(getattr(position, "night_shift", False)):
        out.append(("NIGHT_SHIFT", "岗位包含夜班"))
    if position and bool(getattr(position, "hazardous_flag", False)):
        out.append(("HIGH_RISK", "岗位标记为危险/高风险"))
    region = getattr(position, "work_location", None) or getattr(position, "work_address", None) or ""
    if school_region and region and school_region not in region:
        out.append(("CROSS_PROVINCE", "岗位地点跨省"))
    birth = getattr(student, "birth_date", None) if student else None
    if birth:
        try:
            if hasattr(birth, "date"):
                birth = birth.date()
            today = datetime.utcnow().date()
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            if age < 18:
                out.append(("MINOR", "学生未满18周岁"))
        except Exception:
            pass
    return out


def create(body, user=None):
    b = body or {}
    internship_id = b.get("internshipId")
    if not internship_id:
        raise AppException("VALIDATION_ERROR", "internshipId 必填")
    filing_type = str(b.get("filingType") or "OTHER").upper()
    if filing_type not in _FILING_TYPES:
        raise AppException("VALIDATION_ERROR", "特殊备案类型无效")
    trigger_reason = str(b.get("triggerReason") or "").strip()
    risk_description = str(b.get("riskDescription") or "").strip()
    if len(trigger_reason) < 5:
        raise AppException("VALIDATION_ERROR", "触发原因必填且不少于5字")
    if filing_type in {"HIGH_RISK", "NIGHT_SHIFT", "OVERSEAS", "MINOR"} and len(risk_description) < 5:
        raise AppException("VALIDATION_ERROR", "该类型备案必须填写风险说明")
    file_ids = [str(x) for x in (b.get("fileIds") or []) if x]
    if not file_ids:
        raise AppException("VALIDATION_ERROR", "特殊备案至少上传一份依据材料")
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec = assert_internship_record_scope(db, internship_id, user, "创建特殊备案")
        active = db.scalars(select(InternshipSpecialFiling).where(
            InternshipSpecialFiling.tenant_id == _tid(),
            InternshipSpecialFiling.internship_id == rec.id,
            InternshipSpecialFiling.filing_type == filing_type,
            InternshipSpecialFiling.status.in_(("DRAFT", "PENDING_COLLEGE", "PENDING_SCHOOL", "APPROVED")),
            InternshipSpecialFiling.is_deleted.is_(False),
        ).with_for_update()).first()
        if active:
            raise AppException("DATA_CONFLICT", "该学生已有同类型有效或办理中的特殊备案")
        row = InternshipSpecialFiling(
            tenant_id=_tid(), internship_id=rec.id, batch_id=rec.batch_id,
            student_id=rec.student_id, filing_type=filing_type,
            trigger_reason=trigger_reason,
            destination_region=str(b.get("destinationRegion") or "").strip() or None,
            work_address=str(b.get("workAddress") or "").strip() or None,
            risk_description=risk_description or None,
            student_application=str(b.get("studentApplication") or "").strip() or None,
            guardian_consent_required=bool(b.get("guardianConsentRequired")),
            file_ids=file_ids, valid_until=b.get("validUntil"), status="DRAFT",
            requested_by_name=_op(user), requested_by_user_id=_uid(user),
        )
        db.add(row)
        db.flush()
        _audit(db, row, "CREATE", user, {
            "filingType": filing_type, "triggerReason": trigger_reason,
            "fileCount": len(file_ids), "version": int(row.version or 0),
        })
        db.commit()
        return {"id": str(row.id), "status": row.status, "version": int(row.version or 0)}


def submit(filing_id, user=None, expected_version=None):
    with session() as db:
        row = _get(db, filing_id, lock=True)
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db, row.internship_id, user, "提交特殊备案")
        if expected_version is None or int(expected_version) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "特殊备案版本已变化，请刷新后重试")
        if row.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿可提交")
        if not row.file_ids or not (row.trigger_reason or "").strip():
            raise AppException("VALIDATION_ERROR", "提交前必须具备触发原因和依据材料")
        before = row.status
        row.status = "PENDING_COLLEGE"
        row.version = int(row.version or 0) + 1
        _audit(db, row, "SUBMIT", user, {
            "beforeStatus": before, "afterStatus": row.status,
            "version": int(row.version or 0),
        })
        db.commit()
        return {"id": str(row.id), "status": row.status, "version": int(row.version or 0)}


def _assert_level_role(level, user):
    if is_super_admin(user or {}):
        return
    role = _role(user)
    if level == "COLLEGE" and role not in _COLLEGE_ROLES and role != "SCHOOL_ADMIN":
        raise no_permission("学院审核仅限学院或实习管理授权角色")
    if level == "SCHOOL" and role != "SCHOOL_ADMIN":
        raise no_permission("学校终审仅限学校管理员")


def review(filing_id, level, action, comment="", user=None, expected_version=None):
    level = str(level or "").upper()
    action = str(action or "").upper()
    if level not in ("COLLEGE", "SCHOOL") or action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "审核参数错误")
    _assert_level_role(level, user)
    reason = str(comment or "").strip()
    if action == "REJECT" and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
    with session() as db:
        row = _get(db, filing_id, lock=True)
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        assert_internship_record_scope(db, row.internship_id, user, "审核特殊备案")
        if expected_version is None or int(expected_version) != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "特殊备案版本已变化，请刷新后重试")
        expected = "PENDING_" + level
        if row.status != expected:
            raise AppException("DATA_CONFLICT", "当前备案不在该审核环节")
        actor_id = _uid(user)
        if actor_id and actor_id == str(row.requested_by_user_id or ""):
            raise no_permission("特殊备案申请人与审核人必须分离")
        before = row.status
        now = datetime.utcnow()
        if level == "COLLEGE":
            row.college_review_by = _op(user)
            row.college_review_at = now
            row.college_comment = reason or None
            row.status = "PENDING_SCHOOL" if action == "APPROVE" else "REJECTED"
        else:
            row.school_review_by = _op(user)
            row.school_review_at = now
            row.school_comment = reason or None
            row.status = "APPROVED" if action == "APPROVE" else "REJECTED"
            row.approved_by_name = _op(user) if action == "APPROVE" else None
            row.approved_at = now if action == "APPROVE" else None
        row.reviewed_by_name = _op(user)
        row.reviewed_at = now
        row.version = int(row.version or 0) + 1
        _audit(db, row, f"{level}_{action}", user, {
            "beforeStatus": before, "afterStatus": row.status,
            "comment": reason, "requesterUserId": str(row.requested_by_user_id or ""),
            "reviewerUserId": actor_id, "version": int(row.version or 0),
        })
        db.commit()
        return {"id": str(row.id), "status": row.status, "version": int(row.version or 0)}


def supersede_old(db, internship_id, user=None):
    rows = db.scalars(select(InternshipSpecialFiling).where(
        InternshipSpecialFiling.tenant_id == _tid(),
        InternshipSpecialFiling.internship_id == _as_id(internship_id),
        InternshipSpecialFiling.status == "APPROVED",
        InternshipSpecialFiling.is_deleted.is_(False),
    ).with_for_update()).all()
    for row in rows:
        before = row.status
        row.status = "SUPERSEDED"
        row.version = int(row.version or 0) + 1
        _audit(db, row, "SUPERSEDE", user, {
            "beforeStatus": before, "afterStatus": row.status,
            "version": int(row.version or 0),
        })
