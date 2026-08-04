"""迁移前成绩策略兼容层。

新正式成绩仍必须冻结租户级版本化策略；仅对迁移前、尚未补齐策略字段的历史多次修读记录，
按迁移种子策略 LEGACY_LATEST_ATTEMPT_V1 读取，并持续由 policy_snapshot_debt 暴露治理欠账。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_service as _policy


def _compatible_group_strategy(rows, explicit=None):
    if explicit:
        strategy = str(explicit).upper()
    else:
        frozen = [row for row in rows if getattr(row, "effective_attempt_strategy", None)]
        if frozen:
            latest = max(frozen, key=lambda row: (_policy._base_rank(row)[0], _policy._base_rank(row)[5]))
            strategy = str(latest.effective_attempt_strategy).upper()
        elif len(rows) == 1:
            return "SINGLE_RECORD"
        else:
            strategy = "LATEST_ATTEMPT"
            _policy._LOG.warning(
                "legacy effective-grade fallback LEGACY_LATEST_ATTEMPT_V1; missing frozen policy; gradeIds=%s",
                [str(getattr(row, "id", "")) for row in rows[:20]],
            )
    if strategy not in _policy.VALID_ATTEMPT_STRATEGIES:
        raise AppException(
            "DATA_CONFLICT",
            f"不支持的有效成绩策略：{strategy}",
            http_status=409,
        )
    return strategy


_policy._group_strategy = _compatible_group_strategy
