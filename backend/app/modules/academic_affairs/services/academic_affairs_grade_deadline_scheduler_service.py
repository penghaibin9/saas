"""C-W4 scheduled GradeTask deadline reminders and overdue escalation.

Production scheduling remains owned by ``scripts.run_scheduled_jobs``.  This module
owns only the tenant-scoped business scan:

- 7 / 3 / 1 day milestones remind current formal grade-entry assignees;
- overdue tasks are grouped into scoped digests for college/school academic admins;
- shared MessageEventOutbox provides delivery, retry and deduplication;
- current GradeTask rows are selected with ``FOR UPDATE SKIP LOCKED`` so the scan
  never races a concurrent deadline extension and never waits behind an operator;
- college recipients are resolved through the same ``build_affairs_context``
  fail-closed scope model used by academic-affairs services.

No scheduler state table is added: the outbox dedup key is the durable execution
proof.  Extending a deadline changes the deadline identity and therefore creates a
new legitimate reminder series while old milestone keys remain historical facts.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select, text

from app.core.affairs_security import build_affairs_context
from app.services.message_event_outbox_service import emit_message_event

from . import academic_affairs_grade_core_service as grade_core
from . import academic_affairs_grade_message_event_guard as message_event_guard
from . import academic_affairs_grade_todo_teacher_relation_guard as todo_guard

_REMINDABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}
_ADMIN_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}
_MILESTONES = (1, 3, 7)
_MAX_SCAN = 500
_MAX_DIGEST_ITEMS = 50

message_event_guard.install()


def _deadline_key(value: datetime) -> str:
    return value.replace(microsecond=0).strftime("%Y%m%dT%H%M%S")


def _milestone_days(deadline: datetime, now: datetime) -> int | None:
    remaining = (deadline - now).total_seconds()
    if remaining <= 0:
        return None
    for days in _MILESTONES:
        if remaining <= days * 24 * 60 * 60:
            return days
    return None


def _outbox_exists(db, dedup_key: str) -> bool:
    from app.models import MessageEventOutbox

    return db.scalar(select(MessageEventOutbox.id).where(
        MessageEventOutbox.tenant_id == grade_core._tid(),
        MessageEventOutbox.dedup_key == str(dedup_key)[:120],
        MessageEventOutbox.is_deleted.is_(False),
    )) is not None


def _pending_teacher_ids(db, task) -> list[int]:
    from app.models import UnifiedTodo

    todo_guard.sync_grade_entry_todos(db, task)
    db.flush()
    return sorted({
        int(value) for value in db.scalars(select(UnifiedTodo.assignee_id).where(
            UnifiedTodo.tenant_id == grade_core._tid(),
            UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_type == "AA_GRADE_TASK",
            UnifiedTodo.source_biz_id == int(task.id),
            UnifiedTodo.todo_type == grade_core.TODO_GRADE_ENTRY,
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.assignee_id.isnot(None),
            UnifiedTodo.is_deleted.is_(False),
        )).all()
        if int(value or 0) > 0
    })


def _task_college_map(db, tasks) -> dict[int, int | None]:
    """Resolve one bounded task batch to a college without per-row queries."""
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, Major, SchoolClass

    task_list = list(tasks or [])
    teaching_task_ids = sorted({int(row.teaching_task_id) for row in task_list if row.teaching_task_id})
    teaching_tasks = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == grade_core._tid(),
        AaTeachingTask.id.in_(teaching_task_ids or [-1]),
        AaTeachingTask.is_deleted.is_(False),
    )).all()
    teaching_by_id = {int(row.id): row for row in teaching_tasks}

    batch_ids = sorted({int(row.batch_id) for row in teaching_tasks if row.batch_id})
    batches = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == grade_core._tid(),
        AaTeachingTaskBatch.id.in_(batch_ids or [-1]),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all()
    batch_by_id = {int(row.id): row for row in batches}

    class_ids = sorted({int(row.class_id) for row in task_list if row.class_id})
    classes = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == grade_core._tid(),
        SchoolClass.id.in_(class_ids or [-1]),
        SchoolClass.is_deleted.is_(False),
    )).all()
    class_by_id = {int(row.id): row for row in classes}
    major_ids = sorted({int(row.major_id) for row in classes if row.major_id})
    majors = db.scalars(select(Major).where(
        Major.tenant_id == grade_core._tid(),
        Major.id.in_(major_ids or [-1]),
        Major.is_deleted.is_(False),
    )).all()
    major_by_id = {int(row.id): row for row in majors}

    course_ids = sorted({int(row.course_id) for row in task_list if row.course_id})
    courses = db.scalars(select(AaCourse).where(
        AaCourse.tenant_id == grade_core._tid(),
        AaCourse.id.in_(course_ids or [-1]),
        AaCourse.is_deleted.is_(False),
    )).all()
    course_by_id = {int(row.id): row for row in courses}

    result: dict[int, int | None] = {}
    for task in task_list:
        college_id = None
        teaching = teaching_by_id.get(int(task.teaching_task_id)) if task.teaching_task_id else None
        batch = batch_by_id.get(int(teaching.batch_id)) if teaching and teaching.batch_id else None
        if batch and batch.college_id:
            college_id = int(batch.college_id)
        if college_id is None and task.class_id:
            school_class = class_by_id.get(int(task.class_id))
            major = major_by_id.get(int(school_class.major_id)) if school_class and school_class.major_id else None
            if major and major.college_id:
                college_id = int(major.college_id)
        if college_id is None and task.course_id:
            course = course_by_id.get(int(task.course_id))
            if course and course.owner_college_id:
                college_id = int(course.owner_college_id)
        result[int(task.id)] = college_id
    return result


def _admin_visibility(db, tasks, task_colleges: dict[int, int | None]) -> dict[int, set[int]]:
    """Return recipient user -> visible overdue task ids, fail-closed for college scope."""
    from app.models import Role, User, UserRole

    assignments = db.execute(
        select(User, Role)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.tenant_id == grade_core._tid(),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
            UserRole.tenant_id == grade_core._tid(),
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            Role.tenant_id == grade_core._tid(),
            Role.role_code.in_(sorted(_ADMIN_ROLES)),
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )
        .order_by(User.id, Role.id)
    ).all()

    all_task_ids = {int(task.id) for task in tasks}
    visible: dict[int, set[int]] = defaultdict(set)
    for user_row, role_row in assignments:
        role_code = str(role_row.role_code or "").upper()
        user_ctx = {
            "userId": f"u_{int(user_row.id)}",
            "loginName": user_row.login_name or "",
            "userType": user_row.user_type or "",
            "currentRoleCode": role_code,
        }
        scope = build_affairs_context(user_ctx, db)
        if scope.scope_type == "TENANT_ALL":
            visible[int(user_row.id)].update(all_task_ids)
            continue
        if role_code != "COLLEGE_ADMIN" or scope.scope_type != "COLLEGE" or not scope.college_ids:
            continue
        allowed = {int(value) for value in scope.college_ids}
        visible[int(user_row.id)].update({
            task_id for task_id in all_task_ids
            if task_colleges.get(task_id) is not None and int(task_colleges[task_id]) in allowed
        })
    return visible


def _emit_teacher_milestone(db, task, deadline: datetime, milestone_days: int) -> bool:
    assignee_ids = _pending_teacher_ids(db, task)
    if not assignee_ids:
        return False
    key = f"GRADE.ENTRY_DEADLINE_REMINDER:{task.id}:{_deadline_key(deadline)}:D{milestone_days}"
    if _outbox_exists(db, key):
        return False
    emit_message_event(
        db,
        event_code="GRADE.ENTRY_DEADLINE_REMINDER",
        source_module="academic-affairs",
        source_biz_type="AA_GRADE_TASK",
        source_biz_id=int(task.id),
        recipient_refs=[{"userId": value} for value in assignee_ids],
        variables={
            "gradeTaskId": str(task.id),
            "courseName": task.course_name or "",
            "deadline": deadline.isoformat(),
            "milestoneDays": milestone_days,
        },
        content=(
            f"《{task.course_name or '课程'}》成绩提交距截止时间不足 {milestone_days} 天。"
            f"截止时间：{deadline.isoformat()}。请尽快完成录入并提交学院审核。"
        ),
        title=f"成绩录入截止提醒：{task.course_name or '课程'}",
        dedup_key=key,
    )
    grade_core._audit(
        db,
        "AA_GRADE_TASK",
        int(task.id),
        "GRADE_ENTRY_DEADLINE_REMINDER_AUTO",
        f"milestoneDays={milestone_days};deadline={deadline.isoformat()};assignees={','.join(str(v) for v in assignee_ids)}",
    )
    return True


def _emit_overdue_digests(db, overdue_tasks, deadlines: dict[int, datetime], task_colleges) -> int:
    task_by_id = {int(task.id): task for task in overdue_tasks}
    visibility = _admin_visibility(db, overdue_tasks, task_colleges)
    emitted = 0
    for user_id, task_ids in visibility.items():
        selected = [task_by_id[value] for value in sorted(task_ids) if value in task_by_id]
        if not selected:
            continue
        fingerprint_src = "|".join(
            f"{task.id}:{_deadline_key(deadlines[int(task.id)])}" for task in selected
        )
        digest_hash = hashlib.sha256(fingerprint_src.encode("utf-8")).hexdigest()[:20]
        key = f"GRADE.ENTRY_OVERDUE_DIGEST:{int(user_id)}:{digest_hash}"
        if _outbox_exists(db, key):
            continue
        preview = selected[:10]
        preview_text = "；".join(
            f"{task.course_name or '课程'}(任务#{task.id})" for task in preview
        )
        if len(selected) > len(preview):
            preview_text += f"；另有{len(selected) - len(preview)}项"
        payload_items = [
            {
                "gradeTaskId": str(task.id),
                "courseName": task.course_name or "",
                "deadline": deadlines[int(task.id)].isoformat(),
                "collegeId": str(task_colleges.get(int(task.id)) or ""),
            }
            for task in selected[:_MAX_DIGEST_ITEMS]
        ]
        emit_message_event(
            db,
            event_code="GRADE.ENTRY_OVERDUE_DIGEST",
            source_module="academic-affairs",
            source_biz_type="AA_GRADE_OVERDUE_DIGEST",
            source_biz_id=int(selected[0].id),
            recipient_refs=[{"userId": int(user_id)}],
            variables={
                "overdueCount": len(selected),
                "items": payload_items,
                "truncated": len(selected) > _MAX_DIGEST_ITEMS,
            },
            content=f"当前有 {len(selected)} 个成绩任务已逾期未提交：{preview_text}。请进入成绩任务工作台处理。",
            title=f"成绩录入逾期清单（{len(selected)}项）",
            dedup_key=key,
        )
        emitted += 1
    return emitted


def scan_grade_deadlines(*, limit: int = _MAX_SCAN) -> dict:
    """Run one tenant-scoped scheduled scan. Caller owns tenant iteration/policy."""
    from app.models import AaGradeTask

    bounded = min(_MAX_SCAN, max(1, int(limit or _MAX_SCAN)))
    now = datetime.utcnow().replace(microsecond=0)
    with grade_core.session() as db:
        rows = db.execute(text(
            "SELECT id, deadline_at, status FROM t_aa_grade_task "
            "WHERE tenant_id=:tenant_id AND is_deleted=0 "
            "AND status IN ('NOT_STARTED','INPUTTING','RETURNED') "
            "AND deadline_at IS NOT NULL "
            "AND deadline_at <= DATE_ADD(UTC_TIMESTAMP(), INTERVAL 7 DAY) "
            "ORDER BY deadline_at ASC, id ASC LIMIT :limit FOR UPDATE SKIP LOCKED"
        ), {"tenant_id": int(grade_core._tid()), "limit": bounded}).mappings().all()
        if not rows:
            db.rollback()
            return {"scanned": 0, "teacherReminders": 0, "overdueDigests": 0}

        row_by_id = {int(row["id"]): row for row in rows}
        task_ids = sorted(row_by_id)
        tasks = db.scalars(select(AaGradeTask).where(
            AaGradeTask.tenant_id == grade_core._tid(),
            AaGradeTask.id.in_(task_ids),
            AaGradeTask.is_deleted.is_(False),
        ).order_by(AaGradeTask.id)).all()
        tasks = [task for task in tasks if str(task.status or "").upper() in _REMINDABLE]
        task_colleges = _task_college_map(db, tasks)

        teacher_emitted = 0
        overdue_tasks = []
        deadlines: dict[int, datetime] = {}
        for task in tasks:
            raw = row_by_id.get(int(task.id))
            deadline = raw.get("deadline_at") if raw else None
            if not isinstance(deadline, datetime):
                continue
            deadlines[int(task.id)] = deadline
            if deadline <= now:
                overdue_tasks.append(task)
                continue
            milestone = _milestone_days(deadline, now)
            if milestone is not None and _emit_teacher_milestone(db, task, deadline, milestone):
                teacher_emitted += 1

        overdue_digest_count = _emit_overdue_digests(
            db, overdue_tasks, deadlines, task_colleges
        ) if overdue_tasks else 0
        db.commit()
        return {
            "scanned": len(tasks),
            "teacherReminders": teacher_emitted,
            "overdueTasks": len(overdue_tasks),
            "overdueDigests": overdue_digest_count,
        }
