"""补考重修免修学生身份历史兼容入口。

学生本人解析已收口到 ``academic_affairs_makeup_service._student``，无法建立唯一绑定时直接404。
"""
from __future__ import annotations

from . import academic_affairs_makeup_service as _canonical

_base = _canonical
_legacy = _canonical
_required_student = _canonical._student


def __getattr__(name):
    return getattr(_canonical, name)
