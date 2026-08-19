"""C15-18 effective-week data scope for teacher TeachingClass reads.

The mature teaching-class query service already enforces tenant/admin dataScope, but
its teacher branch treats any ACTIVE relation as permanently readable.  Formal
teacher execution now has week-bounded relations, so current class detail/roster
visibility must revoke with the same authority window.

Admins continue through the mature scope resolver unchanged.  Non-admin teachers
may read a TeachingClass only when one of their ACTIVE formal relations covers the
class's task-clamped non-occurrence authority week.  No class/roster/relation fact is
written here.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.core.permissions import is_super_admin
from app.core.affairs_security import no_data_scope
from app.services.db_service import _tid

from . import academic_affairs_teacher_relation_authority as teacher_authority
from . import academic_affairs_teaching_class_query_service as query_service

_ORIGINAL_ACCESSIBLE = query_service._accessible_rows


def _accessible_rows(db, user, rows):
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role in query_service._ADMIN_ROLES:
        return _ORIGINAL_ACCESSIBLE(db, user, rows)

    from app.models import AaTeachingClassTeacher

    keys = sorted(teacher_authority.user_keys(user))
    if not keys:
        raise no_data_scope("当前教师账号没有稳定工号，无法确认授课教学班")
    row_list = list(rows or [])
    if not row_list:
        return []
    class_by_id = {int(row.id): row for row in row_list}
    relation_rows = db.scalars(select(AaTeachingClassTeacher).where(
        AaTeachingClassTeacher.tenant_id == _tid(),
        AaTeachingClassTeacher.teaching_class_id.in_(sorted(class_by_id)),
        AaTeachingClassTeacher.teacher_key.in_(keys),
        AaTeachingClassTeacher.status == "ACTIVE",
        AaTeachingClassTeacher.is_deleted.is_(False),
    )).all()
    by_class = defaultdict(list)
    for relation in relation_rows:
        by_class[int(relation.teaching_class_id)].append(relation)

    allowed = []
    for teaching_class in row_list:
        if str(teaching_class.status or "").upper() != "ACTIVE":
            continue
        relations = by_class.get(int(teaching_class.id), [])
        if not relations:
            continue
        week = teacher_authority.class_authority_week(db, teaching_class)
        if any(teacher_authority.relation_covers_week(relation, week) for relation in relations):
            allowed.append(teaching_class)
    return allowed


_accessible_rows._teaching_class_effective_teacher_scope = True


def install() -> None:
    current = getattr(query_service, "_accessible_rows", None)
    if getattr(current, "_teaching_class_effective_teacher_scope", False):
        return
    if not hasattr(query_service, "_teacher_scope_guard_original_accessible_rows"):
        query_service._teacher_scope_guard_original_accessible_rows = current
    query_service._accessible_rows = _accessible_rows
