"""V2-02 教学任务兼容属性守卫。

AaTeachingTask 真实字段只有 class_id / teaching_class_name，没有 class_name。早期教学班服务沿用了
若干旧DTO对 class_name 的直接访问，会在真实运行时触发 AttributeError。本层不伪造数据库列，
仅给读取函数传入安全代理；行政班名称后续从组织字典展示，缺失时保留ID。
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


_base._task_snapshot = _task_snapshot
_query._class_dto = _class_dto
_admin._preview_rows = _preview_rows
