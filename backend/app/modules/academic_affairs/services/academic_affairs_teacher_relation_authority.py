"""C-C1/C-W5 current teaching-teacher authority.

For projected teaching classes, ``AaTeachingClassTeacher`` is the formal authority
for teacher-facing execution. ``AaTeachingTask.teacher_key`` is only a migration
fallback when no teaching-class projection exists yet. Workload, attendance history,
grade-task snapshots and names must never be used to infer permission.

Effective-week policy:
- before term start use week 1;
- during term use the current local teaching week;
- after the configured teaching weeks use the final teaching week;
- unbounded teacher relations (start/end NULL) cover the whole term;
- bounded relations require a resolvable term week, otherwise fail closed.
This makes a 1-8 -> 9-16 teacher handoff revoke the former teacher after week 8
while still allowing the final teacher to complete end-of-term grade execution.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.exceptions import AppException
from app.services.db_service import _tid


def user_keys(user) -> set[str]:
    return {str(value).strip() for value in (_derive_keys(user or {}) or set()) if str(value).strip()}


def authority_week(db, term_id: int) -> int | None:
    from app.models import AaTerm
    from .student_exam_read_service import _tenant_timezone

    term = db.scalars(select(AaTerm).where(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    )).first()
    if not term or not term.start_date:
        return None
    zone, _zone_name = _tenant_timezone(db)
    now = datetime.now(zone)
    start = term.start_date.date() if isinstance(term.start_date, datetime) else term.start_date
    current = now.astimezone(zone).date()
    if current < start:
        week = 1
    else:
        week = ((current - start).days // 7) + 1
    teaching_weeks = int(getattr(term, "teaching_weeks", 0) or 0)
    if teaching_weeks > 0:
        week = min(max(1, week), teaching_weeks)
    return max(1, int(week))


def relation_covers_week(relation, week: int | None) -> bool:
    start = int(relation.start_week) if relation.start_week is not None else None
    end = int(relation.end_week) if relation.end_week is not None else None
    if start is None and end is None:
        return True
    if week is None:
        return False
    if start is not None and week < start:
        return False
    if end is not None and week > end:
        return False
    return True


def class_authority(db, teaching_task_id: int, *, lock: bool = False):
    """Return active formal teaching class or None for not-yet-projected legacy data."""
    from app.models import AaTeachingClass

    query = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(),
        AaTeachingClass.teaching_task_id == int(teaching_task_id),
        AaTeachingClass.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        return None
    if str(row.status or "").upper() != "ACTIVE":
        raise AppException(
            "DATA_CONFLICT",
            "成绩任务关联的正式教学班已归档/失效，禁止继续教师写入",
            details={"teachingClassId": str(row.id), "status": row.status},
            http_status=409,
        )
    return row


def active_relations(db, teaching_class, *, lock: bool = False):
    from app.models import AaTeachingClassTeacher

    query = db.query(AaTeachingClassTeacher).filter(
        AaTeachingClassTeacher.tenant_id == _tid(),
        AaTeachingClassTeacher.teaching_class_id == int(teaching_class.id),
        AaTeachingClassTeacher.status == "ACTIVE",
        AaTeachingClassTeacher.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    rows = query.order_by(AaTeachingClassTeacher.role_type, AaTeachingClassTeacher.id).all()
    week = authority_week(db, int(teaching_class.term_id))
    bounded = [row for row in rows if row.start_week is not None or row.end_week is not None]
    if bounded and week is None:
        raise AppException(
            "DATA_CONFLICT",
            "正式教师关系包含有效周次，但学期起始日缺失，无法安全裁决当前教师权限",
            details={"teachingClassId": str(teaching_class.id)},
            http_status=409,
        )
    return [row for row in rows if relation_covers_week(row, week)], week


def require_teacher(db, teaching_task, user, *, lock: bool = False) -> dict:
    """Require formal TeachingClassTeacher; fallback to task only before projection exists."""
    from app.models import AaTeachingTask

    keys = user_keys(user)
    if not keys:
        raise AppException("NO_DATA_SCOPE", "当前教师账号缺少稳定工号，无法确认授课权限", http_status=403)

    teaching_class = class_authority(db, int(teaching_task.id), lock=lock)
    if teaching_class is not None:
        relations, week = active_relations(db, teaching_class, lock=lock)
        if not relations:
            raise AppException(
                "DATA_CONFLICT",
                "当前有效周次没有正式任课教师关系，禁止按历史快照继续执行",
                details={"teachingClassId": str(teaching_class.id), "authorityWeek": week},
                http_status=409,
            )
        matched = [row for row in relations if str(row.teacher_key or "").strip() in keys]
        if not matched:
            raise AppException(
                "NO_DATA_SCOPE",
                "当前账号不在教学班本周正式教师关系中",
                details={
                    "teachingClassId": str(teaching_class.id),
                    "authorityWeek": week,
                    "activeTeacherKeys": [str(row.teacher_key) for row in relations],
                },
                http_status=403,
            )
        return {
            "source": "TEACHING_CLASS_TEACHER",
            "teachingClassId": int(teaching_class.id),
            "authorityWeek": week,
            "teacherKeys": [str(row.teacher_key) for row in relations],
            "matchedRelationIds": [int(row.id) for row in matched],
        }

    # Migration fallback is permitted only when no formal teaching-class projection exists.
    query = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == int(teaching_task.id),
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    current = query.first()
    if not current:
        raise AppException("DATA_CONFLICT", "成绩任务关联的教学任务已失效", http_status=409)
    key = str(current.teacher_key or "").strip()
    if not key:
        raise AppException("NO_DATA_SCOPE", "当前教学任务未绑定任课教师，请联系教务处处理", http_status=403)
    if key not in keys:
        raise AppException("NO_DATA_SCOPE", "任课教师已发生变更，当前账号不再具有该任务权限", http_status=403)
    return {
        "source": "TEACHING_TASK_MIGRATION_FALLBACK",
        "teachingClassId": None,
        "authorityWeek": None,
        "teacherKeys": [key],
        "matchedRelationIds": [],
    }
