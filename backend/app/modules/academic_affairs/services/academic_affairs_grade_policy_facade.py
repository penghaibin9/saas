"""P0-11 正式成绩公开最终层：身份欠账 + 有效成绩策略快照欠账。"""
from __future__ import annotations

from . import academic_affairs_grade_identity_facade as _base
from .academic_affairs_effective_grade_policy_service import policy_snapshot_debt


def __getattr__(name):
    return getattr(_base, name)


def identity_debt(user, term=None) -> dict:
    """教务处治理视图：课程身份、修读次数和策略快照必须同时完整。"""
    identity = _base.identity_debt(user, term)
    with _base._legacy.session() as db:
        policy = policy_snapshot_debt(db, term=term)
    return {
        **identity,
        "missingPolicySnapshot": policy["missingPolicySnapshot"],
        "legacyNameKey": policy["legacyNameKey"],
        "policyReady": policy["ready"],
        "policyCode": "LATEST_FORMAL_SOURCE_V1",
        "ready": bool(identity.get("ready")) and bool(policy.get("ready")),
        "samplePolicyDebtGradeIds": policy["sampleGradeIds"],
    }


# 历史完整模块路径调用identity_debt时也统一返回策略欠账。
_base.identity_debt = identity_debt
