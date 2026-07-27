"""成绩认定身份守卫旧兼容入口。

稳定学生身份、课程版本和正式成绩来源回链已合并到
``academic_affairs_recognition_public_service``；本模块仅保留无副作用兼容导出。
"""
from . import academic_affairs_recognition_public_service as _service

_resolve_student = _service._resolve_student
submit = _service.submit
review = _service.review
my = _service.my


def __getattr__(name):
    return getattr(_service, name)


__all__ = ["submit", "review", "my"]
