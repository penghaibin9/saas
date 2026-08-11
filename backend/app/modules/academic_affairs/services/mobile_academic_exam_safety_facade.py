"""移动端考务安全旧兼容入口。

考试安排、缓考候选和提交已合并到 ``mobile_academic_affairs_facade`` 单一公开入口；
本模块仅保留无副作用兼容导出，并显式绑定学生考务安全读取服务，避免导入顺序把旧实现抢回公开入口。
"""
from . import mobile_academic_affairs_facade as _service
from . import student_exam_read_service as _safe_exam


def exam_my(user):
    return _safe_exam.exam_my(user)


def exam_defer_options_my(user):
    return _safe_exam.deferrable_courses(user)


def exam_defer_apply_my(user, body):
    return _safe_exam.defer_apply(user, body)


def __getattr__(name):
    return getattr(_service, name)


__all__ = ["exam_my", "exam_defer_options_my", "exam_defer_apply_my"]
