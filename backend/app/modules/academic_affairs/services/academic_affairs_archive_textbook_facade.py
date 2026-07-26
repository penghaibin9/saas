"""教务归档第13域：教材征订、发放与费用。

真实模型没有教材费用termCode，全部按以下链路核验所属学期：
``费用→发放记录→发放批次→征订批次→term_id``。

学期归档前：
- 征订批次须 ARRIVED/ARCHIVED/CANCELLED（兼容历史RECEIVED文本）；
- 已到货的学生教材征订须形成发放批次，发放批次须 COMPLETED；
- 不得存在 PENDING 发放记录；
- 已签收/退领记录必须有费用台账；
- 费用只能 PAID/WAIVED，UNPAID/PARTIAL 均阻断；
- 未启用教材业务时不阻断。

教材目录和库存汇总是跨学期主数据，不属于本归档域写冻结对象。
"""
from __future__ import annotations

from collections import defaultdict

from app.services.db_service import _tid

from . import academic_affairs_archive_evaluation_facade as _base

_legacy = _base._legacy
_archive_executor = _base._archive_executor
_previous_evaluate_domains = _archive_executor._evaluate_domains
_ORDER_TERMINAL = {"ARRIVED", "RECEIVED", "ARCHIVED", "CANCELLED"}
_FEE_TERMINAL = {"PAID", "WAIVED"}


def __getattr__(name):
    return getattr(_base, name)


def _textbook_gate_result(
    orders,
    *,
    missing_distribution_orders: int = 0,
    unfinished_distributions: int = 0,
    pending_records: int = 0,
    missing_fee_records: int = 0,
    unsettled_fees: int = 0,
):
    orders = list(orders or [])
    if not orders:
        return _legacy._result(0, True, "本学期未启用教材征订，不作为归档阻断")
    unfinished_orders = [
        row for row in orders
        if str(getattr(row, "status", None) or "").upper() not in _ORDER_TERMINAL
    ]
    blockers = []
    if unfinished_orders:
        blockers.append(f"未到货/未取消征订批次 {len(unfinished_orders)} 个")
    if missing_distribution_orders:
        blockers.append(f"已到货但未形成发放批次的征订 {int(missing_distribution_orders)} 个")
    if unfinished_distributions:
        blockers.append(f"未完成教材发放批次 {int(unfinished_distributions)} 个")
    if pending_records:
        blockers.append(f"仍有待处理教材发放记录 {int(pending_records)} 条")
    if missing_fee_records:
        blockers.append(f"已签收/退领但缺少费用台账 {int(missing_fee_records)} 条")
    if unsettled_fees:
        blockers.append(f"未结清教材费用 {int(unsettled_fees)} 条")
    passed = not blockers
    total = (
        len(orders)
        + int(unfinished_distributions)
        + int(pending_records)
        + int(missing_fee_records)
        + int(unsettled_fees)
    )
    return _legacy._result(
        total,
        passed,
        "教材征订、发放和费用均已收口" if passed else "；".join(blockers),
    )


def _evaluate_textbook(db, term_id):
    from app.models import (
        AaTextbookDistributionBatch,
        AaTextbookDistributionRecord,
        AaTextbookFeeLedger,
        AaTextbookOrderBatch,
        AaTextbookOrderItem,
    )

    if not term_id:
        return _legacy._result(0, False, "未指定学期，无法核验教材业务")
    orders = db.query(AaTextbookOrderBatch).filter(
        AaTextbookOrderBatch.tenant_id == _tid(),
        AaTextbookOrderBatch.term_id == int(term_id),
        AaTextbookOrderBatch.is_deleted.is_(False),
    ).all()
    if not orders:
        return _textbook_gate_result([])
    order_ids = [int(row.id) for row in orders]

    items = db.query(AaTextbookOrderItem).filter(
        AaTextbookOrderItem.tenant_id == _tid(),
        AaTextbookOrderItem.order_batch_id.in_(order_ids),
        AaTextbookOrderItem.is_deleted.is_(False),
    ).all()
    ordered_qty = defaultdict(int)
    for item in items:
        ordered_qty[int(item.order_batch_id)] += int(item.order_qty or 0)

    distributions = db.query(AaTextbookDistributionBatch).filter(
        AaTextbookDistributionBatch.tenant_id == _tid(),
        AaTextbookDistributionBatch.order_batch_id.in_(order_ids),
        AaTextbookDistributionBatch.is_deleted.is_(False),
    ).all()
    distribution_order_ids = {int(row.order_batch_id) for row in distributions}
    missing_distribution_orders = sum(
        1 for order in orders
        if str(order.status or "").upper() in {"ARRIVED", "RECEIVED", "ARCHIVED"}
        and ordered_qty.get(int(order.id), 0) > 0
        and int(order.id) not in distribution_order_ids
    )
    unfinished_distributions = sum(
        1 for row in distributions
        if str(row.status or "").upper() != "COMPLETED"
    )

    distribution_ids = [int(row.id) for row in distributions]
    records = []
    if distribution_ids:
        records = db.query(AaTextbookDistributionRecord).filter(
            AaTextbookDistributionRecord.tenant_id == _tid(),
            AaTextbookDistributionRecord.batch_id.in_(distribution_ids),
            AaTextbookDistributionRecord.is_deleted.is_(False),
        ).all()
    pending_records = sum(
        1 for row in records if str(row.status or "").upper() == "PENDING"
    )

    chargeable_records = [
        row for row in records
        if str(row.status or "").upper() in {"RECEIVED", "RETURNED", "EXCHANGED"}
    ]
    chargeable_ids = [int(row.id) for row in chargeable_records]
    fees = []
    if chargeable_ids:
        fees = db.query(AaTextbookFeeLedger).filter(
            AaTextbookFeeLedger.tenant_id == _tid(),
            AaTextbookFeeLedger.distribution_record_id.in_(chargeable_ids),
            AaTextbookFeeLedger.is_deleted.is_(False),
        ).all()
    fee_record_ids = {int(row.distribution_record_id) for row in fees}
    missing_fee_records = sum(
        1 for row in chargeable_records if int(row.id) not in fee_record_ids
    )
    unsettled_fees = sum(
        1 for row in fees
        if str(row.status or "").upper() not in _FEE_TERMINAL
    )
    return _textbook_gate_result(
        orders,
        missing_distribution_orders=missing_distribution_orders,
        unfinished_distributions=unfinished_distributions,
        pending_records=pending_records,
        missing_fee_records=missing_fee_records,
        unsettled_fees=unsettled_fees,
    )


def _evaluate_domains(db, term_id, term_code, college_ids=None):
    results = _previous_evaluate_domains(db, term_id, term_code, college_ids)
    try:
        results["TEXTBOOK"] = _evaluate_textbook(db, term_id)
    except Exception as exc:
        results["TEXTBOOK"] = _legacy._result(0, False, f"该域语义检查失败：{type(exc).__name__}")
    return results


if not any(code == "TEXTBOOK" for code, _label in _legacy._DOMAINS):
    _legacy._DOMAINS.append(("TEXTBOOK", "教材征订发放费用"))

_archive_executor._evaluate_domains = _evaluate_domains
