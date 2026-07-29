"""专业分流学生身份历史兼容入口。

稳定身份与学生自助写事务已收口到 ``academic_affairs_major_split_public_service``；
本文件仅保留旧导入路径，不再修改原 Service。
"""
from __future__ import annotations

from . import academic_affairs_major_split_public_service as _canonical

_base = _canonical
_student_profile = _canonical._student_profile
submit_volunteer = _canonical.submit_volunteer
student_open_batches = _canonical.student_open_batches
my_volunteer = _canonical.my_volunteer


def __getattr__(name):
    return getattr(_canonical, name)
