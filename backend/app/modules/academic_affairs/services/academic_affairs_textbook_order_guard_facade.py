"""教材征订保护旧兼容入口。

正式实现已合并到 ``academic_affairs_textbook_final_facade``；本模块只保留纯规则和兼容导出。
"""
from . import academic_affairs_textbook_final_facade as _service

_missing_price_textbook_ids = _service._missing_price_textbook_ids
create_order_batch = _service.create_order_batch


def __getattr__(name):
    return getattr(_service, name)


__all__ = ["create_order_batch"]
