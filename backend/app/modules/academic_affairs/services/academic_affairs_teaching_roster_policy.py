"""TeachingRoster 历史兼容入口。

正式 Authority 已收口到 ``academic_affairs_teaching_roster_service``。本模块只保留旧导入路径，
不得再通过 import side effect monkey-patch canonical service；否则相同函数会因模块导入顺序出现
不同 ``_tid`` / 校验实现，破坏 exact-head 的单一运行时真值。
"""
from __future__ import annotations

from . import academic_affairs_teaching_roster_service as _canonical

# 兼容旧测试/调用方曾读取的模块属性；真正执行函数始终来自 canonical owner。
_base = _canonical
_tid = _canonical._tid

resolve_teaching_task_roster = _canonical.resolve_teaching_task_roster
validate_selection_lock = _canonical.validate_selection_lock
apply_locked_roster_projection = _canonical.apply_locked_roster_projection


def __getattr__(name):
    return getattr(_canonical, name)
