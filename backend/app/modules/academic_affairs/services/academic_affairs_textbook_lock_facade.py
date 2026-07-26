"""教材签收、退领与费用并发安全最终层。

统一锁顺序：发放记录 → 发放批次 → 费用行。管理员签收、学生签收、退领和收款并发时，
不会重复生成应收，也不会因相反锁顺序形成可避免的死锁。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found

from . import academic_affairs_textbook_roster_facade as _base

_legacy = _base._legacy
_term_layer = _base._term_layer
_original_get_ob = _term_layer._original_get_ob


def __getattr__(name):
    return getattr(_base, name)


def _distribution_chain(db, record_id):
    from app.models import AaTextbookDistributionBatch, AaTextbookDistributionRecord

    record = db.query(AaTextbookDistributionRecord).filter(
        AaTextbookDistributionRecord.id == int(record_id),
        AaTextbookDistributionRecord.tenant_id == _legacy._tid(),
        AaTextbookDistributionRecord.is_deleted.is_(False),
    ).with_for_update().first()
    if not record:
        raise not_found("发放记录不存在")
    distribution = db.query(AaTextbookDistributionBatch).filter(
        AaTextbookDistributionBatch.id == record.batch_id,
        AaTextbookDistributionBatch.tenant_id == _legacy._tid(),
        AaTextbookDistributionBatch.is_deleted.is_(False),
    ).with_for_update().first()
    if not distribution:
        raise AppException("DATA_CONFLICT", "发放记录未关联有效发放批次", http_status=409)
    order = _original_get_ob(db, distribution.order_batch_id)
    _term_layer._term(db, order.term_id)
    return record, distribution, order


def _fee_chain(db, fee_id):
    from app.models import AaTextbookFeeLedger

    # 第一次只取关联recordId；随后按固定顺序锁record，再锁fee。
    preview = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.id == int(fee_id),
        AaTextbookFeeLedger.tenant_id == _legacy._tid(),
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).first()
    if not preview:
        raise not_found("费用记录不存在")
    record, distribution, order = _distribution_chain(db, preview.distribution_record_id)
    fee = db.query(AaTextbookFeeLedger).filter(
        AaTextbookFeeLedger.id == int(fee_id),
        AaTextbookFeeLedger.tenant_id == _legacy._tid(),
        AaTextbookFeeLedger.is_deleted.is_(False),
    ).with_for_update().first()
    if not fee:
        raise not_found("费用记录不存在")
    return fee, record, distribution, order


# 下层函数通过term facade模块对象查找这两个helper；直接替换真实执行对象即可覆盖所有写入口。
_term_layer._distribution_chain = _distribution_chain
_term_layer._fee_chain = _fee_chain
