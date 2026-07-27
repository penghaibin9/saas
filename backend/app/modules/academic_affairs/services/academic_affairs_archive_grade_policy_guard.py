"""有效成绩策略欠账归档门禁兼容入口。

正式归档编排显式调用本规则；本文件不再修改 ``archive_rule_evaluator.evaluate_grade``。
"""
from __future__ import annotations

from . import academic_affairs_archive_domain_policy as _policy
from . import academic_affairs_archive_rule_evaluator as _evaluator


def evaluate_grade(db, term_code, previous_result: dict) -> dict:
    result = _evaluator.evaluate_grade(db, term_code, previous_result)
    return _policy.apply_effective_grade_policy_debt(db, term_code, result)
