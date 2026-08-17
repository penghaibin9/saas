"""A-owned TeachingTask formation provenance consumer boundary.

Only a persisted ``source_program_course_id`` may establish ProgramCourse provenance.
Course/class labels, current Program activation, major/grade and task-majority heuristics
are deliberately excluded.  Legacy/incomplete rows remain UNKNOWN; contradictory direct
links are CONFLICT.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import _tid, session

from .academic_affairs_task_formation_policy import normalize_formation_mode

STATUS_PROVEN = "PROVEN"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_CONFLICT = "CONFLICT"


def _snapshot(task, *, status: str, source_id=None, formation_mode=None, blockers=()) -> dict:
    return {
        "status": status,
        "teachingTaskId": str(task.id),
        "sourceProgramCourseId": str(source_id or ""),
        "formationMode": str(formation_mode or ""),
        "blockers": list(blockers),
    }


def _normalized(value):
    try:
        return normalize_formation_mode(value), None
    except ValueError:
        return None, "FORMATION_MODE_INVALID"


def resolve_task_formation_snapshot(db, task_id, *, tenant_id: int) -> dict:
    """Return B-consumable provenance from the persisted direct source link only."""
    try:
        tid = int(tenant_id)
        task_pk = int(task_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("positive tenant_id and task_id are required") from exc
    if tid <= 0 or task_pk <= 0:
        raise ValueError("positive tenant_id and task_id are required")

    from app.models import AaProgramCourse, AaTeachingTask

    task = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.id == task_pk,
        AaTeachingTask.tenant_id == tid,
        AaTeachingTask.is_deleted.is_(False),
    )).first()
    if not task:
        raise not_found("教学任务不存在")

    source_id = getattr(task, "source_program_course_id", None)
    task_mode, task_error = _normalized(getattr(task, "formation_mode", None))
    if task_error:
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id,
            formation_mode=getattr(task, "formation_mode", None),
            blockers=("TASK_FORMATION_MODE_INVALID",),
        )
    if not source_id:
        return _snapshot(
            task, status=STATUS_UNKNOWN, formation_mode=task_mode,
            blockers=("SOURCE_PROGRAM_COURSE_ID_MISSING",),
        )

    source = db.scalars(select(AaProgramCourse).where(
        AaProgramCourse.id == int(source_id),
        AaProgramCourse.tenant_id == tid,
        AaProgramCourse.is_deleted.is_(False),
    )).first()
    if not source:
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,
            blockers=("SOURCE_PROGRAM_COURSE_NOT_FOUND",),
        )

    source_mode, source_error = _normalized(getattr(source, "formation_mode", None))
    if source_error:
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,
            blockers=("SOURCE_PROGRAM_COURSE_FORMATION_INVALID",),
        )
    if int(getattr(source, "course_id", 0) or 0) != int(getattr(task, "course_id", 0) or 0):
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,
            blockers=("SOURCE_PROGRAM_COURSE_COURSE_MISMATCH",),
        )
    if not task_mode or not source_mode:
        return _snapshot(
            task, status=STATUS_UNKNOWN, source_id=source_id, formation_mode=task_mode,
            blockers=("FORMATION_MODE_UNRESOLVED",),
        )
    if task_mode != source_mode:
        return _snapshot(
            task, status=STATUS_CONFLICT, source_id=source_id, formation_mode=task_mode,
            blockers=("TASK_SOURCE_FORMATION_MISMATCH",),
        )

    return _snapshot(
        task, status=STATUS_PROVEN, source_id=source_id, formation_mode=task_mode,
    )


def get_task_formation_snapshot(task_id) -> dict:
    """Request-context convenience facade; internal callers may share their DB session above."""
    with session() as db:
        return resolve_task_formation_snapshot(db, task_id, tenant_id=_tid())
