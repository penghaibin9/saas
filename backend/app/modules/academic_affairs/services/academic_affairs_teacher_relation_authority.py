"""C-C1/C-W5 formal teaching-teacher authority.

For projected teaching classes, ``AaTeachingClassTeacher`` is the formal authority
for teacher-facing execution. ``AaTeachingTask.teacher_key`` is only a migration
fallback when no teaching-class projection exists yet. Workload, attendance history,
grade-task snapshots and names must never be used to infer permission.

Week semantics are explicit:
- grade/end-of-term execution uses ``authority_week``: before term -> week 1,
  during term -> current local teaching week, after teaching period -> final week;
- occurrence execution (attendance) may pass the occurrence's teaching week so a
  1-8 -> 9-16 handoff is judged against the actual class date, not today's date;
- unbounded relations cover the whole term;
- bounded relations require a resolvable term week, otherwise fail closed.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.exceptions import AppException
from app.services.db_service import _tid


def user_keys(user) -> set[str]:
    return {str(value).strip() for value in (_derive_keys(user or {}) or set()) if str(value).strip()}


def _term(db, term_id: int):
    from app.models import AaTerm

    return db.scalars(select(AaTerm).where(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    )).first()


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def teaching_week_for_date(db, term_id: int, on_date) -> int | None:
    """Resolve a concrete occurrence date to its 1-based teaching week.

    Dates outside the configured teaching period are not silently clamped: an
    attendance occurrence outside the term must be rejected by its own calendar /
    occurrence contract rather than borrowing the first/last teacher relation.
    """
    term = _term(db, term_id)
    target = _as_date(on_date)
    start = _as_date(getattr(term, "start_date", None)) if term else None
    if not term or not start or not target or target < start:
        return None
    week = ((target - start).days // 7) + 1
    teaching_weeks = int(getattr(term, "teaching_weeks", 0) or 0)
    if teaching_weeks > 0 and week > teaching_weeks:
        return None
    return max(1, int(week))


def authority_week(db, term_id: int) -> int | None:
    """Current/end-of-term authority week for non-occurrence workflows (e.g. grades)."""
    from .student_exam_read_service import _tenant_timezone

    term = _term(db, term_id)
    start = _as_date(getattr(term, "start_date", None)) if term else None
    if not term or not start:
        return None
    zone, _zone_name = _tenant_timezone(db)
    current = datetime.now(zone).astimezone(zone).date()
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
            "正式教学班已归档/失效，禁止继续教师执行",
            details={"teachingClassId": str(row.id), "status": row.status},
            http_status=409,
        )
    return row


def active_relations(db, teaching_class, *, lock: bool = False, week: int | None = None):
    """Return ACTIVE formal teacher relations covering ``week``.

    When week is omitted, use current/end-of-term authority semantics. Callers tied
    to a concrete occurrence should pass that occurrence's resolved teaching week.
    """
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
    resolved_week = authority_week(db, int(teaching_class.term_id)) if week is None else int(week)
    bounded = [row for row in rows if row.start_week is not None or row.end_week is not None]
    if bounded and resolved_week is None:
        raise AppException(
            "DATA_CONFLICT",
            "正式教师关系包含有效周次，但无法解析教学周，不能安全裁决教师权限",
            details={"teachingClassId": str(teaching_class.id)},
            http_status=409,
        )
    return [row for row in rows if relation_covers_week(row, resolved_week)], resolved_week


def require_teacher(db, teaching_task, user, *, lock: bool = False, week: int | None = None) -> dict:
    """Require formal TeachingClassTeacher; fallback to task only before projection exists."""
    from app.models import AaTeachingTask

    keys = user_keys(user)
    if not keys:
        raise AppException("NO_DATA_SCOPE", "当前教师账号缺少稳定工号，无法确认授课权限", http_status=403)

    teaching_class = class_authority(db, int(teaching_task.id), lock=lock)
    if teaching_class is not None:
        relations, resolved_week = active_relations(db, teaching_class, lock=lock, week=week)
        if not relations:
            raise AppException(
                "DATA_CONFLICT",
                "该教学周没有正式任课教师关系，禁止按历史快照继续执行",
                details={"teachingClassId": str(teaching_class.id), "authorityWeek": resolved_week},
                http_status=409,
            )
        matched = [row for row in relations if str(row.teacher_key or "").strip() in keys]
        if not matched:
            raise AppException(
                "NO_DATA_SCOPE",
                "当前账号不在该教学周正式教师关系中",
                details={
                    "teachingClassId": str(teaching_class.id),
                    "authorityWeek": resolved_week,
                    "activeTeacherKeys": [str(row.teacher_key) for row in relations],
                },
                http_status=403,
            )
        return {
            "source": "TEACHING_CLASS_TEACHER",
            "teachingClassId": int(teaching_class.id),
            "authorityWeek": resolved_week,
            "teacherKeys": [str(row.teacher_key) for row in relations],
            "matchedTeacherKeys": [str(row.teacher_key) for row in matched],
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
        raise AppException("DATA_CONFLICT", "教学任务已失效", http_status=409)
    key = str(current.teacher_key or "").strip()
    if not key:
        raise AppException("NO_DATA_SCOPE", "当前教学任务未绑定任课教师，请联系教务处处理", http_status=403)
    if key not in keys:
        raise AppException("NO_DATA_SCOPE", "任课教师已发生变更，当前账号不再具有该任务权限", http_status=403)
    return {
        "source": "TEACHING_TASK_MIGRATION_FALLBACK",
        "teachingClassId": None,
        "authorityWeek": week,
        "teacherKeys": [key],
        "matchedTeacherKeys": [key],
        "matchedRelationIds": [],
    }
