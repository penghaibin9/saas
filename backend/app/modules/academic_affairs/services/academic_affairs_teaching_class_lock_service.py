"""独立教学班名单锁定历史兼容入口。

正式教学班、名单版本、选课锁定投影与并发规则统一由
``academic_affairs_teaching_class_service`` 持有。本模块只保留旧 import 路径，
不得再保存第二套名单写事务或覆盖正式 Service。
"""
from __future__ import annotations

from . import academic_affairs_teaching_class_service as _base


# 保留历史按值导入兼容，同时让函数对象与正式 owner 完全相同。
create_roster_version = _base.create_roster_version
ensure_teaching_class_for_task = _base.ensure_teaching_class_for_task
resolve_teaching_task_roster = _base.resolve_teaching_task_roster
project_selection_batch_locked = _base.project_selection_batch_locked
sync_batch_teaching_classes = _base.sync_batch_teaching_classes


def __getattr__(name):
    """其余历史 helper 继续透明转给唯一正式 Service。"""
    return getattr(_base, name)
