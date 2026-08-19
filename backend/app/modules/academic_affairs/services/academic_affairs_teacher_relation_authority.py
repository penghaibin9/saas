"""C-C1/C-W5 formal teaching-teacher authority.

For projected teaching classes, ``AaTeachingClassTeacher`` is the formal authority
for teacher-facing execution. ``AaTeachingTask.teacher_key`` is only a migration
fallback when no teaching-class projection exists yet. Workload, attendance history,
grade-task snapshots and names must never be used to infer permission.

Week semantics are explicit:
- occurrence execution (attendance) passes the occurrence's real teaching week;
- non-occurrence execution (grades/Todos) starts from the current/final term week,
  then clamps it into the linked TeachingTask ``start_week/end_week`` window. A
  weeks-1-8 course may therefore finish grading in week 10 without reviving a later
  teacher relation from some unrelated week;
- unbounded relations cover the whole applicable task window;
- bounded relations require a resolvable authority week, otherwise fail closed.
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


def _authority_week_from_term(term, current: date) -> int | None:
    start = _as_date(getattr(term, "start_date", None)) if term else None
    if not term or not start:
        return None
    if current < start:
        week = 1
    else:
        week = ((current - start).days // 7) + 1
    teaching_weeks = int(getattr(term, "teaching_weeks", 0) or 0)
    if teaching_weeks > 0:
        week = min(max(1, week), teaching_weeks)
    return max(1, int(week))


def authority_week(db, term_id: int) -> int | None:
    """Current/final term week before any task-window clamping."""
    from .student_exam_read_service import _tenant_timezone

    term = _term(db, term_id)
    zone, _zone_name = _tenant_timezone(db)
    current = datetime.now(zone).astimezone(zone).date()
    return _authority_week_from_term(term, current)


def _clamp_task_authority_week(teaching_class, task, term, base_week: int | None) -> int | None:
    if base_week is None:
        return None
    if not task:
        raise AppException(
            "DATA_CONFLICT",
            "正式教学班无法回链教学任务，不能安全裁决教师权限",
            details={"teachingClassId": str(teaching_class.id)},
            http_status=409,
        )
    term_weeks = int(getattr(term, "teaching_weeks", 0) or 0) if term else 0
    start_week = int(task.start_week) if task.start_week is not None else 1
    end_week = int(task.end_week) if task.end_week is not None else (term_weeks or base_week)
    if start_week <= 0 or end_week <= 0 or end_week < start_week:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务存在非法有效周次，不能安全裁决教师权限",
            details={
                "teachingTaskId": str(task.id),
                "startWeek": task.start_week,
                "endWeek": task.end_week,
            },
            http_status=409,
        )
    if term_weeks > 0 and (start_week > term_weeks or end_week > term_weeks):
        raise AppException(
            "DATA_CONFLICT",
            "教学任务有效周次超出学期教学周，不能安全裁决教师权限",
            details={
                "teachingTaskId": str(task.id),
                "startWeek": start_week,
                "endWeek": end_week,
                "teachingWeeks": term_weeks,
            },
            http_status=409,
        )
    return min(max(int(base_week), start_week), end_week)


def class_authority_weeks(db, teaching_classes) -> dict[int, int | None]:
    """Batch-resolve non-occurrence authority weeks for a bounded class collection.

    Read workbenches may project hundreds of classes. Resolving term, task and tenant
    timezone per class creates a hidden N+1. This helper keeps that projection bounded:
    one term query, one task query and one timezone resolution for the whole page.
    """
    from app.models import AaTeachingTask, AaTerm
    from .student_exam_read_service import _tenant_timezone

    classes = [row for row in (teaching_classes or []) if row is not None]
    if not classes:
        return {}
    term_ids = sorted({int(row.term_id) for row in classes if row.term_id})
    task_ids = sorted({int(row.teaching_task_id) for row in classes if row.teaching_task_id})
    terms = db.scalars(select(AaTerm).where(
        AaTerm.id.in_(term_ids or [-1]),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    )).all()
    tasks = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.id.in_(task_ids or [-1]),
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    )).all()
    terms_by_id = {int(row.id): row for row in terms}
    tasks_by_id = {int(row.id): row for row in tasks}
    zone, _zone_name = _tenant_timezone(db)
    current = datetime.now(zone).astimezone(zone).date()

    result: dict[int, int | None] = {}
    for teaching_class in classes:
        term = terms_by_id.get(int(teaching_class.term_id)) if teaching_class.term_id else None
        task = tasks_by_id.get(int(teaching_class.teaching_task_id)) if teaching_class.teaching_task_id else None
        base_week = _authority_week_from_term(term, current)
        result[int(teaching_class.id)] = _clamp_task_authority_week(
            teaching_class, task, term, base_week
        )
    return result


def class_authority_week(db, teaching_class) -> int | None:
    """Non-occurrence authority week clamped into the linked TeachingTask window."""
    return class_authority_weeks(db, [teaching_class]).get(int(teaching_class.id))


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

    Callers tied to a concrete occurrence pass its resolved teaching week. When week
    is omitted, non-occurrence workflows use ``class_authority_week`` so authority is
    clamped into the linked TeachingTask's actual teaching window.
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
    resolved_week = class_authority_week(db, teaching_class) if week is None else int(week)
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