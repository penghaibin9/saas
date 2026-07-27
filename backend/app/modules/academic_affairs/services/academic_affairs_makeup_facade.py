"""补考、清考候选历史兼容入口。

稳定学生身份、数据范围和有效成绩候选已收口到 ``academic_affairs_makeup_service``。
本文件仅保留旧导入路径，不再修改 core Service。
"""
from __future__ import annotations

from . import academic_affairs_makeup_service as _canonical

_legacy = _canonical

_student = _canonical._student
_effective_failed_rows = _canonical._effective_failed_rows
makeup_pending = _canonical.makeup_pending
_clearance_candidates = _canonical._clearance_candidates


def __getattr__(name):
    return getattr(_canonical, name)
