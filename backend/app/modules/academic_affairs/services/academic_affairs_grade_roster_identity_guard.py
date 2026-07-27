"""成绩发布名单版本历史兼容入口。

正式发布函数自身已经执行 R9 当前名单校验，本文件仅保留旧导入路径。
"""
from __future__ import annotations

from . import academic_affairs_grade_service as _canonical

_base = _canonical
_legacy = _canonical
publish_grades = _canonical.publish_grades


def __getattr__(name):
    return getattr(_canonical, name)
