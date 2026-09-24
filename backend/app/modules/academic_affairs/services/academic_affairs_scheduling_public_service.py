"""排课工作台公开入口：规则/冲突来自 final，汇总与发布共用同一闸门。"""
from __future__ import annotations

import importlib

from app.core.exceptions import not_found

from . import academic_affairs_schedule_gate_service as gate_service

_base = importlib.import_module(
    ".academic_affairs_scheduling_final_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_base, name)


def summary(user, batch_id):
    from app.models import AaScheduleBatch, AaScheduleItem, AaTeacherAvailability, AaTeachingTask

    with _base._base.session() as db:
        _base._base._ctx(user, db)
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _base._base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        result = gate_service.evaluate(db, batch)

        # 只在同一个事务里为闸门结果补充前 100 个可处理任务的展示字段，
        # 避免再次执行整套冲突/漏排计算导致工作台超时。
        queue_source = [*result.get("missingTasks", []), *result.get("invalidTasks", [])]
        queue_source.sort(key=lambda row: (
            0 if int(row.get("scheduledSessions") or 0) == 0 else 1,
            str(row.get("courseName") or ""),
        ))
        queue_ids = [int(row["taskId"]) for row in queue_source[:100] if row.get("taskId")]
        task_rows = db.query(AaTeachingTask).filter(
            AaTeachingTask.tenant_id == _base._base._tid(),
            AaTeachingTask.id.in_(queue_ids or [-1]),
            AaTeachingTask.is_deleted.is_(False),
        ).all()
        task_by_id = {int(row.id): row for row in task_rows}
        task_queue = []
        for source in queue_source[:100]:
            task = task_by_id.get(int(source["taskId"]))
            actual = int(source.get("scheduledSessions") or 0)
            expected = int(source.get("expectedSessions") or source.get("weeklyHours") or 0)
            invalid = source in result.get("invalidTasks", [])
            task_queue.append({
                "taskId": source["taskId"],
                "courseCode": getattr(task, "course_code", None),
                "courseName": source.get("courseName") or getattr(task, "course_name", None),
                "teacherName": getattr(task, "teacher_name", None),
                "teacherKey": getattr(task, "teacher_key", None),
                "classId": str(task.class_id) if task and task.class_id else None,
                "className": getattr(task, "teaching_class_name", None),
                "weeklyHours": expected,
                "totalHours": int(getattr(task, "total_hours", 0) or 0),
                "startWeek": source.get("startWeek") or getattr(task, "start_week", None),
                "endWeek": source.get("endWeek") or getattr(task, "end_week", None),
                "requiredRoomType": getattr(task, "required_room_type", None),
                "expectedSessions": expected,
                "scheduledSessions": actual,
                "remainingSessions": max(0, expected - actual),
                "issueType": "NOT_READY" if invalid else ("UNSCHEDULED" if actual == 0 else "PARTIAL"),
                "issueLabel": "教学任务数据异常" if invalid else ("未排" if actual == 0 else "部分漏排"),
                "canSchedule": not invalid and batch.status == "DRAFT",
            })

        pending_availability_count = db.query(AaTeacherAvailability).filter(
            AaTeacherAvailability.tenant_id == _base._base._tid(),
            AaTeacherAvailability.term_id == int(batch.term_id),
            AaTeacherAvailability.status == "PENDING",
            AaTeacherAvailability.is_deleted.is_(False),
        ).count()
        teacher_objection_count = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == _base._base._tid(),
            AaScheduleItem.batch_id == int(batch.id),
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.objection_status == "PENDING",
            AaScheduleItem.is_deleted.is_(False),
        ).count()

        blockers = []
        if result["totalTasks"] == 0:
            blockers.append("本学期还没有 READY 教学任务")
        if result["invalidTaskCount"]:
            blockers.append(f"{result['invalidTaskCount']} 个教学任务的周次或周学时异常")
        if pending_availability_count:
            blockers.append(f"{pending_availability_count} 条教师不可排时间待处理")
        if result["missingTaskCount"]:
            blockers.append(f"{result['missingTaskCount']} 个教学任务仍有未排节次")
        if result["overScheduledTaskCount"]:
            blockers.append(f"{result['overScheduledTaskCount']} 个教学任务排课超量")
        if result["orphanItemCount"]:
            blockers.append(f"{result['orphanItemCount']} 个课位无法回溯教学任务")
        if result["invalidCoordinateItemCount"]:
            blockers.append(f"{result['invalidCoordinateItemCount']} 个课位周次坐标异常")
        if result["hardConflicts"]:
            blockers.append(f"{result['hardConflicts']} 个硬冲突必须清零")
        if batch.status == "PRE_PUBLISHED" and teacher_objection_count:
            blockers.append(f"{teacher_objection_count} 条教师异议待处理")

        if batch.status in {"PUBLISHED", "SUPERSEDED", "ARCHIVED"}:
            current_stage_key = "PUBLISH"
            if batch.status == "PUBLISHED" and not result["complete"]:
                next_action = {
                    "code": "BATCH_REISSUE",
                    "label": "创建纠错草稿",
                    "description": "保留当前四端正式课表和已排课位，在纠错草稿中补齐漏排后再安全换版；不能用单课位调停课掩盖批次级缺口",
                }
            else:
                next_action = {
                    "code": "CHANGE_LEDGER" if batch.status == "PUBLISHED" else "READ_ONLY",
                    "label": "进入调停课台账" if batch.status == "PUBLISHED" else "查看历史课表",
                    "description": "正式课表日常变更走调停课审批" if batch.status == "PUBLISHED" else "该批次只读留痕",
                }
        elif batch.status == "PRE_PUBLISHED":
            current_stage_key = "PRE_PUBLISH"
            next_action = {
                "code": "HANDLE_OBJECTIONS" if teacher_objection_count else "PUBLISH",
                "label": "处理教师异议" if teacher_objection_count else "正式发布",
                "description": "异议清零后再正式发布" if teacher_objection_count else "发布后同步教师、学生四端课表",
            }
        elif result["totalTasks"] == 0 or result["invalidTaskCount"]:
            current_stage_key = "PREPARE"
            next_action = {"code": "TEACHING_TASKS", "label": "完善教学任务", "description": "先完成教师、班级、周学时和周次确认"}
        elif pending_availability_count and not result["scheduledSessions"]:
            current_stage_key = "PREFERENCE"
            next_action = {"code": "AVAILABILITY", "label": "处理教师偏好", "description": "采纳或驳回待处理的不可排时间"}
        elif not result["scheduledSessions"]:
            current_stage_key = "AUTO"
            next_action = {"code": "AUTO_DRY_RUN", "label": "执行试排预览", "description": "先预览，不写入正式课表"}
        elif result["missingTaskCount"]:
            current_stage_key = "MANUAL"
            next_action = {"code": "TASK_QUEUE", "label": "处理未排与漏排", "description": "从任务队列逐项补齐剩余节次"}
        else:
            current_stage_key = "QUALITY"
            next_action = {
                "code": "CONFLICTS" if result["hardConflicts"] else "PRE_PUBLISH",
                "label": "处理硬冲突" if result["hardConflicts"] else "进入预发布检查",
                "description": "硬冲突必须清零" if result["hardConflicts"] else "排课完整，可执行预发布闸门",
            }

        stage_order = [
            ("PREPARE", "数据准备"), ("PREFERENCE", "教师偏好"),
            ("AUTO", "自动初排"), ("MANUAL", "人工微调"),
            ("QUALITY", "冲突与漏排"), ("PRE_PUBLISH", "预发布"),
            ("PUBLISH", "正式发布"),
        ]
        current_index = next(i for i, row in enumerate(stage_order) if row[0] == current_stage_key)
        result.update({
            "batchName": batch.batch_name,
            "readyTaskCount": result["totalTasks"],
            "confirmedTaskCount": result["totalTasks"],
            "notReadyTaskCount": result["invalidTaskCount"],
            "excludedTaskCount": 0,
            "expectedHours": result["expectedSessions"],
            "scheduledHours": result["scheduledSessions"],
            "unplacedTaskCount": sum(1 for row in result["missingTasks"] if int(row.get("scheduledSessions") or 0) == 0),
            "partiallyScheduledTaskCount": sum(1 for row in result["missingTasks"] if int(row.get("scheduledSessions") or 0) > 0),
            "pendingAvailabilityCount": pending_availability_count,
            "teacherObjectionCount": teacher_objection_count,
            "taskQueue": task_queue,
            "taskQueueTotal": len(queue_source),
            "workflow": {
                "currentStageKey": current_stage_key,
                "steps": [{
                    "key": key,
                    "label": label,
                    "state": "completed" if index < current_index else ("current" if index == current_index else "pending"),
                } for index, (key, label) in enumerate(stage_order)],
                "blockers": blockers,
                "nextAction": next_action,
            },
        })
        return result
