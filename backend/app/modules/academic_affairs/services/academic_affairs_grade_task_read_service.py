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


def _user_relation_task_ids(db, user, *, term_id=None) -> set[int]:
    """Resolve grade responsibility with the canonical clamped non-occurrence week."""
    scope = _teacher_authority.relation_scope(db, user, term_id=term_id)
    return {int(value) for value in scope.get("taskIds") or []}


def college_scope_condition(college_ids):
    """开课单位先于任务批次，与审批受理人共用同一归属链。"""
    from app.models import AaCourse, AaGradeTask, AaTeachingTask, AaTeachingTaskBatch

    teaching_course = select(AaTeachingTask.course_id).where(
        AaTeachingTask.id == AaGradeTask.teaching_task_id,
        AaTeachingTask.tenant_id == _core._tid(), AaTeachingTask.is_deleted.is_(False),
    ).correlate(AaGradeTask).scalar_subquery()
    owner = select(AaCourse.owner_college_id).where(
        AaCourse.id == func.coalesce(AaGradeTask.course_id, teaching_course), AaCourse.tenant_id == _core._tid(),
        AaCourse.is_deleted.is_(False),
    ).correlate(AaGradeTask).scalar_subquery()
    batch_owner = select(AaTeachingTaskBatch.college_id).join(
        AaTeachingTask, AaTeachingTask.batch_id == AaTeachingTaskBatch.id,
    ).where(
        AaTeachingTask.id == AaGradeTask.teaching_task_id,
        AaTeachingTask.tenant_id == _core._tid(), AaTeachingTask.is_deleted.is_(False),
        AaTeachingTaskBatch.tenant_id == _core._tid(), AaTeachingTaskBatch.is_deleted.is_(False),
    ).correlate(AaGradeTask).scalar_subquery()
    return func.coalesce(owner, batch_owner).in_(sorted(college_ids) or [-1])


def _scope_conditions(db, user, status=None, task_id=None, term_id=None):
    """Build canonical grade-task scope with relation-first teacher authority."""
    from app.models import AaGradeTask, AaTeachingClass, AaTeachingTask

    conditions = [
        AaGradeTask.tenant_id == _core._tid(),
        AaGradeTask.is_deleted.is_(False),
    ]
    if status:
        conditions.append(AaGradeTask.status == str(status).upper())
    if task_id is not None:
        conditions.append(AaGradeTask.id == int(task_id))
    if term_id is not None:
        conditions.append(AaGradeTask.term_id == int(term_id))

    from app.core.affairs_security import build_affairs_context
    context = build_affairs_context(user, db)
    if context.scope_type == "TENANT_ALL":
        return conditions
    if context.scope_type == "COLLEGE":
        conditions.append(college_scope_condition(context.college_ids))
        return conditions

    keys = list(_teacher_authority.user_keys(user)) or ["__none__"]
    formal_task_ids = sorted(_user_relation_task_ids(db, user, term_id=term_id))
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
    """Batch-project current formal teachers and clamped authority weeks for one page."""
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
            "teachingClassName": teaching_class.class_name,
            "teachingClassStatus": teaching_class.status,
            "authorityWeek": week,
            "teacherKeys": [str(row.teacher_key) for row in candidates if row.teacher_key],
            "teacherNames": [str(row.teacher_name or "") for row in candidates],
            "authorityReady": str(teaching_class.status or "").upper() == "ACTIVE" and bool(candidates) and not relation_error,
            "authorityError": "TASK_WEEK_UNRESOLVED" if relation_error else "",
        }
    return result


def _allowed_actions(task, user, authority_ready: bool, *, context, deadline_overdue: bool = False) -> list[str]:
    """Status-level actions only; command endpoints still re-check permission + state."""
    status = str(task.status or "").upper()
    from app.core.permissions import _match
    permitted = lambda action: _match("academicAffairs.grade." + action, context.permission_codes)
    actions = ["VIEW"]

    if context.scope_type == "TENANT_ALL":
        if status in _REMINDABLE and permitted("publish"):
            actions.extend(["EXTEND_DEADLINE", "REMIND"])
        if status == "ACADEMIC_REVIEW" and permitted("publish"):
            actions.extend(["PUBLISH", "RETURN"])
        if status == "PUBLISHED" and permitted("archive"):
            actions.append("ARCHIVE")
        return actions

    if context.scope_type == "COLLEGE" and permitted("collegeReview"):
        if status in _REMINDABLE:
            actions.extend(["EXTEND_DEADLINE", "REMIND"])
        if status == "SUBMITTED":
            actions.append("COLLEGE_REVIEW")
        return actions

    if not authority_ready:
        return actions
    if status in _TEACHER_EDITABLE:
        if permitted("input"):
            actions.extend(["INPUT", "IMPORT"])
        if status in {"INPUTTING", "RETURNED"} and not deadline_overdue and permitted("submit"):
            actions.append("SUBMIT")
    elif status == "PUBLISHED" and _match("academicAffairs.gradeChange.apply", context.permission_codes):
        actions.append("REQUEST_CHANGE")
    return actions


def list_tasks(user, status=None, page=1, page_size=20, *, task_id=None, term_id=None, term=None, keyword=None):
    """Return a bounded SQL page and batch-project teacher/deadline truth."""
    from app.models import AaGradeTask, AaTeachingTask

    page_no = max(1, int(page or 1))
    size = max(1, min(int(page_size or 20), _MAX_PAGE_SIZE))
    with _core.session() as db:
        from app.core.affairs_security import build_affairs_context
        context = build_affairs_context(user, db)
        conditions = _scope_conditions(db, user, status, task_id, term_id)
        if term:
            conditions.append(AaGradeTask.term_code == str(term).strip())
        if keyword and str(keyword).strip():
            conditions.append(AaGradeTask.course_name.contains(str(keyword).strip(), autoescape=True))
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
        from . import academic_affairs_responsibility_service as responsibility
        from .academic_affairs_grade_correction_command import _current_user_id, _task_college_id
        from app.core.exceptions import AppException
        teaching_tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _core._tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.id.in_([task.teaching_task_id for task, _ in result if task.teaching_task_id] or [-1]),
        )).all()
        from app.models import AaCourse, AaTeachingTaskBatch
        course_ids = {task.course_id for task, _ in result if task.course_id} | {task.course_id for task in teaching_tasks}
        # 保持强引用，让同页逐行归属校验复用 Session 身份映射，避免每行再次查课程与批次。
        _ownership_rows = [
            *db.scalars(select(AaCourse).where(AaCourse.tenant_id == _core._tid(), AaCourse.id.in_(course_ids or [-1]))).all(),
            *db.scalars(select(AaTeachingTaskBatch).where(AaTeachingTaskBatch.tenant_id == _core._tid(),
                AaTeachingTaskBatch.id.in_([task.batch_id for task in teaching_tasks] or [-1]))).all(),
        ]
        responsibility_cache = {}
        teacher_owners = responsibility.resolve_teachers(db, teaching_tasks,
            permission_code="academicAffairs.grade.input", cache=responsibility_cache)
        college_owners = {}
        school_owner = responsibility.resolve_school(db, permission_code="academicAffairs.grade.publish",
            cache=responsibility_cache) if result else None
        try:
            actor_id = str(_current_user_id(db, user)) if result else ""
        except AppException as error:
            if error.code != "NO_PERMISSION":
                raise
            actor_id = ""
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
                item["teachingClassName"] = authority["teachingClassName"]
                item["authorityWeek"] = authority["authorityWeek"]
                item["teacherAuthorityError"] = authority["authorityError"]
                authority_ready = bool(authority["authorityReady"])
            elif task.teaching_task_id:
                item["teacherKey"] = task_teacher_key or ""
                item["teacherKeys"] = [task_teacher_key] if task_teacher_key else []
                item["teacherNames"] = []
                item["teacherAuthoritySource"] = "TEACHING_TASK_MIGRATION_FALLBACK"
                item["teachingClassId"] = None
                item["teachingClassName"] = None
                item["authorityWeek"] = None
                item["teacherAuthorityError"] = ""
                authority_ready = bool(task_teacher_key)
            else:
                item["teacherKeys"] = [task.teacher_key] if task.teacher_key else []
                item["teacherNames"] = []
                item["teacherAuthoritySource"] = "GRADE_TASK_COMPAT_SCOPE"
                item["teachingClassId"] = None
                item["teachingClassName"] = None
                item["authorityWeek"] = None
                item["teacherAuthorityError"] = ""
                authority_ready = bool(task.teacher_key)
            deadline_data = deadline_projection[int(task.id)]
            item["teacherAuthorityReady"] = authority_ready
            item["allowedActions"] = _allowed_actions(
                task,
                user,
                authority_ready and bool(set(item["teacherKeys"]) & _teacher_authority.user_keys(user)),
                context=context,
                deadline_overdue=deadline_data.get("isOverdue") is True,
            )
            item.update(deadline_data)
            college_id = _task_college_id(db, task)
            if college_id not in college_owners:
                college_owners[college_id] = responsibility.resolve_organization(db, "COLLEGE", college_id,
                    permission_code="academicAffairs.grade.collegeReview", cache=responsibility_cache)
            college_owner = college_owners[college_id]
            if task.status == "SUBMITTED":
                item["responsibility"] = college_owner
                item["nextStep"] = {"code": "ACADEMIC_REVIEW", "label": "校教务发布成绩", "responsibility": school_owner}
                if actor_id not in college_owner["assigneeUserIds"]:
                    item["allowedActions"] = [action for action in item["allowedActions"] if action != "COLLEGE_REVIEW"]
            elif task.status in {"ACADEMIC_REVIEW", "PUBLISHED"}:
                item["responsibility"] = school_owner
                item["nextStep"] = None
                if task.status == "ACADEMIC_REVIEW" and school_owner["assigneeUserIds"] != [actor_id]:
                    item["allowedActions"] = [action for action in item["allowedActions"] if action not in {"PUBLISH", "RETURN"}]
            elif task.status in _TEACHER_EDITABLE:
                item["responsibility"] = teacher_owners.get(task.teaching_task_id)
                item["nextStep"] = {"code": "COLLEGE_REVIEW", "label": "开课学院审核", "responsibility": college_owner}
            else:
                item["responsibility"], item["nextStep"] = None, None
            items.append(item)
        return items, total
