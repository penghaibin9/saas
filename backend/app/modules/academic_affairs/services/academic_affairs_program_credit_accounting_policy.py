"""Canonical Program practice-credit accounting policy.

ProgramCourse and PracticeSegment can both carry credit. Without an explicit
accounting policy the same concentrated-practice credit can be counted twice.
Legacy Programs keep historical additive behavior when the JSON policy is absent;
new Program import requires the policy explicitly so no new ambiguity is created.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Mapping

PRACTICE_CREDIT_ADDITIVE = "ADDITIVE"
PRACTICE_CREDIT_INCLUDED_IN_PROGRAM_COURSE = "INCLUDED_IN_PROGRAM_COURSE"
PRACTICE_CREDIT_ACCOUNTING_MODES = frozenset({
    PRACTICE_CREDIT_ADDITIVE,
    PRACTICE_CREDIT_INCLUDED_IN_PROGRAM_COURSE,
})


def normalize_practice_credit_accounting(
    value: object,
    *,
    required: bool = False,
    legacy_default: str = PRACTICE_CREDIT_ADDITIVE,
) -> str:
    text = str(value or "").strip().upper()
    if not text:
        if required:
            raise ValueError("practiceCreditAccounting is required")
        text = str(legacy_default or "").strip().upper()
    if text not in PRACTICE_CREDIT_ACCOUNTING_MODES:
        raise ValueError(f"unsupported practiceCreditAccounting: {text}")
    return text


def practice_credit_accounting_from_requirement(value: object) -> str:
    """Read policy from requirement_json; missing key preserves legacy ADDITIVE."""
    if value is None or value == "":
        return PRACTICE_CREDIT_ADDITIVE
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Program requirement_json is invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Program requirement_json must be a JSON object")
        payload = parsed
    return normalize_practice_credit_accounting(
        payload.get("practiceCreditAccounting"),
        required=False,
    )


def counted_practice_credit(value: object, *, mode: object) -> Decimal:
    credit = value if isinstance(value, Decimal) else Decimal(str(value or 0))
    normalized = normalize_practice_credit_accounting(mode, required=True)
    if normalized == PRACTICE_CREDIT_INCLUDED_IN_PROGRAM_COURSE:
        return Decimal("0")
    return credit


def program_total_credit(
    course_credit: object,
    practice_credit: object,
    *,
    mode: object,
) -> Decimal:
    course = course_credit if isinstance(course_credit, Decimal) else Decimal(str(course_credit or 0))
    practice = counted_practice_credit(practice_credit, mode=mode)
    return course + practice
