"""正式成绩身份历史兼容入口。

课程版本、修读次数、教学班名单版本和来源回链已收口到
``academic_affairs_grade_service``。本文件仅保留旧导入路径，不再覆盖公开或 core Service。
"""
from __future__ import annotations

from . import academic_affairs_grade_service as _canonical

_base = _canonical
_legacy = _canonical

create_grade_task = _canonical.create_grade_task
publish_grades = _canonical.publish_grades
identity_debt = _canonical.identity_debt
effective_grade_rows = _canonical.effective_grade_rows


def __getattr__(name):
    return getattr(_canonical, name)
