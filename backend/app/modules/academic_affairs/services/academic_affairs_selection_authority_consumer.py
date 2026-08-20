from __future__ import annotations

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid

from . import academic_affairs_grade_service as grade_service
from . import academic_affairs_schedule_truth_service as schedule_truth


def _effective_passed_items(student_id: int, user=None) -> list[dict]:
    data = grade_service.transcript(
        int(student_id),
        user or get_current_user_ctx() or {},
    )
    return [
        item for item in (data.get("items") or [])
        if str(item.get("passStatus") or "").upper() == "PASSED"
    ]


def passed_course_codes(student_id: int, user=None) -> set[str]:
    return {
        str(item.get("courseCode") or "").strip().upper()
        for item in _effective_passed_items(student_id, user)
        if str(item.get("courseCode") or "").strip()
    }


def passed_course_names(student_id: int, user=None) -> set[str]:
    return {
        str(item.get("courseName") or "").strip()
        for item in _effective_passed_items(student_id, user)
        if str(item.get("courseName") or "").strip()
    }


def task_slots(db, teaching_task_id):
    if not teaching_task_id:
        return []

    from app.models import AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch

    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == int(teaching_task_id),
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if not task:
        raise AppException(
            "DATA_CONFLICT",
            "选课供给关联的教学任务不存在或已删除，请联系教务管理员修复",
            details={"teachingTaskId": str(teaching_task_id)},
            http_status=409,
        )

    batch = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.id == int(task.batch_id),
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.is_deleted.is_(False),
    ).first()
    if not batch or not batch.term_id:
        raise AppException(
            "DATA_CONFLICT",
            "教学任务未关联有效学期批次，不能判断正式课表冲突",
            details={"teachingTaskId": str(teaching_task_id)},
            http_status=409,
        )

    scopes = [("SCHOOL", 0)]
    if batch.college_id:
        scopes.append(("COLLEGE", int(batch.college_id)))
    active_batch_ids = []
    for scope_type, scope_id in scopes:
        active_id = schedule_truth.active_batch_id(
            db, int(batch.term_id), scope_type, scope_id,
        )
        if active_id and int(active_id) not in active_batch_ids:
            active_batch_ids.append(int(active_id))
    if not active_batch_ids:
        return []

    rows = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id.in_(active_batch_ids),
        AaScheduleItem.task_id == int(teaching_task_id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all()
    containing_batch_ids = {int(row.batch_id) for row in rows}
    if len(containing_batch_ids) > 1:
        raise AppException(
            "DATA_CONFLICT",
            "同一教学任务同时出现在多个当前正式课表范围，请先修复ScopeHead后再选课",
            details={
                "teachingTaskId": str(teaching_task_id),
                "activeScheduleBatchIds": [str(value) for value in sorted(containing_batch_ids)],
            },
            http_status=409,
        )
    return [
        (row.weekday, row.slot_no, row.start_week, row.end_week, row.week_parity)
        for row in rows
    ]
