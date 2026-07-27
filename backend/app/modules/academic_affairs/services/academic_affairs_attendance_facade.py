"""课堂考勤旧兼容导出。

正式实现已合并到 ``academic_affairs_attendance_service``；本模块仅保留无副作用导入兼容，
不替换函数、不修改模块对象，也不承载独立业务规则。
"""
from .academic_affairs_attendance_service import (  # noqa: F401
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
