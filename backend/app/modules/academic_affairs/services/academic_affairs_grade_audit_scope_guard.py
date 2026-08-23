"""成绩操作审计的对象归属安全层。

历史实现把 ``AffairsAuditTrail.operator``（展示姓名）与 ``_user_keys``（稳定 userId/login）直接比较，
导致普通任课教师的“本人审计”永久查空。不能把 realName 加回身份键：同名教师会互相命中。
本层只对 ACADEMIC_TEACHER 收紧为真实业务对象归属：AA_GRADE_TASK 按 teacher_key，
AA_GRADE_RECORD 按其所属任务；无法证明归属的成绩单导出等审计行 fail-closed 不返回。
校级/院级既有行为保持原实现。
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_service as _public

_ORIGINAL = _core.list_grade_audit


def list_grade_audit(user, biz_type=None, page=1, page_size=50):
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role != "ACADEMIC_TEACHER":
        return _ORIGINAL(user, biz_type=biz_type, page=page, page_size=page_size)

    from app.models import AaGradeRecord, AaGradeTask, AffairsAuditTrail

    with _core.session() as db:
        keys = _core._user_keys(user)
        task_ids = db.scalars(select(AaGradeTask.id).where(
            AaGradeTask.tenant_id == _core._tid(),
            AaGradeTask.is_deleted.is_(False),
            AaGradeTask.teacher_key.in_(list(keys) or ["__none__"]),
        )).all()
        record_ids = db.scalars(select(AaGradeRecord.id).where(
            AaGradeRecord.tenant_id == _core._tid(),
            AaGradeRecord.is_deleted.is_(False),
            AaGradeRecord.task_id.in_(list(task_ids) or [-1]),
        )).all()

        conditions = [
            AffairsAuditTrail.tenant_id == _core._tid(),
            AffairsAuditTrail.biz_type.like("AA_GRADE%"),
            or_(
                and_(
                    AffairsAuditTrail.biz_type == "AA_GRADE_TASK",
                    AffairsAuditTrail.biz_id.in_(list(task_ids) or [-1]),
                ),
                and_(
                    AffairsAuditTrail.biz_type == "AA_GRADE_RECORD",
                    AffairsAuditTrail.biz_id.in_(list(record_ids) or [-1]),
                ),
            ),
        ]
        if biz_type:
            conditions.append(AffairsAuditTrail.biz_type == biz_type)
        total = db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(*conditions)) or 0
        offset = (max(1, int(page)) - 1) * int(page_size)
        rows = db.scalars(select(AffairsAuditTrail).where(*conditions)
                          .order_by(AffairsAuditTrail.id.desc()).offset(offset).limit(int(page_size))).all()
        items = [{
            "id": str(row.id),
            "bizType": row.biz_type,
            "bizId": str(row.biz_id) if row.biz_id else None,
            "action": row.action,
            "operator": row.operator,
            "roleName": row.role_name,
            "detail": row.detail,
            "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
        } for row in rows]
        return items, int(total)


def install() -> None:
    _core.list_grade_audit = list_grade_audit
    _public.list_grade_audit = list_grade_audit

    # High-risk grade state transitions share the same production audit boundary.
    # Install structured before/after evidence here so HTTP, scripts and internal callers
    # all get the same rule without changing authorization, workflow routing or statuses.
    from . import academic_affairs_grade_audit_evidence_guard
    academic_affairs_grade_audit_evidence_guard.install()
