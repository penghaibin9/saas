"""等级考试学生身份历史兼容入口。

稳定学生身份已收口到 ``academic_affairs_level_exam_service._student_profile``；
本文件仅保留旧导入路径，不再修改正式 Service。
"""
from __future__ import annotations

from . import academic_affairs_level_exam_service as _canonical

_base = _canonical
_student_profile = _canonical._student_profile


def __getattr__(name):
    return getattr(_canonical, name)
