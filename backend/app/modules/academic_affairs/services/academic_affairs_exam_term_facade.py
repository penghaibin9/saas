"""考务学期写保护旧兼容入口。

正式实现已合并到 ``academic_affairs_exam_facade`` 公开入口；本模块不再修改原 Service。
"""
from . import academic_affairs_exam_facade as _service

create_batch = _service.create_batch


def __getattr__(name):
    return getattr(_service, name)


__all__ = ["create_batch"]
