"""补考、清考正式成绩身份历史兼容入口。

来源回链、课程版本、修读次数、名单版本和策略快照已收口到
``academic_affairs_makeup_service.finish_makeup_batch``。
"""
from __future__ import annotations

from . import academic_affairs_makeup_service as _canonical

_base = _canonical
_term = _canonical
_legacy = _canonical

_effective_failed_grade = _canonical._effective_failed_grade
finish_makeup_batch = _canonical.finish_makeup_batch


def __getattr__(name):
    return getattr(_canonical, name)
