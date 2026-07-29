"""有效成绩策略欠账历史兼容入口。

正式身份欠账与策略快照欠账已统一由 ``academic_affairs_grade_service.identity_debt`` 返回。
"""
from __future__ import annotations

from . import academic_affairs_grade_service as _canonical

_base = _canonical
_legacy = _canonical
identity_debt = _canonical.identity_debt


def __getattr__(name):
    return getattr(_canonical, name)
