"""学生选课身份与课程口径历史兼容入口。

稳定账号绑定、courseCode 先修规则和统一有效成绩判断已收口到
``academic_affairs_selection_service``。本文件仅保留旧导入路径。
"""
from __future__ import annotations

from . import academic_affairs_selection_service as _canonical

_base = _canonical
_legacy = _canonical

_load_student = _canonical._load_student
_passed_course_codes = _canonical._passed_course_codes
_validate_enroll = _canonical._validate_enroll
student_courses = _canonical.student_courses
student_enroll = _canonical.student_enroll
student_drop = _canonical.student_drop
my_selections = _canonical.my_selections


def __getattr__(name):
    return getattr(_canonical, name)
