"""补考、清考、重修、免修归档门禁兼容入口。

正式规则位于 ``academic_affairs_archive_domain_policy``，本文件不再追加归档域或覆盖执行器。
"""
from __future__ import annotations

from . import academic_affairs_archive_service as _canonical
from . import academic_affairs_archive_domain_policy as _policy

_evaluate_makeup = _policy.evaluate_makeup


def _makeup_gate_result(batches, *, active_retakes: int = 0, active_exemptions: int = 0):
    batches = list(batches or [])
    unfinished = [
        row for row in batches
        if str(getattr(row, "status", None) or "").upper() != "FINISHED"
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未结束补考/清考批次 {len(unfinished)} 个")
    if active_retakes:
        blockers.append(f"仍有在途重修申请 {int(active_retakes)} 条")
    if active_exemptions:
        blockers.append(f"仍有在途免修申请 {int(active_exemptions)} 条")
    return _canonical._result(
        len(batches) + int(active_retakes) + int(active_exemptions),
        not blockers,
        "补考、清考、重修和免修均已收口" if not blockers else "；".join(blockers),
    )


def __getattr__(name):
    return getattr(_canonical, name)
