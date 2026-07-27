"""P0-10/P0-11：有效成绩策略欠账进入学期归档门禁。"""
from __future__ import annotations

from . import academic_affairs_archive_rule_evaluator as _evaluator
from .academic_affairs_effective_grade_policy_service import policy_snapshot_debt

_original_evaluate_grade = _evaluator.evaluate_grade


def evaluate_grade(db, term_code, previous_result: dict) -> dict:
    result = _original_evaluate_grade(db, term_code, previous_result)
    debt = policy_snapshot_debt(db, term=term_code)
    policy_blockers = int(debt["missingPolicySnapshot"] or 0) + int(debt["legacyNameKey"] or 0)
    if not policy_blockers:
        result["evidence"] = [
            *(result.get("evidence") or []),
            {
                "type": "EFFECTIVE_GRADE_POLICY",
                "policyCode": "LATEST_FORMAL_SOURCE_V1",
                "totalGrades": debt["total"],
                "missingPolicySnapshot": 0,
                "legacyNameKey": 0,
            },
        ]
        return result

    result["present"] = False
    result["result"] = "BLOCKED"
    result["blockingCount"] = int(result.get("blockingCount") or 0) + policy_blockers
    result["ruleCode"] = "GRADE_EFFECTIVE_POLICY_DEBT"
    result["summary"] = (
        f"有效成绩策略欠账{policy_blockers}项：缺少策略快照{debt['missingPolicySnapshot']}条，"
        f"LEGACY_NAME_KEY {debt['legacyNameKey']}条；禁止归档"
    )
    result["remark"] = result["summary"]
    result["route"] = "/admin/academic-affairs/grade-identity-debt"
    result["evidence"] = [
        *(result.get("evidence") or []),
        {
            "type": "EFFECTIVE_GRADE_POLICY_DEBT",
            "policyCode": "LATEST_FORMAL_SOURCE_V1",
            "totalGrades": debt["total"],
            "missingPolicySnapshot": debt["missingPolicySnapshot"],
            "legacyNameKey": debt["legacyNameKey"],
            "sampleGradeIds": debt["sampleGradeIds"],
        },
    ]
    return result


_evaluator.evaluate_grade = evaluate_grade
