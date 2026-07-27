"""学生PC/微信考务读取与缓考申请最终安全门面。

保持移动教务其它能力和教师成绩闭环不变，只把学生考试安排、可缓考课程与提交
统一委托 student_exam_read_service，避免兼容入口绕回UTC比较和缺失FINISHED状态。
"""
from __future__ import annotations

from . import mobile_academic_grade_entry_closure_service as _base
from . import student_exam_read_service as _safe_exam


def __getattr__(name):
    return getattr(_base, name)


def exam_my(user) -> dict:
    return _safe_exam.exam_my(user)


def exam_defer_options_my(user) -> dict:
    return _safe_exam.deferrable_courses(user)


def exam_defer_apply_my(user, body) -> dict:
    if not isinstance(body, dict):
        body = vars(body) if body is not None and hasattr(body, "__dict__") else {}
    return _safe_exam.defer_apply(user, body or {})
