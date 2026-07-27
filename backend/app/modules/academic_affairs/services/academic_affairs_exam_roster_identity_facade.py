"""考务名单版本旧兼容入口。

名单冻结、铺位与发布校验已合并到 ``academic_affairs_exam_facade`` 公开入口；
本模块仅做无副作用兼容导出，不再替换任何函数对象。
"""
from . import academic_affairs_exam_facade as _service

confirm_course = _service.confirm_course
assign_seats = _service.assign_seats
list_courses = _service.list_courses
_check_arrangement_complete = _service._check_arrangement_complete
publish_batch = _service.publish_batch


def __getattr__(name):
    return getattr(_service, name)


__all__ = [
    "confirm_course",
    "assign_seats",
    "list_courses",
    "publish_batch",
]
