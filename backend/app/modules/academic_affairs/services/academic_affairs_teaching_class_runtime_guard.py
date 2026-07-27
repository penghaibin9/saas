"""教学班旧运行时兼容入口。

教学任务真实字段兼容、教学班 DTO 和存量回填已收口到正式 Service；
本文件仅保留旧导入路径，不再覆盖写入口、查询函数或管理服务。
"""
from __future__ import annotations

from . import academic_affairs_teaching_class_admin_service as _admin
from . import academic_affairs_teaching_class_query_service as _query
from . import academic_affairs_teaching_class_service as _canonical

_safe_class_name = _canonical._safe_class_name
_safe_task_snapshot = _canonical._safe_task_snapshot
backfill_term = _canonical.backfill_term
backfill_teaching_classes = _admin.backfill_teaching_classes
list_teaching_classes = _query.list_teaching_classes
get_teaching_class = _query.get_teaching_class


def __getattr__(name):
    return getattr(_canonical, name)
