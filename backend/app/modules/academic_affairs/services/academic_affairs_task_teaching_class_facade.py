"""教学任务→独立教学班双写最终层。

旧任务服务各自管理事务，本层在旧写成功后执行可重试投影：不篡改旧事务结果；单条投影使用
保存点隔离，成功教学班正常提交，失败项返回 projectionErrors 供回填接口修复。
"""
from __future__ import annotations

import json

from app.services.db_service import _tid, session

from . import academic_affairs_task_program_gate_facade as _base
from .academic_affairs_teaching_class_service import (
    ensure_teaching_class_for_task,
    sync_batch_teaching_classes,
)

_original_generate_batch = _base.generate_batch
_original_assign_teacher = _base.assign_teacher
_original_adjust_task = _base.adjust_task
_original_merge_tasks = _base.merge_tasks
_original_split_task = _base.split_task


def __getattr__(name):
    return getattr(_base, name)


def _task_id(result) -> int | None:
    value = (result or {}).get("taskId") or (result or {}).get("id")
    return int(value) if str(value or "").isdigit() else None


def _sync_task(task_id: int) -> dict:
    with session() as db:
        try:
            row = ensure_teaching_class_for_task(db, int(task_id))
            db.commit()
            return {
                "ok": True,
                "teachingTaskId": str(task_id),
                "teachingClassId": str(row.id),
                "rosterVersionNo": int(row.current_roster_version_no or 0),
            }
        except Exception as exc:
            db.rollback()
            return {
                "ok": False,
                "teachingTaskId": str(task_id),
                "error": str(exc),
            }


def generate_batch(body, user) -> dict:
    result = _original_generate_batch(body, user)
    batch_id = int(result["batchId"])
    with session() as db:
        projection = sync_batch_teaching_classes(db, batch_id)
        db.commit()
    result["teachingClassProjection"] = projection
    return result


def assign_teacher(task_id, user, body) -> dict:
    result = _original_assign_teacher(task_id, user, body)
    result["teachingClassProjection"] = _sync_task(int(task_id))
    return result


def adjust_task(task_id, user, body) -> dict:
    result = _original_adjust_task(task_id, user, body)
    result["teachingClassProjection"] = _sync_task(int(task_id))
    return result


def merge_tasks(body, user) -> dict:
    result = _original_merge_tasks(body, user)
    survivor_id = _task_id(result)
    task_ids = sorted({int(value) for value in (getattr(body, "taskIds", None) or []) if str(value).isdigit()})
    projections = [_sync_task(task_id) for task_id in task_ids]
    if survivor_id and survivor_id not in task_ids:
        projections.append(_sync_task(survivor_id))
    result["teachingClassProjections"] = projections
    return result


def split_task(task_id, user) -> dict:
    member_ids = []
    with session() as db:
        from app.models import AaTeachingTask
        task = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(task_id),
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).first()
        if task and task.merge_snapshot_json:
            try:
                snapshot = json.loads(task.merge_snapshot_json)
                member_ids = [int(value) for value in snapshot.get("memberTaskIds", []) if str(value).isdigit()]
            except (TypeError, ValueError):
                member_ids = []
    result = _original_split_task(task_id, user)
    result["teachingClassProjections"] = [
        _sync_task(value) for value in [int(task_id), *member_ids]
    ]
    return result


# 完整路径导入下层任务facade时仍命中双写层。
_base.generate_batch = generate_batch
_base.assign_teacher = assign_teacher
_base.adjust_task = adjust_task
_base.merge_tasks = merge_tasks
_base.split_task = split_task
