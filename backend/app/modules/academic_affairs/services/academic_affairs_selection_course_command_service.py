"""B-W4 · SelectionCourse canonical write commands.

This module owns the formal SelectionCourse supply mutations exposed by the Move-Only
router.  It does not invent the upstream formation contract before INT freezes it.
The independent invariants enforced here are already available from current code:

- every formal SelectionCourse must bind an explicit TeachingTask;
- the task must exist in the current tenant and be READY;
- the task must point at the same course as the SelectionCourse supply;
- the task batch and selection batch must belong to the same formal term;
- once the INT provenance runtime exists, the exact TeachingTask -> ProgramCourse
  snapshot must be PROVEN and A's canonical policy must allow Selection supply;
- mutable lifecycle/task/supply rows are locked before validation and persistence;
- every supply mutation reuses the canonical term-writable guard;
- capacity/min-capacity invariants are checked atomically against selected_count.

Legacy ``academic_affairs_selection_core_service`` supply writes remain compatibility
debt only; the formal router is statically sealed against calling them.  DB NOT NULL /
FK / generated constraints and provenance schema remain INT-owned.
"""
from __future__ import annotations

import importlib

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_core_service as _core
from . import academic_affairs_selection_service as _selection


_UPSTREAM_PROVENANCE_MODULE = (
    f"{__package__}.academic_affairs_task_formation_provenance_service"
)


def _conflict(message: str, **details) -> AppException:
    return AppException(
        "DATA_CONFLICT",
        message,
        details=details or None,
        http_status=409,
    )


def _required_int(value, *, field: str, message: str) -> int:
    if value is None or not str(value).strip():
        raise _conflict(message, field=field)
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise _conflict(message, field=field) from exc
    if parsed <= 0:
        raise _conflict(message, field=field)
    return parsed


def _lock_supply_course(db, course_id):
    from app.models import AaSelectionCourse

    row = db.execute(
        select(AaSelectionCourse).where(
            AaSelectionCourse.id == int(course_id),
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.is_deleted.is_(False),
        ).with_for_update()
    ).scalar_one_or_none()
    if not row:
        raise not_found("可选课程供给项不存在")
    return row


def _lock_supply_batch(db, batch_id):
    from app.models import AaSelectionBatch

    row = db.execute(
        select(AaSelectionBatch).where(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _core._tid(),
            AaSelectionBatch.is_deleted.is_(False),
        ).with_for_update()
    ).scalar_one_or_none()
    if not row:
        raise not_found("选课批次不存在")
    return row


def _guard_selection_formation(db, teaching_task_id: int) -> bool:
    """Activate the frozen A/INT formation handoff without copying A policy into B.

    The already-sealed B independent surface predates the shared provenance module, so
    a standalone B checkout keeps that historical sub-seal and returns ``False`` only
    when the *whole* upstream provenance module is genuinely absent.  Once INT is
    present in the integration tree, missing/partial provenance is fail-closed through
    B's existing dependency normalizer and eligibility is delegated to A's canonical
    ``selection_eligible`` policy.  A broken partial upstream import is never swallowed.
    """
    try:
        provenance = importlib.import_module(
            ".academic_affairs_task_formation_provenance_service",
            package=__package__,
        )
    except ModuleNotFoundError as exc:
        if exc.name == _UPSTREAM_PROVENANCE_MODULE:
            return False
        raise

    policy = importlib.import_module(
        ".academic_affairs_task_formation_policy",
        package=__package__,
    )
    dependency = importlib.import_module(
        ".academic_affairs_selection_formation_dependency",
        package=__package__,
    )

    snapshot = provenance.resolve_task_formation_snapshot(
        db,
        int(teaching_task_id),
        tenant_id=_core._tid(),
    )
    normalized = dependency.require_proven_task_formation_snapshot(
        snapshot,
        teaching_task_id=int(teaching_task_id),
    )
    mode_key = "formation" + "Mode"
    mode = normalized[mode_key]
    try:
        allowed = bool(policy.selection_eligible(mode))
    except ValueError as exc:
        raise _conflict(
            "教学任务编班模式非法，禁止进入选课供给",
            blocker="SELECTION_FORMATION_INVALID",
            teachingTaskId=str(teaching_task_id),
            resolvedMode=str(mode or ""),
        ) from exc
    if not allowed:
        raise _conflict(
            "当前教学任务的正式编班模式不允许进入学生选课供给",
            blocker="SELECTION_FORMATION_NOT_SELECTABLE",
            teachingTaskId=str(teaching_task_id),
            sourceProgramCourseId=str(normalized.get("sourceProgramCourseId") or ""),
            resolvedMode=str(mode or ""),
        )
    return True


def add_course(user, batch_id, body) -> dict:
    """Create one task-bound SelectionCourse in a single canonical transaction."""
    from app.models import (
        AaCourse,
        AaSelectionBatch,
        AaSelectionCourse,
        AaTeachingTask,
        AaTeachingTaskBatch,
    )

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))

        # Freeze the lifecycle state before deciding whether supply is still writable.
        # This serializes add-course against PUBLISH/OPEN/CLOSE, whose canonical
        # commands also lock the SelectionBatch row before changing its state.
        batch = db.execute(
            select(AaSelectionBatch).where(
                AaSelectionBatch.id == int(batch_id),
                AaSelectionBatch.tenant_id == _core._tid(),
                AaSelectionBatch.is_deleted.is_(False),
            ).with_for_update()
        ).scalar_one_or_none()
        if not batch:
            raise not_found("选课批次不存在")
        _selection._guard_batch_writable(db, batch)
        if batch.status not in (_core._BATCH_DRAFT, _core._BATCH_PUBLISHED):
            raise _core._invalid("仅 DRAFT/PUBLISHED 批次可增课程")

        course_id = _required_int(
            getattr(body, "courseId", None),
            field="courseId",
            message="可选课程必须关联有效课程主档",
        )
        course = db.query(AaCourse).filter(
            AaCourse.id == course_id,
            AaCourse.tenant_id == _core._tid(),
            AaCourse.is_deleted.is_(False),
        ).first()
        if not course:
            raise not_found("课程不存在")

        task_id = _required_int(
            getattr(body, "teachingTaskId", None),
            field="teachingTaskId",
            message="可选课程必须绑定 READY 教学任务",
        )

        # READY is a mutable authority fact. Lock the task row so another writer
        # cannot invalidate it between this check and SelectionCourse persistence.
        task = db.execute(
            select(AaTeachingTask).where(
                AaTeachingTask.id == task_id,
                AaTeachingTask.tenant_id == _core._tid(),
                AaTeachingTask.is_deleted.is_(False),
            ).with_for_update()
        ).scalar_one_or_none()
        if not task:
            raise not_found("教学任务不存在")
        if str(task.status or "").upper() != "READY":
            raise _conflict(
                "教学任务未处于 READY，不可作为选课供给",
                teachingTaskId=str(task_id),
                taskStatus=str(task.status or ""),
            )
        if not getattr(task, "course_id", None) or int(task.course_id) != course_id:
            raise _conflict(
                "教学任务与所选课程不一致",
                teachingTaskId=str(task_id),
                requestedCourseId=str(course_id),
                taskCourseId=str(getattr(task, "course_id", "") or ""),
            )
        if not getattr(task, "batch_id", None):
            raise _conflict(
                "教学任务缺少正式任务批次归属",
                teachingTaskId=str(task_id),
            )

        task_batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.id == int(task.batch_id),
            AaTeachingTaskBatch.tenant_id == _core._tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).first()
        if not task_batch or not getattr(task_batch, "term_id", None):
            raise _conflict(
                "教学任务缺少正式学期归属",
                teachingTaskId=str(task_id),
                teachingTaskBatchId=str(getattr(task, "batch_id", "") or ""),
            )
        if not getattr(batch, "term_id", None):
            raise _conflict("选课批次必须绑定正式学期", batchId=str(batch.id))
        if int(task_batch.term_id) != int(batch.term_id):
            raise _conflict(
                "教学任务与选课批次不属于同一学期",
                teachingTaskId=str(task_id),
                taskTermId=str(task_batch.term_id),
                selectionTermId=str(batch.term_id),
            )

        _guard_selection_formation(db, task_id)

        duplicate = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == _core._tid(),
            AaSelectionCourse.batch_id == batch.id,
            AaSelectionCourse.course_id == course_id,
            AaSelectionCourse.teaching_task_id == task_id,
            AaSelectionCourse.is_deleted.is_(False),
        ).first()
        if duplicate:
            raise AppException("VALIDATION_ERROR", "该课程(教学班)已在本批次")

        row = AaSelectionCourse(
            tenant_id=_core._tid(),
            batch_id=batch.id,
            course_id=course_id,
            course_name=getattr(course, "course_name", None) or getattr(course, "name", None),
            teaching_task_id=task_id,
            teacher_key=task.teacher_key,
            teacher_name=task.teacher_name,
            credit=getattr(course, "credit", None),
            capacity=int(getattr(body, "capacity", 0) or 0),
            min_capacity=int(getattr(body, "minCapacity", 0) or 0),
            selected_count=0,
            status=_core._COURSE_OPEN,
        )
        db.add(row)
        db.flush()
        _core._audit(
            db,
            batch.id,
            "SELECTION_COURSE_ADD",
            f"增课程 {row.course_name}; teachingTaskId={task_id}; termId={batch.term_id}",
        )
        db.commit()
        return _core._course_dto(row)


def update_course(user, course_id, body) -> dict:
    """Update supply capacity atomically without falling back to legacy writes."""
    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        # Global Selection command lock order keeps the hot supply row before batch.
        course = _lock_supply_course(db, course_id)
        batch = _lock_supply_batch(db, course.batch_id)
        _selection._guard_batch_writable(db, batch)
        if batch.status in (_core._BATCH_LOCKED, _core._BATCH_ARCHIVED):
            raise _core._invalid("批次已锁定，不可改课程容量/规则")

        next_capacity = int(course.capacity or 0)
        next_min_capacity = int(course.min_capacity or 0)
        if getattr(body, "capacity", None) is not None:
            next_capacity = int(body.capacity)
        if getattr(body, "minCapacity", None) is not None:
            next_min_capacity = int(body.minCapacity)

        selected_count = int(course.selected_count or 0)
        if next_capacity < selected_count:
            raise AppException("VALIDATION_ERROR", f"容量不可小于已选人数 {selected_count}")
        if next_min_capacity < 0:
            raise AppException("VALIDATION_ERROR", "开班下限不可小于 0")
        if next_min_capacity > next_capacity:
            raise AppException("VALIDATION_ERROR", "开班下限不可大于课程容量")

        course.capacity = next_capacity
        course.min_capacity = next_min_capacity
        _core._audit(db, batch.id, "SELECTION_COURSE_UPDATE", f"改课程 {course.course_name} 容量/下限")
        db.commit()
        return _core._course_dto(course)


def cancel_course(user, course_id, body=None) -> dict:
    """Cancel a CLOSED-batch supply row and its selected records under one lock order."""
    from app.models import AaSelectionRecord

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        # Keep course→batch ordering aligned with student Selection commands.
        course = _lock_supply_course(db, course_id)
        batch = _lock_supply_batch(db, course.batch_id)
        _selection._guard_batch_writable(db, batch)
        if batch.status != _core._BATCH_CLOSED:
            raise _core._invalid("仅 CLOSED 批次可取消低人数课程")
        if course.status == _core._COURSE_CANCELLED:
            return _core._course_dto(course)

        course.status = _core._COURSE_CANCELLED
        db.query(AaSelectionRecord).filter(
            AaSelectionRecord.selection_course_id == course.id,
            AaSelectionRecord.tenant_id == _core._tid(),
            AaSelectionRecord.status == _core._REC_SELECTED,
            AaSelectionRecord.is_deleted.is_(False),
        ).update(
            {AaSelectionRecord.status: _core._REC_COURSE_CANCELLED},
            synchronize_session=False,
        )
        _core._audit(
            db,
            batch.id,
            "SELECTION_COURSE_CANCEL",
            f"取消开课 {course.course_name}(人数不足)",
        )
        db.commit()
        return _core._course_dto(course)
