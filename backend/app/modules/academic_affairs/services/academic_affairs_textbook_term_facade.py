"""教材学期保护旧兼容入口。

正式实现已合并到 ``academic_affairs_textbook_final_facade``；本模块不再修改原 Service。
"""
from . import academic_affairs_textbook_final_facade as _service


def __getattr__(name):
    return getattr(_service, name)


create_selection = _service.create_selection
submit_selection = _service.submit_selection
withdraw_selection = _service.withdraw_selection
create_review_batch = _service.create_review_batch
review_batch_advance = _service.review_batch_advance
create_order_batch = _service.create_order_batch
submit_order = _service.submit_order
record_arrival = _service.record_arrival
archive_order_batch = _service.archive_order_batch
cancel_order_batch = _service.cancel_order_batch
generate_distribution = _service.generate_distribution
sign_receipt = _service.sign_receipt
sign_receipt_my = _service.sign_receipt_my
return_distribution = _service.return_distribution
mark_fee = _service.mark_fee
textbook_stock = _service.textbook_stock

__all__ = [name for name in globals() if not name.startswith("_")]
