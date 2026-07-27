"""成绩域历史兼容入口。

正式成绩、有效成绩和学生聚合已收口到 ``academic_affairs_grade_service``。
本文件仅保留旧导入路径，不再修改正式 Service 的函数。
"""
from __future__ import annotations

from . import academic_affairs_grade_service as _canonical
from .academic_affairs_effective_grade_policy_service import grade_identity_key

_legacy = _canonical

effective_grade_rows = _canonical.effective_grade_rows
refresh_academic_aggregates = _canonical._refresh_aggregates


def __getattr__(name):
    return getattr(_canonical, name)
