"""课堂考勤名单版本历史兼容入口。

名单冻结与读取已显式收口到 ``academic_affairs_attendance_public_service``；
本文件仅保留旧导入路径，不再修改考勤 Service 函数。
"""
from __future__ import annotations

from . import academic_affairs_attendance_public_service as _canonical

create_session = _canonical.create_session
get_session = _canonical.get_session
list_sessions = _canonical.list_sessions
attendance_stats = _canonical.attendance_stats
mark_attendance = _canonical.mark_attendance
submit_session = _canonical.submit_session


def __getattr__(name):
    return getattr(_canonical, name)
