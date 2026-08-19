"""课堂考勤历史兼容导出。

正式公开入口已经收口到 ``academic_affairs_attendance_public_service``；本模块不再保留
第二套 create/list/stats/get/mark/submit 业务实现。保留此 import path 是为了旧代码、
测试和插件仍能读取成熟常量/辅助函数，同时所有写读命令都进入同一个最终 Authority。
"""
from __future__ import annotations

from . import academic_affairs_attendance_public_service as _public

_STATUS_OK = _public._STATUS_OK
_ADMIN_ROLES = _public._ADMIN_ROLES
ATTENDANCE_TASK_STATUSES = _public.ATTENDANCE_TASK_STATUSES
_ATTENDANCE_TASK_STATUSES = ATTENDANCE_TASK_STATUSES

session = _public.session
_tid = _public._tid
_audit = _public._audit
_role = _public._role
_teacher_keys = _public._teacher_keys
_primary_teacher_key = _public._primary_teacher_key
_check_owner = _public._check_owner
_row = _public._row
attendance_task_executable = _public.attendance_task_executable

create_session = _public.create_session
get_session = _public.get_session
list_sessions = _public.list_sessions
attendance_stats = _public.attendance_stats
mark_attendance = _public.mark_attendance
submit_session = _public.submit_session


def __getattr__(name):
    return getattr(_public, name)


__all__ = [
    "ATTENDANCE_TASK_STATUSES",
    "attendance_task_executable",
    "create_session",
    "get_session",
    "list_sessions",
    "attendance_stats",
    "mark_attendance",
    "submit_session",
]
