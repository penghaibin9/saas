"""有效成绩只消费 ACTIVE 正式记录；整组已作废/被替代时不得回捞旧成绩。"""
from __future__ import annotations

from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_service as _policy


def _active_only_resolve_effective_grade(rows, strategy=None):
    grouped = {}
    legacy = []
    for row in rows or []:
        status = str(getattr(row, "record_status", None) or "ACTIVE").upper()
        if status != "ACTIVE":
            continue
        key = _policy.grade_identity_key(row)
        if len(key) > 1 and key[1] == "LEGACY_NAME_KEY":
            legacy.append(row)
            continue
        grouped.setdefault(key, []).append(row)

    selected = list(legacy)
    if legacy:
        _policy._LOG.warning("effective grade kept %s ACTIVE LEGACY_NAME_KEY rows separate", len(legacy))
    for candidates in grouped.values():
        group_strategy = _policy._group_strategy(candidates, strategy)
        if group_strategy == "SINGLE_RECORD":
            selected.append(candidates[0])
        else:
            selected.append(max(candidates, key=lambda row: _policy._rank(row, group_strategy)))
    return selected


_policy.resolve_effective_grade = _active_only_resolve_effective_grade
