"""成绩操作审计的对象归属安全层。

历史实现把 ``AffairsAuditTrail.operator``（展示姓名）与 ``_user_keys``（稳定 userId/login）直接比较，
导致普通任课教师的“本人审计”永久查空。不能把 realName 加回身份键：同名教师会互相命中。
本层对 ACADEMIC_TEACHER 使用正式任务任课关系，AA_GRADE_RECORD 按其所属任务；
无法证明归属的成绩单导出等审计行 fail-closed 不返回。
校级保留原行为；学院审计按既有成绩任务/学生对象范围收敛，未知对象类型不扩权。
教师复用正式教学任务关系，使用 SQL 子查询避免全量装载任务与成绩明细 ID。
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_service as _public

_ORIGINAL = _core.list_grade_audit


def list_grade_audit(user, biz_type=None, page=1, page_size=50):
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role not in {"ACADEMIC_TEACHER", "COLLEGE_ADMIN"} or (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN":
        return _ORIGINAL(user, biz_type=biz_type, page=page, page_size=page_size)

    from app.models import AaGradeRecord, AaGradeTask, AffairsAuditTrail

    with _core.session() as db:
        from .academic_affairs_grade_task_read_service import _base_query, _scope_conditions

        task_ids = _base_query().with_only_columns(AaGradeTask.id).where(*_scope_conditions(db, user))
        record_ids = select(AaGradeRecord.id).where(
            AaGradeRecord.tenant_id == _core._tid(), AaGradeRecord.is_deleted.is_(False),
            AaGradeRecord.task_id.in_(task_ids),
        )
        object_scope = [
            and_(AffairsAuditTrail.biz_type == "AA_GRADE_TASK", AffairsAuditTrail.biz_id.in_(task_ids)),
            and_(AffairsAuditTrail.biz_type == "AA_GRADE_RECORD", AffairsAuditTrail.biz_id.in_(record_ids)),
        ]
        if role == "COLLEGE_ADMIN":
            from app.core.affairs_security import build_affairs_context
            from app.models import StudentProfile

            allowed = build_affairs_context(user, db).allowed_class_ids(db)
            students = select(StudentProfile.id).where(
                StudentProfile.tenant_id == _core._tid(), StudentProfile.is_deleted.is_(False),
            )
            if allowed is not None:
                students = students.where(StudentProfile.class_id.in_(list(allowed) or [-1]))
            object_scope.append(and_(AffairsAuditTrail.biz_type == "AA_GRADE_TRANSCRIPT",
                                     AffairsAuditTrail.biz_id.in_(students)))
        conditions = [
            AffairsAuditTrail.tenant_id == _core._tid(), AffairsAuditTrail.biz_type.like("AA_GRADE%"),
            or_(*object_scope),
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
            "beforeValue": row.before_val,
            "afterValue": row.after_val,
            "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
        } for row in rows]
        return items, int(total)


def install() -> None:
    _core.list_grade_audit = list_grade_audit
    _public.list_grade_audit = list_grade_audit
