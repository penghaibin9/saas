"""课表预发布/正式发布同事务闸门。"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services.db_service import _tid

from . import academic_affairs_schedule_policy as policy
from . import academic_affairs_scheduling_final_service as scheduling_service


def evaluate(db, batch) -> dict:
    from app.models import AaScheduleItem, AaTeachingTask, AaTeachingTaskBatch

    _term, teaching_weeks = policy.term_bounds(db, int(batch.term_id))
    task_batch_query = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(batch.term_id),
        AaTeachingTaskBatch.status == "APPROVED",
        AaTeachingTaskBatch.is_deleted.is_(False),
    )
    if getattr(batch, "college_id", None):
        task_batch_query = task_batch_query.filter(
            AaTeachingTaskBatch.college_id == int(batch.college_id)
        )
    task_batch_ids = [int(row.id) for row in task_batch_query.all()]
    tasks = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(task_batch_ids or [-1]),
        AaTeachingTask.status == "READY",
        AaTeachingTask.no_auto_schedule.is_(False),
        AaTeachingTask.is_deleted.is_(False),
    ).all()
    items = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _tid(),
        AaScheduleItem.batch_id == int(batch.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).all()

    task_map = {int(task.id): task for task in tasks}
    counts: dict[int, int] = {}
    orphan_items = []
    invalid_coordinate_items = []
    for item in items:
        if (
            int(item.weekday or 0) < 1
            or int(item.weekday or 0) > 7
            or int(item.start_week or 0) < 1
            or int(item.end_week or 0) < int(item.start_week or 0)
            or int(item.end_week or 0) > teaching_weeks
        ):
            invalid_coordinate_items.append(item)
        if not item.task_id or int(item.task_id) not in task_map:
            orphan_items.append(item)
            continue
        counts[int(item.task_id)] = counts.get(int(item.task_id), 0) + 1

    missing = []
    over = []
    invalid_tasks = []
    for task in tasks:
        expected = int(task.weekly_hours or 0)
        actual = int(counts.get(int(task.id), 0))
        start_week = int(task.start_week or 1)
        end_week = int(task.end_week or teaching_weeks)
        if expected <= 0 or start_week < 1 or end_week < start_week or end_week > teaching_weeks:
            invalid_tasks.append({
                "taskId": str(task.id),
                "courseName": task.course_name,
                "weeklyHours": task.weekly_hours,
                "startWeek": task.start_week,
                "endWeek": task.end_week,
            })
            continue
        if actual < expected:
            missing.append({
                "taskId": str(task.id),
                "courseName": task.course_name,
                "expectedSessions": expected,
                "scheduledSessions": actual,
            })
        elif actual > expected:
            over.append({
                "taskId": str(task.id),
                "courseName": task.course_name,
                "expectedSessions": expected,
                "scheduledSessions": actual,
            })

    conflicts = scheduling_service.conflict_report_in_session(db, batch)
    expected_sessions = sum(max(0, int(task.weekly_hours or 0)) for task in tasks)
    scheduled_sessions = sum(counts.values())
    complete = bool(tasks) and not any((
        invalid_tasks,
        missing,
        over,
        orphan_items,
        invalid_coordinate_items,
        conflicts["hardCount"],
    ))
    return {
        "batchId": str(batch.id),
        "termId": str(batch.term_id),
        "batchStatus": batch.status,
        "teachingWeeks": teaching_weeks,
        "taskBatchCount": len(task_batch_ids),
        "totalTasks": len(tasks),
        "scheduledTasks": len(counts),
        "expectedSessions": expected_sessions,
        "scheduledSessions": scheduled_sessions,
        "completionRate": round(len(counts) / len(tasks) * 100, 1) if tasks else 0.0,
        "invalidTaskCount": len(invalid_tasks),
        "missingTaskCount": len(missing),
        "overScheduledTaskCount": len(over),
        "orphanItemCount": len(orphan_items),
        "invalidCoordinateItemCount": len(invalid_coordinate_items),
        "hardConflicts": conflicts["hardCount"],
        "softConflicts": conflicts["softCount"],
        "invalidTasks": invalid_tasks,
        "missingTasks": missing,
        "overScheduledTasks": over,
        "orphanItemIds": [str(item.id) for item in orphan_items],
        "invalidCoordinateItemIds": [str(item.id) for item in invalid_coordinate_items],
        "hardConflictItems": conflicts["hardConflicts"],
        "softConflictItems": conflicts["softConflicts"],
        "complete": complete,
        "canPrePublish": complete,
        "ruleVersion": "AA_SCHEDULE_RULE_V2",
    }


def require_publishable(db, batch) -> dict:
    result = evaluate(db, batch)
    if result["complete"]:
        return result
    reasons = []
    if result["totalTasks"] == 0:
        reasons.append("本学期没有可排的 READY 教学任务")
    if result["invalidTaskCount"]:
        reasons.append(f"教学任务周次/周学时异常 {result['invalidTaskCount']} 条")
    if result["missingTaskCount"]:
        reasons.append(f"漏排教学任务 {result['missingTaskCount']} 条")
    if result["overScheduledTaskCount"]:
        reasons.append(f"超排教学任务 {result['overScheduledTaskCount']} 条")
    if result["orphanItemCount"]:
        reasons.append(f"未关联正式教学任务的课表行 {result['orphanItemCount']} 条")
    if result["invalidCoordinateItemCount"]:
        reasons.append(f"周次坐标异常课表行 {result['invalidCoordinateItemCount']} 条")
    if result["hardConflicts"]:
        reasons.append(f"硬冲突 {result['hardConflicts']} 条")
    raise AppException(
        "DATA_CONFLICT",
        "课表尚未达到预发布条件：" + "；".join(reasons),
        details=result,
        http_status=409,
    )
