"""教材并发锁旧兼容入口。

正式实现已合并到 ``academic_affairs_textbook_final_facade``；本模块不再替换下层 helper。
"""
from . import academic_affairs_textbook_final_facade as _service

_distribution_chain = _service._distribution_chain
_fee_chain = _service._fee_chain
textbook_stock = _service.textbook_stock
generate_distribution = _service.generate_distribution
mark_fee = _service.mark_fee


def __getattr__(name):
    return getattr(_service, name)


__all__ = ["textbook_stock", "generate_distribution", "mark_fee"]
