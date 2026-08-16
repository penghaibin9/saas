"""B-W4 · SelectionCourse canonical write command.

This command owns the formal ``POST /selection/batches/{batchId}/courses`` write.
It deliberately does not invent formationMode truth before A-C4 freezes.  The
independent invariants enforced here are already available from current code:

- every formal SelectionCourse must bind an explicit TeachingTask;
- the task must exist in the current tenant and be READY;
- the task must point at the same course as the SelectionCourse supply;
- the task batch and selection batch must belong to the same formal term;
- validation and insert happen in one database transaction.

Legacy ``academic_affairs_selection_core_service.add_course`` remains only as
compatibility debt while W4 is open; the Move-Only router is statically sealed
against calling it.  DB NOT NULL / FK / generated constraints remain INT-owned.
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found

from . import academic_affairs_selection_core_service as _core
from . import academic_affairs_selection_service as _selection


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


def add_course(user, batch_id, body) -> dict:
    """Create one task-bound SelectionCourse in a single canonical transaction."""
    from app.models import AaCourse, AaSelectionCourse, AaTeachingTask, AaTeachingTaskBatch

    with _core.session() as db:
        _core._require_manage_scope(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
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
        task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == task_id,
            AaTeachingTask.tenant_id == _core._tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
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
