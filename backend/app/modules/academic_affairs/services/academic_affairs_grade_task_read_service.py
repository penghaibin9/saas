"""D8-U2 / C-W5 成绩任务列表只读 SQL 分页。

GET /grade-tasks keeps COUNT + LIMIT/OFFSET in SQL. For teacher-facing scope the
formal authority is ``AaTeachingClassTeacher`` + the linked TeachingTask's effective
window whenever a teaching-class projection exists. ``AaTeachingTask.teacher_key``
is used only for not-yet-projected migration data; ``AaGradeTask.teacher_key`` is
only a final compatibility scope for tasks with no teaching_task_id.

The projection publishes one status/action/authority vocabulary for PC and miniapp.
C-W4 deadline fields consume the persisted GradeTask deadline schema in one bounded
page query; teacher authority weeks are batch-resolved for the same page. Neither
projection fans out per row or invents ``term.end_date`` as a deadline.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, exists, func, or_, select

from . import academic_affairs_grade_core_service as _core
from . import academic_affairs_grade_deadline_service as _deadline
from . import academic_affairs_grade_service as _grade_public
from . import academic_affairs_teacher_relation_authority as _teacher_authority

_MAX_PAGE_SIZE = 200
_TEACHER_EDITABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}
_REMINDABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}


def _user_relation_task_ids(db, user) -> set[int]:
    """Resolve this teacher's formal task IDs with one batch authority-week projection."""
    from app.models import AaTeachingClass, AaTeachingClassTeacher

    keys = sorted(_teacher_authority.user_keys(user))
    if not keys:
        return set()
    rows = db.execute(
        select(AaTeachingClassTeacher, AaTeachingClass)
        .join(AaTeachingClass, AaTeachingClass.id == AaTeachingClassTeacher.teaching_class_id)
        .where(
            AaTeachingClassTeacher.tenant_id == _core._tid(),
            AaTeachingClassTeacher.teacher_key.in_(keys),
            AaTeachingClassTeacher.status == "ACTIVE",
            AaTeachingClassTeacher.is_deleted.is_(False),
            AaTeachingClass.tenant_id == _core._tid(),
            AaTeachingClass.status == "ACTIVE",
            AaTeachingClass.is_deleted.is_(False),
        )
    ).all()
    class_by_id = {int(teaching_class.id): teaching_class for _relation, teaching_class in rows}
    week_by_class = _teacher_authority.class_authority_weeks(db, class_by_id.values())
    task_ids: set[int] = set()
    for relation, teaching_class in rows:
        week = week_by_class.get(int(teaching_class.id))
        if (relation.start_week is not None or relation.end_week is not None) and week is None:
            continue
        if _teacher_authority.relation_covers_week(relation, week):
            task_ids.add(int(teaching_class.teaching_task_id))
    return task_ids


def _scope_conditions(db, user, status=None):
    """Build canonical grade-task scope with relation-first teacher authority."""
    from app.models import AaGradeTask, AaTeachingClass, AaTeachingTask

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

    keys = list(_teacher_authority.user_keys(user)) or ["__none__"]
    formal_task_ids = sorted(_user_relation_task_ids(db, user))
    projected_class_exists = exists(
        select(AaTeachingClass.id).where(
            AaTeachingClass.tenant_id == _core._tid(),
            AaTeachingClass.teaching_task_id == AaGradeTask.teaching_task_id,
            AaTeachingClass.is_deleted.is_(False),
        )
    )
    conditions.append(
        or_(
            AaGradeTask.teaching_task_id.in_(formal_task_ids or [-1]),
            and_(
                AaGradeTask.teaching_task_id.is_not(None),
                ~projected_class_exists,
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


def _formal_teacher_projection(db, teaching_task_ids) -> dict[int, dict]:
    """Batch-project current formal teachers and authority weeks for one page."""
    from app.models import AaTeachingClass, AaTeachingClassTeacher

    ids = sorted({int(value) for value in teaching_task_ids if value})
    if not ids:
        return {}
    classes = db.scalars(select(AaTeachingClass).where(
        AaTeachingClass.tenant_id == _core._tid(),
        AaTeachingClass.teaching_task_id.in_(ids),
        AaTeachingClass.is_deleted.is_(False),
    )).all()
    class_by_id = {int(row.id): row for row in classes}
    relation_rows = []
    if class_by_id:
        relation_rows = db.scalars(select(AaTeachingClassTeacher).where(
            AaTeachingClassTeacher.tenant_id == _core._tid(),
            AaTeachingClassTeacher.teaching_class_id.in_(sorted(class_by_id)),
            AaTeachingClassTeacher.status == "ACTIVE",
            AaTeachingClassTeacher.is_deleted.is_(False),
        )).all()
    relations_by_class = defaultdict(list)
    for relation in relation_rows:
        relations_by_class[int(relation.teaching_class_id)].append(relation)
    week_by_class = _teacher_authority.class_authority_weeks(db, classes)

    result: dict[int, dict] = {}
    for teaching_class in classes:
        week = week_by_class.get(int(teaching_class.id))
        candidates = []
        relation_error = False
        for relation in relations_by_class.get(int(teaching_class.id), []):
            if relation.start_week is not None or relation.end_week is not None:
                if week is None:
                    relation_error = True
                    continue
            if _teacher_authority.relation_covers_week(relation, week):
                candidates.append(relation)
        candidates.sort(key=lambda row: (0 if str(row.role_type or "").upper() == "PRIMARY" else 1, int(row.id)))
        result[int(teaching_class.teaching_task_id)] = {
            "source": "TEACHING_CLASS_TEACHER",
            "teachingClassId": str(teaching_class.id),
            "teachingClassStatus": teaching_class.status,
            "authorityWeek": week,
            "teacherKeys": [str(row.teacher_key) for row in candidates if row.teacher_key],
            "teacherNames": [str(row.teacher_name or "") for row in candidates],
            "authorityReady": str(teaching_class.status or "").upper() == "ACTIVE" and bool(candidates) and not relation_error,
            "authorityError": "TASK_WEEK_UNRESOLVED" if relation_error else "",
        }
    return result


def _allowed_actions(task, user, authority_ready: bool, *, deadline_overdue: bool = False) -> list[str]:
    """Status-level actions only; command endpoints still re-check permission + state."""
    status = str(task.status or "").upper()
    role = str((user or {}).get("currentRoleCode") or "").upper()
    actions = ["VIEW"]

    if (user or {}).get("userType") == "PLATFORM_SUPER_ADMIN":
        role = "SCHOOL_ADMIN"

    if role in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}:
        if status in _REMINDABLE:
            actions.extend(["EXTEND_DEADLINE", "REMIND"])
        if status == "ACADEMIC_REVIEW":
            actions.extend(["PUBLISH", "RETURN"])
        if status == "PUBLISHED":
            actions.append("ARCHIVE")
        return actions

    if role == "COLLEGE_ADMIN":
        if status in _REMINDABLE:
            actions.extend(["EXTEND_DEADLINE", "REMIND"])
        if status == "SUBMITTED":
            actions.append("COLLEGE_REVIEW")
        return actions

    if not authority_ready:
        return actions
    if status in _TEACHER_EDITABLE:
        actions.extend(["INPUT", "IMPORT"])
        if status in {"INPUTTING", "RETURNED"} and not deadline_overdue:
            actions.append("SUBMIT")
    elif status == "PUBLISHED":
        actions.append("REQUEST_CHANGE")
    return actions


def list_tasks(user, status=None, page=1, page_size=20):
    """Return a bounded SQL page and batch-project teacher/deadline truth."""
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
        projection = _formal_teacher_projection(
            db,
            [task.teaching_task_id for task, _task_teacher in result if task.teaching_task_id],
        )
        deadline_projection = _deadline.deadline_projection_map(
            db,
            [(int(task.id), str(task.status or "")) for task, _task_teacher in result],
        )
        items = []
        for task, task_teacher_key in result:
            item = _grade_public._task_row(task)
            if task.teaching_task_id and int(task.teaching_task_id) in projection:
                authority = projection[int(task.teaching_task_id)]
                teacher_keys = authority["teacherKeys"]
                item["teacherKey"] = teacher_keys[0] if teacher_keys else ""
                item["teacherKeys"] = teacher_keys
                item["teacherNames"] = authority["teacherNames"]
                item["teacherAuthoritySource"] = authority["source"]
                item["teachingClassId"] = authority["teachingClassId"]
                item["authorityWeek"] = authority["authorityWeek"]
                item["teacherAuthorityError"] = authority["authorityError"]
                authority_ready = bool(authority["authorityReady"])
            elif task.teaching_task_id:
                item["teacherKey"] = task_teacher_key or ""
                item["teacherKeys"] = [task_teacher_key] if task_teacher_key else []
                item["teacherNames"] = []
                item["teacherAuthoritySource"] = "TEACHING_TASK_MIGRATION_FALLBACK"
                item["teachingClassId"] = None
                item["authorityWeek"] = None
                item["teacherAuthorityError"] = ""
                authority_ready = bool(task_teacher_key)
            else:
                item["teacherKeys"] = [task.teacher_key] if task.teacher_key else []
                item["teacherNames"] = []
                item["teacherAuthoritySource"] = "GRADE_TASK_COMPAT_SCOPE"
                item["teachingClassId"] = None
                item["authorityWeek"] = None
                item["teacherAuthorityError"] = ""
                authority_ready = bool(task.teacher_key)
            deadline_data = deadline_projection[int(task.id)]
            item["teacherAuthorityReady"] = authority_ready
            item["allowedActions"] = _allowed_actions(
                task,
                user,
                authority_ready,
                deadline_overdue=deadline_data.get("isOverdue") is True,
            )
            item.update(deadline_data)
            items.append(item)
        return items, total
