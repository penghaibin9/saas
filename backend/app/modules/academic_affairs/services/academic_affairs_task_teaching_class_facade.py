"""教学任务→独立教学班双写最终层。

旧任务服务各自管理事务，本层在旧写成功后执行可重试投影：不篡改旧事务结果；单条投影使用
保存点隔离，成功教学班正常提交，失败项返回 projectionErrors 供回填接口修复。
合班/拆班除同步教学班外，必须重建行政班成员事实版本，不能只改名称和预计人数。
"""
from __future__ import annotations

import json

from app.services.db_service import _tid, session

from . import academic_affairs_task_program_gate_facade as _base
from . import academic_affairs_teaching_class_lock_service as _teaching_class

ensure_teaching_class_for_task = _teaching_class.ensure_teaching_class_for_task
sync_batch_teaching_classes = _teaching_class.sync_batch_teaching_classes

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


def _refresh_administrative_roster(task_id: int, reason: str) -> dict:
    """合拆班后按教学任务当前行政班并集形成新版本；选课教学班禁止从此入口覆盖。"""
    with session() as db:
        try:
            from app.models import AaSelectionCourse, AaTeachingTask

            task = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == int(task_id),
                AaTeachingTask.tenant_id == _tid(),
                AaTeachingTask.is_deleted.is_(False),
            ).first()
            if not task:
                raise ValueError("教学任务不存在")
            selection_exists = db.query(AaSelectionCourse.id).filter(
                AaSelectionCourse.tenant_id == _tid(),
                AaSelectionCourse.teaching_task_id == int(task_id),
                AaSelectionCourse.is_deleted.is_(False),
            ).first() is not None
            if selection_exists:
                raise ValueError("教学任务已进入选课流程，合拆班名单必须回选课管理重新锁定")

            teaching_class = ensure_teaching_class_for_task(
                db, int(task_id), initialize_admin_roster=False,
            )
            student_ids = _teaching_class._administrative_roster(db, task)
            if not student_ids:
                raise ValueError("教学任务当前行政班范围没有有效学生，不能形成正式名单版本")
            version, created = _teaching_class.create_roster_version(
                db,
                teaching_class,
                student_ids,
                source_type="ADMIN_CLASS",
                source_id=None if task.is_merged else task.class_id,
                reason=reason,
            )
            db.commit()
            return {
                "ok": True,
                "teachingTaskId": str(task_id),
                "teachingClassId": str(teaching_class.id),
                "rosterVersionId": str(version.id),
                "rosterVersionNo": int(version.version_no),
                "memberCount": int(version.member_count),
                "created": bool(created),
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
    result["rosterProjection"] = (
        _refresh_administrative_roster(survivor_id, "教学任务合班后重建行政班成员并集")
        if survivor_id else {"ok": False, "error": "合班结果缺少survivor教学任务ID"}
    )
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
    restored_ids = list(dict.fromkeys([int(task_id), *member_ids]))
    result["teachingClassProjections"] = [_sync_task(value) for value in restored_ids]
    result["rosterProjections"] = [
        _refresh_administrative_roster(value, "教学任务拆班后恢复行政班正式名单")
        for value in restored_ids
    ]
    return result


# 完整路径导入下层任务facade时仍命中双写层。
_base.generate_batch = generate_batch
_base.assign_teacher = assign_teacher
_base.adjust_task = adjust_task
_base.merge_tasks = merge_tasks
_base.split_task = split_task
