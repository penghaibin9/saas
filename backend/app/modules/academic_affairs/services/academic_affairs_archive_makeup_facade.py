"""教务归档第11域：补考/清考/重修/免修。

当前真实模型口径：
- AaMakeupBatch 同时存在 term_id/term_code，兼容历史数据；
- 免修模型名为 AaExemption；
- 重修 ENROLLED/FINISHED/REJECTED、免修 APPROVED/REJECTED/CANCELLED 为申请流程终态。
"""
from __future__ import annotations

from sqlalchemy import or_

from app.services.db_service import _tid

from . import academic_affairs_archive_term_guard_facade as _base

_selection_layer = _base._base
_legacy = _selection_layer._legacy
_archive_executor = _selection_layer._archive_executor
_previous_evaluate_domains = _archive_executor._evaluate_domains


def __getattr__(name):
    return getattr(_base, name)


def _makeup_gate_result(
    batches,
    *,
    active_retakes: int = 0,
    active_exemptions: int = 0,
):
    batches = list(batches or [])
    unfinished_batches = [
        row for row in batches
        if str(getattr(row, "status", None) or "").upper() != "FINISHED"
    ]
    blockers = []
    if unfinished_batches:
        blockers.append(f"未结束补考/清考批次 {len(unfinished_batches)} 个")
    if active_retakes:
        blockers.append(f"仍有在途重修申请 {int(active_retakes)} 条")
    if active_exemptions:
        blockers.append(f"仍有在途免修申请 {int(active_exemptions)} 条")
    passed = not blockers
    total = len(batches) + int(active_retakes) + int(active_exemptions)
    return _legacy._result(
        total,
        passed,
        "补考、清考、重修和免修均已收口" if passed else "；".join(blockers),
    )


def _evaluate_makeup(db, term_id, term_code):
    from app.models import AaExemption, AaMakeupBatch, AaRetakeApply

    if not term_id and not term_code:
        return _legacy._result(0, False, "未指定学期，无法核验补考重修免修")
    batch_term_conditions = []
    if term_id:
        batch_term_conditions.append(AaMakeupBatch.term_id == int(term_id))
    if term_code:
        batch_term_conditions.append(AaMakeupBatch.term_code == term_code)
    batches = db.query(AaMakeupBatch).filter(
        AaMakeupBatch.tenant_id == _tid(),
        or_(*batch_term_conditions),
        AaMakeupBatch.is_deleted.is_(False),
    ).all()
    active_retakes = db.query(AaRetakeApply).filter(
        AaRetakeApply.tenant_id == _tid(),
        AaRetakeApply.term_code == term_code,
        AaRetakeApply.status.in_(["SUBMITTED", "ACADEMIC_REVIEW", "APPROVED"]),
        AaRetakeApply.is_deleted.is_(False),
    ).count() if term_code else 0
    active_exemptions = db.query(AaExemption).filter(
        AaExemption.tenant_id == _tid(),
        AaExemption.term_code == term_code,
        AaExemption.status.notin_(["APPROVED", "REJECTED", "CANCELLED"]),
        AaExemption.is_deleted.is_(False),
    ).count() if term_code else 0
    return _makeup_gate_result(
        batches,
        active_retakes=int(active_retakes or 0),
        active_exemptions=int(active_exemptions or 0),
    )


def _evaluate_domains(db, term_id, term_code, college_ids=None):
    results = _previous_evaluate_domains(db, term_id, term_code, college_ids)
    try:
        results["MAKEUP"] = _evaluate_makeup(db, term_id, term_code)
    except Exception as exc:
        results["MAKEUP"] = _legacy._result(0, False, f"该域语义检查失败：{type(exc).__name__}")
    return results


if not any(code == "MAKEUP" for code, _label in _legacy._DOMAINS):
    _legacy._DOMAINS.append(("MAKEUP", "补考重修免修"))

_archive_executor._evaluate_domains = _evaluate_domains
