"""选课归档门禁兼容入口。

正式规则位于 ``academic_affairs_archive_domain_policy``，本文件仅保留历史函数名，
不再追加归档域或覆盖归档执行器。
"""
from __future__ import annotations

from . import academic_affairs_archive_service as _canonical
from . import academic_affairs_archive_domain_policy as _policy

_active_round_count = _policy._active_round_count
_evaluate_selection = _policy.evaluate_selection


def _selection_gate_result(
    batches,
    *,
    pending_records: int = 0,
    active_rounds: int = 0,
    count_mismatches: int = 0,
    missing_task_courses: int = 0,
):
    batches = list(batches or [])
    if not batches:
        return _canonical._result(0, True, "本学期未启用选课批次，不作为归档阻断")
    unfinished = [
        row for row in batches
        if str(getattr(row, "status", None) or "").upper() not in {"LOCKED", "ARCHIVED"}
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未锁定/未归档选课批次 {len(unfinished)} 个")
    if active_rounds:
        blockers.append(f"仍有未终结选课轮次 {int(active_rounds)} 个")
    if pending_records:
        blockers.append(f"仍有未转正式名单记录 {int(pending_records)} 条")
    if count_mismatches:
        blockers.append(f"课程人数计数与LOCKED名单不一致 {int(count_mismatches)} 门")
    if missing_task_courses:
        blockers.append(f"未关联教学任务的有效课程 {int(missing_task_courses)} 门")
    return _canonical._result(
        len(batches),
        not blockers,
        "选课批次和正式教学名单均已锁定" if not blockers else "；".join(blockers),
    )


def __getattr__(name):
    return getattr(_canonical, name)
