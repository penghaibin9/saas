"""教材名单与库存旧兼容入口。

正式实现已合并到 ``academic_affairs_textbook_final_facade``；本模块只保留纯规则和兼容导出。
"""
from . import academic_affairs_textbook_final_facade as _service

_ACTIVE_ALLOCATION_STATUSES = _service._ACTIVE_ALLOCATION_STATUSES
_ELIGIBLE_STUDENT_STATUSES = _service._ELIGIBLE_STUDENT_STATUSES
_distribution_shortage = _service._distribution_shortage
generate_distribution = _service.generate_distribution
mark_fee = _service.mark_fee


def __getattr__(name):
    return getattr(_service, name)


__all__ = ["generate_distribution", "mark_fee"]
