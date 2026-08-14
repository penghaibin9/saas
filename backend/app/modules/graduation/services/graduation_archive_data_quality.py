"""Graduation archive dirty-data policy for legacy student identities.

Rows with missing student name / student number remain visible for reconciliation,
but every archive write path must treat them as read-only until the canonical
student master is repaired. This module is deliberately pure so read models,
batch previews and route guards share one rule without creating a second writer.
"""
from __future__ import annotations

from app.core.exceptions import AppException


def identity_anomaly_reasons(student) -> list[str]:
    reasons: list[str] = []
    if not str(getattr(student, "name", "") or "").strip():
        reasons.append("学生姓名缺失")
    if not str(getattr(student, "student_no", "") or "").strip():
        reasons.append("学号缺失")
    return reasons


def readonly_missing_markers(student) -> list[str]:
    return [f"历史主档异常：{reason}" for reason in identity_anomaly_reasons(student)]


def assert_archive_identity_writable(student):
    reasons = identity_anomaly_reasons(student)
    if reasons:
        raise AppException(
            "DATA_CONFLICT",
            "历史主档存在异常，仅允许只读查看；请先修复学生姓名/学号后再办理归档："
            + "；".join(reasons),
        )
    return student


__all__ = [
    "assert_archive_identity_writable",
    "identity_anomaly_reasons",
    "readonly_missing_markers",
]
