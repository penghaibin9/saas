"""Bounded condition DSL.  This module intentionally contains no eval path."""
from __future__ import annotations

from typing import Any

from app.core.exceptions import AppException

LEAF_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"}
GROUP_OPERATORS = {"all", "any"}


def _compare(op: str, actual: Any, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "in":
        return actual in expected if isinstance(expected, (list, tuple, set)) else False
    if op == "not_in":
        return actual not in expected if isinstance(expected, (list, tuple, set)) else True
    if actual is None or expected is None:
        return False
    try:
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
    except TypeError:
        return False
    raise AppException("FORM_CONDITION_INVALID", "不支持的表单条件操作符")

def evaluate_condition(condition: dict | None, values: dict[str, Any]) -> bool:
    if condition is None:
        return False
    op = str(condition.get("op") or "").lower()
    if op in GROUP_OPERATORS:
        children = condition.get("conditions")
        if not isinstance(children, list) or not children:
            return False
        results = [evaluate_condition(child, values) for child in children]
        return all(results) if op == "all" else any(results)
    if op in LEAF_OPERATORS:
        return _compare(op, values.get(str(condition.get("field") or "")), condition.get("value"))
    raise AppException("FORM_CONDITION_INVALID", "不支持的表单条件操作符")
