"""D8-U2 / C-W5 成绩任务列表只读 SQL 分页。

GET /grade-tasks keeps COUNT + LIMIT/OFFSET in SQL.  C-W5 additionally makes a
linked AaTeachingTask the live teacher authority: after a teacher replacement the
old teacher must lose the task immediately instead of remaining visible through the
AaGradeTask.teacher_key creation snapshot.
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_service as _grade_public


def _scope_conditions(db, user, status=None):
    """Build the canonical grade-task scope, using live TeachingTask ownership."""
    from app.models import AaGradeTask, AaTeachingTask

    conditions = [
        AaGradeTask.tenant_id == _core._tid(),
        AaGradeTask.is_deleted.is_(False),
    ]
    if status:
        conditions.append(AaGradeTask.status == status)

    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role in _core._REVIEW_ROLES or (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN":
        return conditions
    if role == "COLLEGE_ADMIN":
        from app.core.affairs_security import build_affairs_context

        context = build_affairs_context(user, db)
        allowed = context.allowed_class_ids(db)
        if allowed is not None:
            conditions.append(AaGradeTask.class_id.in_(list(allowed) or [0]))
        return conditions

    keys = list(_core._user_keys(user or {})) or ["__none__"]
    conditions.append(
        or_(
            and_(
                AaGradeTask.teaching_task_id.is_not(None),
                AaTeachingTask.id == AaGradeTask.teaching_task_id,
                AaTeachingTask.tenant_id == _core._tid(),
                AaTeachingTask.is_deleted.is_(False),
                AaTeachingTask.teacher_key.in_(keys),
            ),
            and_(
                AaGradeTask.teaching_task_id.is_(None),
                AaGradeTask.teacher_key.in_(keys),
            ),
        )
    )
    return conditions


def _base_query():
    from app.models import AaGradeTask, AaTeachingTask

    return select(AaGradeTask, AaTeachingTask.teacher_key).outerjoin(
        AaTeachingTask,
        and_(
            AaTeachingTask.id == AaGradeTask.teaching_task_id,
            AaTeachingTask.tenant_id == AaGradeTask.tenant_id,
            AaTeachingTask.is_deleted.is_(False),
        ),
    )


def list_tasks(user, status=None, page=1, page_size=20):
    """Return only the requested page and project the current teacher assignment."""
    from app.models import AaGradeTask, AaTeachingTask

    page_no = max(1, int(page))
    size = int(page_size)
    with _core.session() as db:
        conditions = _scope_conditions(db, user, status)
        total = int(
            db.scalar(
                select(func.count(AaGradeTask.id))
                .select_from(AaGradeTask)
                .outerjoin(
                    AaTeachingTask,
                    and_(
                        AaTeachingTask.id == AaGradeTask.teaching_task_id,
                        AaTeachingTask.tenant_id == AaGradeTask.tenant_id,
                        AaTeachingTask.is_deleted.is_(False),
                    ),
                )
                .where(*conditions)
            )
            or 0
        )
        if size <= 0:
            return [], total

        result = db.execute(
            _base_query()
            .where(*conditions)
            .order_by(AaGradeTask.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        items = []
        for task, live_teacher_key in result:
            item = _grade_public._task_row(task)
            if task.teaching_task_id:
                # Linked-but-missing teaching task is a broken authority.  Do not
                # silently show the historical snapshot as if it were current.
                item["teacherKey"] = live_teacher_key or ""
                item["teacherAuthorityReady"] = bool(live_teacher_key)
            else:
                item["teacherAuthorityReady"] = bool(task.teacher_key)
            items.append(item)
        return items, total
