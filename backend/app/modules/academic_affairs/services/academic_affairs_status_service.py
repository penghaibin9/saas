"""13B-P1 学籍状态单一写入口（Stage C1 temporal fact canonicalized）。

change_student_status() 是全平台允许发起学籍状态/组织归属生效的统一命令入口。
Stage C1 起，当前 ``StudentProfile`` 只是热路径投影；真正的学籍身份变化必须先经过
``append_student_academic_fact``，由同一事务完成：事实版本切换 + Profile CAS 投影 +
异动流水 + 360 事件。任何事实缺失、重叠或 Profile/fact 漂移都 fail-closed。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.services.db_service import _tid, audit_insert

STATUSES = {"NORMAL", "MERGED", "RECYCLED", "PENDING_REGISTER", "REGISTERED", "UNREGISTERED",
            "SUSPENDED", "PRESERVED", "RETAINED", "WITHDRAWN", "TRANSFER_SCHOOL", "GRADUATED",
            "COMPLETED", "INCOMPLETE"}

_ENROLLED = {"NORMAL", "REGISTERED", "RETAINED"}

_TRANSITIONS = {
    "NORMAL": {"PENDING_REGISTER", "REGISTERED", "SUSPENDED", "PRESERVED", "WITHDRAWN",
               "TRANSFER_SCHOOL", "GRADUATED", "COMPLETED", "INCOMPLETE", "RECYCLED"},
    "PENDING_REGISTER": {"REGISTERED", "UNREGISTERED"},
    "UNREGISTERED": {"PENDING_REGISTER", "REGISTERED", "WITHDRAWN"},
    "REGISTERED": {"REGISTERED", "SUSPENDED", "PRESERVED", "WITHDRAWN", "TRANSFER_SCHOOL",
                   "RETAINED", "GRADUATED", "COMPLETED", "INCOMPLETE"},
    "SUSPENDED": {"REGISTERED", "RESUME", "WITHDRAWN", "RETAINED"},
    "PRESERVED": {"REGISTERED", "WITHDRAWN"},
    "RETAINED": {"REGISTERED", "SUSPENDED", "WITHDRAWN"},
}


def is_enrolled(student_status: str | None) -> bool:
    """REGISTERED/NORMAL/RETAINED count as currently enrolled."""
    return (student_status or "NORMAL") in _ENROLLED


def can_transition(from_status: str | None, to_status: str) -> bool:
    frm = from_status or "NORMAL"
    if frm == to_status and to_status in ("REGISTERED",):
        return True
    return to_status in _TRANSITIONS.get(frm, set())


def change_student_status(db, student_id, to_status, change_type, reason="", operator="",
                          source_biz_id=None, term_code=None, existing_change_id=None,
                          to_college_id=None, to_major_id=None, to_class_id=None,
                          expected_student_version=None, effective_at=None) -> dict:
    """Canonical academic-identity apply command. Caller owns commit/rollback.

    ``effective_at`` is the business-effective timestamp. For immediate changes it is
    omitted and resolves to now. A scheduled worker may pass a due timestamp in the
    past; a timestamp still in the future is rejected by the canonical fact command.
    """
    from app.models import AaStatusChange, StudentProfile, StudentStageEvent
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
        append_student_academic_fact,
        resolve_student_academic_fact,
    )

    if to_status not in STATUSES:
        raise AppException("VALIDATION_ERROR", f"非法目标学籍状态：{to_status}")

    s = db.query(StudentProfile).filter(
        StudentProfile.id == int(student_id),
        StudentProfile.tenant_id == _tid(),
    ).with_for_update().first()
    if not s or s.is_deleted:
        raise AppException("DATA_NOT_FOUND", "学生不存在")
    if expected_student_version is not None and int(s.version or 0) != int(expected_student_version):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "学生主档在本申请在途期间已被改写，请重新核对后再终审",
            details={"expectedVersion": int(expected_student_version), "currentVersion": int(s.version or 0)},
            http_status=409,
        )

    frm = s.student_status
    if frm in ("MERGED", "RECYCLED", "WITHDRAWN", "GRADUATED") and to_status != frm:
        raise AppException("VALIDATION_ERROR", f"学生已处于终态 {frm}，不可再发起学籍异动")
    if not can_transition(frm, to_status):
        raise AppException("VALIDATION_ERROR", f"学籍状态不允许 {frm} → {to_status}")

    target_college = s.college_id if to_college_id is None else int(to_college_id)
    target_major = s.major_id if to_major_id is None else int(to_major_id)
    target_class = s.class_id if to_class_id is None else int(to_class_id)
    identity_changed = (
        to_status != frm
        or target_college != s.college_id
        or target_major != s.major_id
        or target_class != s.class_id
    )
    applied_at = effective_at or datetime.utcnow()

    if identity_changed:
        fact, s = append_student_academic_fact(
            db,
            int(student_id),
            effective_at=applied_at,
            student_status=to_status,
            college_id=target_college,
            major_id=target_major,
            class_id=target_class,
            source_type=change_type,
            source_ref_id=(int(existing_change_id) if existing_change_id else
                           int(source_biz_id) if source_biz_id else None),
            source_quality="EXACT",
            expected_student_version=expected_student_version,
            created_by=(int(operator) if str(operator or "").isdigit() else None),
        )
        fact_version = int(fact.version_no)
    else:
        fact = resolve_student_academic_fact(db, int(student_id), applied_at, for_update=True)
        fact_version = int(fact.version_no)

    if existing_change_id:
        row = db.get(AaStatusChange, int(existing_change_id))
        if row:
            row.from_status, row.to_status = frm, to_status
            if row.effective_date is None:
                row.effective_date = applied_at
            row.status = "EFFECTIVE"
    else:
        db.add(AaStatusChange(tenant_id=_tid(), student_id=int(student_id), change_type=change_type,
                              from_status=frm, to_status=to_status, reason=reason,
                              effective_date=applied_at, term_code=term_code,
                              source_biz_id=(int(source_biz_id) if source_biz_id else None),
                              status="EFFECTIVE"))

    db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(student_id), from_stage=frm,
                             to_stage=to_status, reason=f"学籍异动（{change_type}）",
                             source_module="academic-affairs"))
    return {"studentId": str(student_id), "fromStatus": frm, "toStatus": to_status,
            "changeType": change_type, "academicFactVersion": fact_version,
            "effectiveAt": applied_at.isoformat()}


def audit_status_change(student_id, from_status, to_status, change_type, operator=""):
    audit_insert("STUDENT_STATUS_CHANGE", "student_profile",
                 {"studentId": str(student_id), "from": from_status, "to": to_status,
                  "changeType": change_type, "operator": operator}, "SUCCESS")
