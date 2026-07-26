"""V2-02 教学任务兼容属性与旧入口守卫。

AaTeachingTask 真实字段只有 class_id / teaching_class_name，没有 class_name。早期教学班服务沿用了
若干旧DTO对 class_name 的直接访问，会在真实运行时触发 AttributeError。本层不伪造数据库列，
仅给读取函数传入安全代理；同时把遗留 backfill_term 收口到最终原子回填服务。
"""
from __future__ import annotations

from . import academic_affairs_teaching_class_admin_service as _admin
from . import academic_affairs_teaching_class_query_service as _query
from . import academic_affairs_teaching_class_service as _base

_original_task_snapshot = _base._task_snapshot
_original_class_dto = _query._class_dto
_original_preview_rows = _admin._preview_rows


class _TeachingTaskCompat:
    def __init__(self, task):
        self._task = task

    @property
    def class_name(self):
        return getattr(self._task, "class_name", None) or ""

    def __getattr__(self, name):
        return getattr(self._task, name)


def _task_snapshot(task, batch) -> str:
    return _original_task_snapshot(_TeachingTaskCompat(task), batch)


def _class_dto(row, task=None, teachers=None):
    safe_task = _TeachingTaskCompat(task) if task is not None else None
    return _original_class_dto(row, safe_task, teachers)


def _preview_rows(db, tasks):
    return _original_preview_rows(db, [_TeachingTaskCompat(task) for task in tasks])


def backfill_term(user, term_id: int, *, dry_run=True):
    """兼容旧签名；正式写入没有审计原因时由最终服务fail-closed。"""
    return _admin.backfill_teaching_classes(
        user,
        int(term_id),
        bool(dry_run),
        "" if dry_run else "",
    )


_base._task_snapshot = _task_snapshot
_base.backfill_term = backfill_term
_query._class_dto = _class_dto
_query.backfill_term = backfill_term
_admin._preview_rows = _preview_rows
