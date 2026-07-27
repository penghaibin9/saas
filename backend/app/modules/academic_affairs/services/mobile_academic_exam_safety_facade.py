"""移动端考务安全旧兼容入口。

考试安排、缓考候选和提交已合并到 ``mobile_academic_affairs_facade`` 单一公开入口；
本模块仅保留无副作用兼容导出。
"""
from . import mobile_academic_affairs_facade as _service

exam_my = _service.exam_my
exam_defer_options_my = _service.exam_defer_options_my
exam_defer_apply_my = _service.exam_defer_apply_my


def __getattr__(name):
    return getattr(_service, name)


__all__ = ["exam_my", "exam_defer_options_my", "exam_defer_apply_my"]
