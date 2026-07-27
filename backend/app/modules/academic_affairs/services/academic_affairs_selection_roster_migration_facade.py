"""选课锁定名单人工调整历史兼容入口。

正式实现已收口到 ``academic_affairs_selection_service.adjust_record``，
本文件不再维护第二套事务或覆盖任何模块函数。
"""
from __future__ import annotations

from . import academic_affairs_selection_service as _canonical
from . import academic_affairs_selection_roster_projection_service as roster_projection

_base = _canonical
adjust_record = _canonical.adjust_record


def __getattr__(name):
    return getattr(_canonical, name)
