"""D8-U2 / C-W5 成绩任务列表只读 SQL 分页。

GET /grade-tasks keeps COUNT + LIMIT/OFFSET in SQL. C-W5 additionally makes a
linked AaTeachingTask the live teacher authority: after a teacher replacement the
old teacher loses the task immediately and the new teacher sees it without rewriting
the historical AaGradeTask.teacher_key snapshot.

The projection also publishes one status/action vocabulary for PC and miniapp.
Deadline fields are intentionally absent until the INT-owned GradeTask deadline
schema exists; this service never invents ``term.end_date`` as a fake deadline.
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_service as _grade_public

_MAX_PAGE_SIZE = 200
_TEACHER_EDITABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}


def _scope_conditions(db, user, status=None):
    """Build the canonical grade-task scope, using live TeachingTask ownership."""
    from app.models import AaGradeTask, AaTeachingTask

    conditions = [
        AaGradeTask.tenant_id == _core._tid(),
        AaGradeTask.is_deleted.is_(False),
    ]
    if status:
        conditions.append(AaGradeTask.status == str(status).upper())

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


def _allowed_actions(task, user, authority_ready: bool) -> list[str]:
    """Status-level actions only; command endpoints still re-check permission + state."""
    status = str(task.status or "").upper()
    role = str((user or {}).get("currentRoleCode") or "").upper()
    actions = ["VIEW"]

    if (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN":
        role = "SCHOOL_ADMIN"

    if role in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}:
        if status == "ACADEMIC_REVIEW":
            actions.extend(["PUBLISH", "RETURN"])
        if status == "PUBLISHED":
            actions.append("ARCHIVE")
        return actions

    if role == "COLLEGE_ADMIN":
        if status == "SUBMITTED":
            actions.append("COLLEGE_REVIEW")
        return actions

    if not authority_ready:
        return actions
    if status in _TEACHER_EDITABLE:
        actions.extend(["INPUT", "IMPORT"])
        if status in {"INPUTTING", "RETURNED"}:
            actions.append("SUBMIT")
    elif status == "PUBLISHED":
        actions.append("REQUEST_CHANGE")
    return actions


def list_tasks(user, status=None, page=1, page_size=20):
    """Return a bounded SQL page and project the current teacher assignment."""
    from app.models import AaGradeTask, AaTeachingTask

    page_no = max(1, int(page or 1))
    size = max(1, min(int(page_size or 20), _MAX_PAGE_SIZE))
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
                # Linked-but-missing teaching task is a broken authority. Do not
                # silently show the historical snapshot as if it were current.
                item["teacherKey"] = live_teacher_key or ""
                authority_ready = bool(live_teacher_key)
            else:
                authority_ready = bool(task.teacher_key)
            item["teacherAuthorityReady"] = authority_ready
            item["allowedActions"] = _allowed_actions(task, user, authority_ready)
            item["deadlineReady"] = False
            item["deadline"] = None
            item["isOverdue"] = None
            items.append(item)
        return items, total
