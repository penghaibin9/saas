"""C15-18 formal TeachingClassTeacher management.

``AaTeachingClassTeacher`` is the production authority for PRIMARY/CO_TEACHER and
effective-week execution.  The model already existed, but without a management
command surface schools could only configure multi-teacher/week-split teaching by
editing MySQL directly.  This service provides the missing command contract while
preserving the mature TeachingTask/TeachingClass owners.

Rules:
- all writes require an ACTIVE teaching class in caller data scope + writable term;
- teacherKey must resolve to an ACTIVE real TEACHER account in the same tenant;
- exactly one ACTIVE PRIMARY relation is retained; PRIMARY identity may be replaced
  through update, while CO_TEACHER can be created/deactivated independently;
- every teaching week in the linked TeachingTask window must remain covered by at
  least one ACTIVE relation; overlaps are allowed for genuine co-teaching;
- a teacher's proposed window is checked against current ScopeHead formal schedules
  of their other teaching classes; overlapping weekday/slot/week/parity is rejected;
- changes are audited and pending AA_GRADE_ENTRY Todos are synchronized in the same
  transaction;
- no schedule item, attendance, grade, workload or roster fact is rewritten here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_teaching_class_change_service as class_change
from . import academic_affairs_grade_todo_teacher_relation_guard as grade_todo_guard
from . import academic_affairs_schedule_service as schedule_service
from . import academic_affairs_attendance_occurrence_consumer as occurrence

_ROLE_TYPES = {"PRIMARY", "CO_TEACHER"}
_PENDING_GRADE_STATUSES = {"NOT_STARTED", "INPUTTING", "RETURNED"}


def _reason(value) -> str:
    text = str(value or "").strip()
    if len(text) < 5:
        raise AppException("VALIDATION_ERROR", "教师关系变更原因必填且不少于5字")
    return text


def _teacher(db, teacher_key: str):
    from app.models import User

    key = str(teacher_key or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "teacherKey 必填")
    row = None
    if key.startswith("u_") and key[2:].isdigit():
        candidate = db.get(User, int(key[2:]))
        if candidate and candidate.tenant_id == _tid() and not candidate.is_deleted:
            row = candidate
    if row is None:
        row = db.scalars(select(User).where(
            User.tenant_id == _tid(),
            User.login_name == key,
            User.is_deleted.is_(False),
        )).first()
    if not row or str(row.status or "").upper() != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "教师账号不存在、已停用或不属于当前学校")
    if str(row.user_type or "").upper() != "TEACHER":
        raise AppException("VALIDATION_ERROR", "所选账号不是可授课的教师账号")
    return row


def _task_term(db, teaching_class):
    from app.models import AaTeachingTask, AaTerm

    task = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.id == int(teaching_class.teaching_task_id),
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    )).first()
    if not task:
        raise AppException("DATA_CONFLICT", "教学班无法回链有效教学任务", http_status=409)
    term = db.scalars(select(AaTerm).where(
        AaTerm.id == int(teaching_class.term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    )).first()
    if not term:
        raise AppException("DATA_CONFLICT", "教学班无法回链有效学期", http_status=409)
    return task, term


def _task_window(task, term) -> tuple[int, int]:
    teaching_weeks = int(getattr(term, "teaching_weeks", 0) or 0)
    start = int(task.start_week) if task.start_week is not None else 1
    end = int(task.end_week) if task.end_week is not None else teaching_weeks
    if start <= 0 or end <= 0 or end < start:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务缺少合法的起止周，不能管理教师有效周次",
            details={"teachingTaskId": str(task.id), "startWeek": task.start_week, "endWeek": task.end_week},
            http_status=409,
        )
    if teaching_weeks and end > teaching_weeks:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务结束周超出学期教学周",
            details={"teachingTaskId": str(task.id), "endWeek": end, "teachingWeeks": teaching_weeks},
            http_status=409,
        )
    return start, end


def _window(task, term, start_week=None, end_week=None) -> tuple[int, int]:
    task_start, task_end = _task_window(task, term)
    start = task_start if start_week is None else int(start_week)
    end = task_end if end_week is None else int(end_week)
    if start < task_start or end > task_end or start > end:
        raise AppException(
            "VALIDATION_ERROR",
            f"教师有效周次必须落在教学任务 {task_start}-{task_end} 周范围内",
            details={"taskStartWeek": task_start, "taskEndWeek": task_end, "startWeek": start, "endWeek": end},
        )
    return start, end


def _active_relations(db, teaching_class_id: int, *, lock=False):
    from app.models import AaTeachingClassTeacher

    query = db.query(AaTeachingClassTeacher).filter(
        AaTeachingClassTeacher.tenant_id == _tid(),
        AaTeachingClassTeacher.teaching_class_id == int(teaching_class_id),
        AaTeachingClassTeacher.status == "ACTIVE",
        AaTeachingClassTeacher.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    return query.order_by(AaTeachingClassTeacher.role_type, AaTeachingClassTeacher.id).all()


def _validate_topology(task, term, relations) -> None:
    rows = list(relations or [])
    primaries = [row for row in rows if str(row.role_type or "").upper() == "PRIMARY"]
    if len(primaries) != 1:
        raise AppException(
            "DATA_CONFLICT",
            "正式教师关系必须且只能保留1名 ACTIVE PRIMARY 教师",
            details={"activePrimaryCount": len(primaries)},
            http_status=409,
        )
    task_start, task_end = _task_window(task, term)
    gaps = []
    for week in range(task_start, task_end + 1):
        if not any(
            int(row.start_week if row.start_week is not None else task_start) <= week
            <= int(row.end_week if row.end_week is not None else task_end)
            for row in rows
        ):
            gaps.append(week)
    if gaps:
        raise AppException(
            "DATA_CONFLICT",
            "教师关系变更后存在无人授课周次，请先补齐教师覆盖再缩短/停用现有关系",
            details={"uncoveredWeeks": gaps},
            http_status=409,
        )


def _relation_dto(row) -> dict:
    return {
        "teacherRelationId": str(row.id),
        "teacherId": str(row.teacher_id or ""),
        "teacherKey": row.teacher_key,
        "teacherName": row.teacher_name or "",
        "roleType": row.role_type,
        "startWeek": row.start_week,
        "endWeek": row.end_week,
        "status": row.status,
    }


def _audit(db, teaching_class, action: str, detail: str) -> None:
    from app.models import AffairsAuditTrail

    ctx = get_current_user_ctx() or {}
    db.add(AffairsAuditTrail(
        tenant_id=_tid(),
        biz_type="AA_TEACHING_CLASS_TEACHER",
        biz_id=int(teaching_class.id),
        action=action,
        operator=str(ctx.get("userId") or ctx.get("loginName") or ""),
        role_name=str(ctx.get("currentRoleCode") or ""),
        detail=str(detail or "")[:990],
        occurred_at=datetime.utcnow(),
    ))


def _sync_grade_todo(db, teaching_class) -> None:
    from app.models import AaGradeTask

    task = db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.teaching_task_id == int(teaching_class.teaching_task_id),
        AaGradeTask.is_deleted.is_(False),
    ).order_by(AaGradeTask.id.asc())).first()
    if task is not None and str(task.status or "").upper() in _PENDING_GRADE_STATUSES:
        grade_todo_guard.sync_grade_entry_todos(db, task)


def _pattern_windows(patterns, start_week: int, end_week: int):
    output = []
    for pattern in patterns or []:
        start = max(int(pattern.get("startWeek") or 0), int(start_week))
        end = min(int(pattern.get("endWeek") or 0), int(end_week))
        if start <= end:
            output.append({**pattern, "startWeek": start, "endWeek": end})
    return output


def _patterns_conflict(left, right) -> bool:
    if int(left.get("weekday") or 0) != int(right.get("weekday") or 0):
        return False
    if int(left.get("slotNo") or 0) != int(right.get("slotNo") or 0):
        return False
    return schedule_service._weeks_overlap(
        int(left.get("startWeek") or 0), int(left.get("endWeek") or 0), str(left.get("weekParity") or "ALL"),
        int(right.get("startWeek") or 0), int(right.get("endWeek") or 0), str(right.get("weekParity") or "ALL"),
    )


def _schedule_conflict_check(db, teaching_class, teacher_key: str, start_week: int, end_week: int, *, exclude_relation_id=None) -> None:
    """Fail on current formal schedule collisions with this teacher's other classes."""
    from app.models import AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch, AaTerm

    task, term = _task_term(db, teaching_class)
    target_batch = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.id == int(task.batch_id),
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).first()
    if not target_batch:
        raise AppException("DATA_CONFLICT", "教学任务批次不存在，无法校验教师课表冲突", http_status=409)

    other_rows = db.execute(
        select(AaTeachingClassTeacher, AaTeachingClass)
        .join(AaTeachingClass, AaTeachingClass.id == AaTeachingClassTeacher.teaching_class_id)
        .where(
            AaTeachingClassTeacher.tenant_id == _tid(),
            AaTeachingClassTeacher.teacher_key == str(teacher_key),
            AaTeachingClassTeacher.status == "ACTIVE",
            AaTeachingClassTeacher.is_deleted.is_(False),
            AaTeachingClass.tenant_id == _tid(),
            AaTeachingClass.term_id == int(teaching_class.term_id),
            AaTeachingClass.status == "ACTIVE",
            AaTeachingClass.id != int(teaching_class.id),
            AaTeachingClass.is_deleted.is_(False),
        )
    ).all()
    other_task_ids = sorted({int(row.teaching_task_id) for _relation, row in other_rows})
    tasks = []
    if other_task_ids:
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.id.in_(other_task_ids),
            AaTeachingTask.is_deleted.is_(False),
        )).all()
    task_by_id = {int(row.id): row for row in tasks}
    batch_ids = sorted({int(row.batch_id) for row in tasks if row.batch_id})
    batches = []
    if batch_ids:
        batches = db.scalars(select(AaTeachingTaskBatch).where(
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.id.in_(batch_ids),
            AaTeachingTaskBatch.term_id == int(teaching_class.term_id),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )).all()
    batch_by_id = {int(row.id): row for row in batches}

    bindings = [(task, batch_by_id[int(task.batch_id)]) for task in tasks if int(task.batch_id or 0) in batch_by_id]
    target_projection = occurrence.formal_schedule_patterns_for_tasks(db, [(task, target_batch)], term).get(int(task.id), {})
    if str(target_projection.get("status") or "").upper() != "READY":
        return
    target_patterns = _pattern_windows(target_projection.get("patterns") or [], start_week, end_week)
    if not target_patterns or not bindings:
        return
    other_projection = occurrence.formal_schedule_patterns_for_tasks(db, bindings, term)

    relations_by_task = defaultdict(list)
    for relation, other_class in other_rows:
        if exclude_relation_id and int(relation.id) == int(exclude_relation_id):
            continue
        relations_by_task[int(other_class.teaching_task_id)].append(relation)

    for other_task, _other_batch in bindings:
        projection = other_projection.get(int(other_task.id), {})
        if str(projection.get("status") or "").upper() != "READY":
            continue
        for relation in relations_by_task.get(int(other_task.id), []):
            other_start = int(relation.start_week) if relation.start_week is not None else 1
            other_end = int(relation.end_week) if relation.end_week is not None else int(term.teaching_weeks or end_week)
            other_patterns = _pattern_windows(projection.get("patterns") or [], other_start, other_end)
            for target_pattern in target_patterns:
                for other_pattern in other_patterns:
                    if _patterns_conflict(target_pattern, other_pattern):
                        raise AppException(
                            "DATA_CONFLICT",
                            "教师有效周次与其另一正式教学班课表冲突",
                            details={
                                "teacherKey": teacher_key,
                                "targetTeachingClassId": str(teaching_class.id),
                                "conflictTeachingTaskId": str(other_task.id),
                                "conflictCourseName": other_task.course_name or "",
                                "weekday": int(target_pattern.get("weekday") or 0),
                                "slotNo": int(target_pattern.get("slotNo") or 0),
                                "targetScheduleItemId": str(target_pattern.get("scheduleItemId") or ""),
                                "conflictScheduleItemId": str(other_pattern.get("scheduleItemId") or ""),
                            },
                            http_status=409,
                        )


def list_relations(user, teaching_class_id: int) -> list[dict]:
    with session() as db:
        teaching_class = class_change._get_class(db, user, int(teaching_class_id))
        return [_relation_dto(row) for row in _active_relations(db, teaching_class.id)]


def create_relation(user, teaching_class_id: int, *, teacher_key: str, role_type: str, start_week=None, end_week=None, reason="") -> dict:
    from app.models import AaTeachingClassTeacher
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    reason_text = _reason(reason)
    role = str(role_type or "CO_TEACHER").upper()
    if role not in _ROLE_TYPES:
        raise AppException("VALIDATION_ERROR", "roleType 仅支持 PRIMARY/CO_TEACHER")
    with session() as db:
        teaching_class = class_change._get_class(db, user, int(teaching_class_id), lock=True)
        guard_term_writable(db, int(teaching_class.term_id))
        task, term = _task_term(db, teaching_class)
        teacher = _teacher(db, teacher_key)
        normalized_key = str(teacher.login_name)
        start, end = _window(task, term, start_week, end_week)

        active = _active_relations(db, teaching_class.id, lock=True)
        if any(str(row.teacher_key or "") == normalized_key for row in active):
            raise AppException("DATA_CONFLICT", "该教师已存在 ACTIVE 正式授课关系", http_status=409)
        if role == "PRIMARY" and any(str(row.role_type or "").upper() == "PRIMARY" for row in active):
            raise AppException("DATA_CONFLICT", "教学班已存在 ACTIVE PRIMARY；请更新现有 PRIMARY 而不是新增第二个", http_status=409)

        # Reuse an inactive row with the same DB unique identity when possible.
        relation = db.scalars(select(AaTeachingClassTeacher).where(
            AaTeachingClassTeacher.tenant_id == _tid(),
            AaTeachingClassTeacher.teaching_class_id == int(teaching_class.id),
            AaTeachingClassTeacher.teacher_key == normalized_key,
            AaTeachingClassTeacher.role_type == role,
            AaTeachingClassTeacher.is_deleted.is_(False),
        ).order_by(AaTeachingClassTeacher.id.desc())).first()
        if relation is None:
            relation = AaTeachingClassTeacher(
                tenant_id=_tid(),
                teaching_class_id=int(teaching_class.id),
                teacher_id=int(teacher.id),
                teacher_key=normalized_key,
                teacher_name=teacher.real_name,
                role_type=role,
                start_week=start,
                end_week=end,
                status="ACTIVE",
            )
            db.add(relation)
        else:
            relation.teacher_id = int(teacher.id)
            relation.teacher_name = teacher.real_name
            relation.start_week = start
            relation.end_week = end
            relation.status = "ACTIVE"
        db.flush()
        _validate_topology(task, term, _active_relations(db, teaching_class.id, lock=True))
        _schedule_conflict_check(db, teaching_class, normalized_key, start, end)
        _sync_grade_todo(db, teaching_class)
        _audit(db, teaching_class, "TEACHER_RELATION_CREATE", f"relation={relation.id};teacher={normalized_key};role={role};weeks={start}-{end};reason={reason_text}")
        db.commit()
        db.refresh(relation)
        return _relation_dto(relation)


def update_relation(user, teaching_class_id: int, relation_id: int, *, teacher_key=None, start_week=None, end_week=None, reason="") -> dict:
    from app.models import AaTeachingClassTeacher, AaTeachingTask
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    reason_text = _reason(reason)
    with session() as db:
        teaching_class = class_change._get_class(db, user, int(teaching_class_id), lock=True)
        guard_term_writable(db, int(teaching_class.term_id))
        task, term = _task_term(db, teaching_class)
        relation = db.query(AaTeachingClassTeacher).filter(
            AaTeachingClassTeacher.id == int(relation_id),
            AaTeachingClassTeacher.tenant_id == _tid(),
            AaTeachingClassTeacher.teaching_class_id == int(teaching_class.id),
            AaTeachingClassTeacher.is_deleted.is_(False),
        ).with_for_update().first()
        if not relation:
            raise not_found("教师关系不存在")
        if str(relation.status or "").upper() != "ACTIVE":
            raise AppException("DATA_CONFLICT", "仅 ACTIVE 教师关系可修改", http_status=409)

        teacher = _teacher(db, teacher_key) if teacher_key is not None else None
        normalized_key = str(teacher.login_name) if teacher else str(relation.teacher_key)
        current_start = relation.start_week
        current_end = relation.end_week
        start, end = _window(
            task,
            term,
            current_start if start_week is None else start_week,
            current_end if end_week is None else end_week,
        )
        active = _active_relations(db, teaching_class.id, lock=True)
        if any(int(row.id) != int(relation.id) and str(row.teacher_key or "") == normalized_key for row in active):
            raise AppException("DATA_CONFLICT", "该教师已存在另一条 ACTIVE 正式授课关系", http_status=409)

        old_key = str(relation.teacher_key or "")
        relation.teacher_key = normalized_key
        relation.teacher_id = int(teacher.id) if teacher else relation.teacher_id
        relation.teacher_name = teacher.real_name if teacher else relation.teacher_name
        relation.start_week = start
        relation.end_week = end
        if str(relation.role_type or "").upper() == "PRIMARY" and normalized_key != str(task.teacher_key or ""):
            # Keep the legacy TeachingTask snapshot aligned with the formal PRIMARY.
            task.teacher_key = normalized_key
            task.teacher_id = relation.teacher_id
            task.teacher_name = relation.teacher_name
        db.flush()
        _validate_topology(task, term, _active_relations(db, teaching_class.id, lock=True))
        _schedule_conflict_check(db, teaching_class, normalized_key, start, end, exclude_relation_id=relation.id)
        _sync_grade_todo(db, teaching_class)
        _audit(db, teaching_class, "TEACHER_RELATION_UPDATE", f"relation={relation.id};teacher={old_key}->{normalized_key};role={relation.role_type};weeks={start}-{end};reason={reason_text}")
        db.commit()
        db.refresh(relation)
        return _relation_dto(relation)


def deactivate_relation(user, teaching_class_id: int, relation_id: int, *, reason="") -> dict:
    from app.models import AaTeachingClassTeacher
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    reason_text = _reason(reason)
    with session() as db:
        teaching_class = class_change._get_class(db, user, int(teaching_class_id), lock=True)
        guard_term_writable(db, int(teaching_class.term_id))
        task, term = _task_term(db, teaching_class)
        relation = db.query(AaTeachingClassTeacher).filter(
            AaTeachingClassTeacher.id == int(relation_id),
            AaTeachingClassTeacher.tenant_id == _tid(),
            AaTeachingClassTeacher.teaching_class_id == int(teaching_class.id),
            AaTeachingClassTeacher.is_deleted.is_(False),
        ).with_for_update().first()
        if not relation:
            raise not_found("教师关系不存在")
        if str(relation.status or "").upper() != "ACTIVE":
            return _relation_dto(relation)
        if str(relation.role_type or "").upper() == "PRIMARY":
            raise AppException("DATA_CONFLICT", "PRIMARY 不可直接停用；请更新 PRIMARY 教师身份或有效周次", http_status=409)
        relation.status = "INACTIVE"
        db.flush()
        _validate_topology(task, term, _active_relations(db, teaching_class.id, lock=True))
        _sync_grade_todo(db, teaching_class)
        _audit(db, teaching_class, "TEACHER_RELATION_DEACTIVATE", f"relation={relation.id};teacher={relation.teacher_key};role={relation.role_type};reason={reason_text}")
        db.commit()
        db.refresh(relation)
        return _relation_dto(relation)
