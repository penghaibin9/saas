"""C-W4 scheduled GradeTask deadline reminders and overdue escalation.

Production scheduling remains owned by ``scripts.run_scheduled_jobs``. This module
owns only the tenant-scoped business scan:

- 7 / 3 / 1 day milestones remind current formal grade-entry assignees;
- upcoming tasks are locked with ``FOR UPDATE SKIP LOCKED`` so a concurrent deadline
  extension cannot race a teacher reminder;
- the upcoming SQL excludes tasks whose current milestone dedup already exists, so a
  large already-reminded prefix cannot consume the bounded queue forever;
- overdue escalation is not a fixed-row queue: every admin receives a scope-filtered
  full SQL count plus a bounded oldest-50 sample;
- unchanged overdue scope is deduplicated within the UTC day, while a same-day scope
  change produces a fresh digest on the next hourly scheduler pass; an unchanged
  backlog is reminded again on the next UTC day;
- shared MessageEventOutbox provides delivery, retry and durable deduplication;
- college recipients are resolved through the same ``build_affairs_context``
  fail-closed scope model used by academic-affairs services.

No scheduler state table is added. Extending a deadline changes the milestone dedup
identity. Overdue digest identity is recipient + UTC day + a compact SQL aggregate
fingerprint of the recipient's current overdue set, preventing hourly duplicates
without delaying newly overdue work until the next day.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import bindparam, select, text

from app.core.affairs_security import build_affairs_context
from app.services.message_event_outbox_service import emit_message_event

from . import academic_affairs_grade_core_service as grade_core
from . import academic_affairs_grade_message_event_guard as message_event_guard
from . import academic_affairs_grade_todo_teacher_relation_guard as todo_guard

_REMINDABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}
_ADMIN_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}
_MILESTONES = (1, 3, 7)
_MAX_SCAN = 2000
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


def _admin_scopes(db) -> dict[int, set[int] | None]:
    """Map recipient user id to college ids; ``None`` means tenant-wide authority."""
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

    result: dict[int, set[int] | None] = {}
    for user_row, role_row in assignments:
        uid = int(user_row.id)
        if uid in result and result[uid] is None:
            continue
        role_code = str(role_row.role_code or "").upper()
        scope = build_affairs_context({
            "userId": f"u_{uid}",
            "loginName": user_row.login_name or "",
            "userType": user_row.user_type or "",
            "currentRoleCode": role_code,
        }, db)
        if scope.scope_type == "TENANT_ALL":
            result[uid] = None
            continue
        if role_code != "COLLEGE_ADMIN" or scope.scope_type != "COLLEGE" or not scope.college_ids:
            continue
        current = result.setdefault(uid, set())
        if current is not None:
            current.update(int(value) for value in scope.college_ids)
    return result


_OVERDUE_FROM = """
FROM t_aa_grade_task gt
LEFT JOIN t_aa_teaching_task tt
  ON tt.id=gt.teaching_task_id AND tt.tenant_id=gt.tenant_id AND tt.is_deleted=0
LEFT JOIN t_aa_teaching_task_batch ttb
  ON ttb.id=tt.batch_id AND ttb.tenant_id=gt.tenant_id AND ttb.is_deleted=0
LEFT JOIN t_class cls
  ON cls.id=gt.class_id AND cls.tenant_id=gt.tenant_id AND cls.is_deleted=0
LEFT JOIN t_major maj
  ON maj.id=cls.major_id AND maj.tenant_id=gt.tenant_id AND maj.is_deleted=0
LEFT JOIN t_aa_course course
  ON course.id=gt.course_id AND course.tenant_id=gt.tenant_id AND course.is_deleted=0
WHERE gt.tenant_id=:tenant_id AND gt.is_deleted=0
  AND gt.status IN ('NOT_STARTED','INPUTTING','RETURNED')
  AND gt.deadline_at IS NOT NULL AND gt.deadline_at <= UTC_TIMESTAMP()
"""
_COLLEGE_EXPR = "COALESCE(ttb.college_id, maj.college_id, course.owner_college_id)"


def _overdue_total(db) -> int:
    return int(db.scalar(text("SELECT COUNT(*) " + _OVERDUE_FROM), {
        "tenant_id": int(grade_core._tid()),
    }) or 0)


def _overdue_digest_rows(db, college_ids: set[int] | None) -> tuple[list[dict], int, str]:
    params: dict = {
        "tenant_id": int(grade_core._tid()),
        "sample_limit": _MAX_DIGEST_ITEMS,
    }
    stmt = text(
        "SELECT gt.id, gt.course_name, gt.deadline_at, "
        + _COLLEGE_EXPR + " AS college_id, "
        "COUNT(*) OVER() AS total_count, "
        "COALESCE(SUM(gt.id) OVER(), 0) AS id_sum, "
        "COALESCE(MAX(gt.id) OVER(), 0) AS max_id, "
        "MAX(gt.deadline_at) OVER() AS latest_deadline "
        + _OVERDUE_FROM
        + (f" AND {_COLLEGE_EXPR} IN :college_ids" if college_ids is not None else "")
        + " ORDER BY gt.deadline_at ASC, gt.id ASC LIMIT :sample_limit"
    )
    if college_ids is not None:
        if not college_ids:
            return [], 0, ""
        stmt = stmt.bindparams(bindparam("college_ids", expanding=True))
        params["college_ids"] = sorted(int(value) for value in college_ids)
    rows = [dict(row) for row in db.execute(stmt, params).mappings().all()]
    if not rows:
        return [], 0, ""
    head = rows[0]
    total = int(head.get("total_count") or 0)
    fingerprint_source = "|".join([
        str(total),
        str(head.get("id_sum") or 0),
        str(head.get("max_id") or 0),
        str(head.get("latest_deadline") or ""),
    ])
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:16]
    return rows, total, fingerprint


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


def _emit_overdue_digests(db, now: datetime) -> int:
    emitted = 0
    day_key = now.strftime("%Y%m%d")
    for user_id, college_ids in _admin_scopes(db).items():
        rows, total, digest_fingerprint = _overdue_digest_rows(db, college_ids)
        if total <= 0 or not rows or not digest_fingerprint:
            continue
        key = f"GRADE.ENTRY_OVERDUE_DIGEST:{int(user_id)}:{day_key}:{digest_fingerprint}"
        if _outbox_exists(db, key):
            continue
        preview_text = "；".join(
            f"{row.get('course_name') or '课程'}(任务#{row['id']})" for row in rows[:10]
        )
        if total > 10:
            preview_text += f"；另有{total - 10}项"
        items = [{
            "gradeTaskId": str(row["id"]),
            "courseName": row.get("course_name") or "",
            "deadline": row["deadline_at"].isoformat() if row.get("deadline_at") else None,
            "collegeId": str(row.get("college_id") or ""),
        } for row in rows]
        emit_message_event(
            db,
            event_code="GRADE.ENTRY_OVERDUE_DIGEST",
            source_module="academic-affairs",
            source_biz_type="AA_GRADE_OVERDUE_DIGEST",
            source_biz_id=int(rows[0]["id"]),
            recipient_refs=[{"userId": int(user_id)}],
            variables={
                "overdueCount": total,
                "items": items,
                "truncated": total > len(items),
                "generatedAt": now.isoformat(),
                "digestFingerprint": digest_fingerprint,
            },
            content=f"当前有 {total} 个成绩任务已逾期未提交：{preview_text}。请进入成绩任务工作台处理。",
            title=f"成绩录入逾期清单（{total}项）",
            dedup_key=key,
        )
        emitted += 1
    return emitted


def _locked_upcoming_rows(db, limit: int):
    """Lock only work still missing the *current* milestone event.

    The SQL milestone CASE mirrors ``_milestone_days``. When a task later crosses
    D7→D3→D1 the dedup expression changes, so it becomes eligible again; meanwhile
    already-emitted rows no longer consume the bounded queue.
    """
    return db.execute(text(
        "SELECT gt.id, gt.deadline_at, gt.status FROM t_aa_grade_task gt "
        "WHERE gt.tenant_id=:tenant_id AND gt.is_deleted=0 "
        "AND gt.status IN ('NOT_STARTED','INPUTTING','RETURNED') "
        "AND gt.deadline_at IS NOT NULL AND gt.deadline_at > UTC_TIMESTAMP() "
        "AND gt.deadline_at <= DATE_ADD(UTC_TIMESTAMP(), INTERVAL 7 DAY) "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM t_message_event_outbox meo "
        "  WHERE meo.tenant_id=gt.tenant_id AND meo.is_deleted=0 "
        "    AND meo.dedup_key=CONCAT("
        "      'GRADE.ENTRY_DEADLINE_REMINDER:', gt.id, ':', "
        "      DATE_FORMAT(gt.deadline_at, '%Y%m%dT%H%i%s'), ':', 'D', "
        "      CASE "
        "        WHEN TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), gt.deadline_at) <= 86400 THEN 1 "
        "        WHEN TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), gt.deadline_at) <= 259200 THEN 3 "
        "        ELSE 7 END"
        "    )"
        ") "
        "ORDER BY gt.deadline_at ASC, gt.id ASC LIMIT :limit FOR UPDATE SKIP LOCKED"
    ), {"tenant_id": int(grade_core._tid()), "limit": int(limit)}).mappings().all()


def scan_grade_deadlines(*, limit: int = _MAX_SCAN) -> dict:
    """Run one tenant-scoped scheduled scan. Caller owns tenant iteration/policy."""
    from app.models import AaGradeTask

    bounded = min(_MAX_SCAN, max(1, int(limit or _MAX_SCAN)))
    now = datetime.utcnow().replace(microsecond=0)
    with grade_core.session() as db:
        rows = _locked_upcoming_rows(db, bounded)
        task_ids = [int(row["id"]) for row in rows]
        tasks = []
        if task_ids:
            tasks = db.scalars(select(AaGradeTask).where(
                AaGradeTask.tenant_id == grade_core._tid(),
                AaGradeTask.id.in_(task_ids),
                AaGradeTask.is_deleted.is_(False),
            ).order_by(AaGradeTask.id)).all()
            tasks = [task for task in tasks if str(task.status or "").upper() in _REMINDABLE]
        row_by_id = {int(row["id"]): row for row in rows}
        teacher_emitted = 0
        for task in tasks:
            raw = row_by_id.get(int(task.id))
            deadline = raw.get("deadline_at") if raw else None
            if not isinstance(deadline, datetime):
                continue
            milestone = _milestone_days(deadline, now)
            if milestone is not None and _emit_teacher_milestone(db, task, deadline, milestone):
                teacher_emitted += 1

        overdue_total = _overdue_total(db)
        overdue_digest_count = _emit_overdue_digests(db, now) if overdue_total else 0
        db.commit()
        return {
            "scanned": len(tasks),
            "upcomingScanned": len(rows),
            "teacherReminders": teacher_emitted,
            "overdueTasks": overdue_total,
            "overdueDigests": overdue_digest_count,
        }
