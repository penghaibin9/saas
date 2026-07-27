"""教材征订、发放与费用归档门禁兼容入口。

正式规则位于 ``academic_affairs_archive_domain_policy``，本文件不再追加归档域或覆盖执行器。
"""
from __future__ import annotations

from . import academic_affairs_archive_service as _canonical
from . import academic_affairs_archive_domain_policy as _policy

_ORDER_TERMINAL = {"ARRIVED", "RECEIVED", "ARCHIVED", "CANCELLED"}
_FEE_TERMINAL = {"PAID", "WAIVED"}
_evaluate_textbook = _policy.evaluate_textbook


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
        return _canonical._result(0, True, "本学期未启用教材征订，不作为归档阻断")
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
    return _canonical._result(
        len(orders) + int(unfinished_distributions) + int(pending_records)
        + int(missing_fee_records) + int(unsettled_fees),
        not blockers,
        "教材征订、发放和费用均已收口" if not blockers else "；".join(blockers),
    )


def __getattr__(name):
    return getattr(_canonical, name)
