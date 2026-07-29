"""学生评教归档门禁兼容入口。

正式规则位于 ``academic_affairs_archive_domain_policy``，本文件不再追加归档域或覆盖执行器。
"""
from __future__ import annotations

from . import academic_affairs_archive_service as _canonical
from . import academic_affairs_archive_domain_policy as _policy

_evaluate_evaluation = _policy.evaluate_evaluation


def _evaluation_gate_result(batches, *, missing_results: int = 0, active_appeals: int = 0):
    batches = list(batches or [])
    if not batches:
        return _canonical._result(0, True, "本学期未启用学生评教，不作为归档阻断")
    unfinished = [
        row for row in batches
        if str(getattr(row, "status", None) or "").upper() not in {"RESULT_READY", "ARCHIVED"}
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未形成最终结果的评教批次 {len(unfinished)} 个")
    if missing_results:
        blockers.append(f"有提交但未生成结果的评教任务 {int(missing_results)} 个")
    if active_appeals:
        blockers.append(f"仍有在途评教申诉 {int(active_appeals)} 条")
    return _canonical._result(
        len(batches),
        not blockers,
        "评教窗口、结果和申诉均已收口" if not blockers else "；".join(blockers),
    )


def __getattr__(name):
    return getattr(_canonical, name)
