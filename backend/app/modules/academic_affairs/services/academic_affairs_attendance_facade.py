"""课堂考勤旧兼容导出。

正式公开实现为 ``academic_affairs_attendance_public_service``；本模块仅保留无副作用导入兼容。
"""
from .academic_affairs_attendance_public_service import (  # noqa: F401
    attendance_stats,
    create_session,
    get_session,
    list_sessions,
    mark_attendance,
    submit_session,
)

__all__ = [
    "attendance_stats",
    "create_session",
    "get_session",
    "list_sessions",
    "mark_attendance",
    "submit_session",
]
