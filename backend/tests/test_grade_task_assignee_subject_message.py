"""Focused regressions for Grade approval assignee diagnostics and authority routing."""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_grade_task_assignee_guard as guard


def _empty_academic_candidates(monkeypatch):
    monkeypatch.setattr(guard, "_runtime_permission_holder_ids", lambda db, permission: [])
    monkeypatch.setattr(guard, "_college_bound_user_ids", lambda db: set())
    monkeypatch.setattr(guard, "_preferred_role_candidates", lambda db, candidates, role: list(candidates))


def test_grade_task_assignee_conflict_names_grade_task(monkeypatch):
    """Normal Grade submit must never report a correction-specific blocker."""
    _empty_academic_candidates(monkeypatch)

    with pytest.raises(AppException) as exc:
        guard.resolve_grade_task_assignee(object(), guard.ACADEMIC_NODE, object())

    assert exc.value.http_status == 409
    assert "成绩任务审批节点没有唯一真实受理人" in exc.value.message
    assert "成绩更正" not in exc.value.message
    assert exc.value.details["subject"] == "成绩任务"


def test_shared_resolver_preserves_schedule_change_subject(monkeypatch):
    """The shared resolver must identify Schedule Change when that flow calls it."""
    _empty_academic_candidates(monkeypatch)

    with pytest.raises(AppException) as exc:
        guard.resolve_grade_task_assignee(
            object(),
            guard.ACADEMIC_NODE,
            object(),
            college_perm=guard.SCHEDULE_CHANGE_COLLEGE_PERM,
            academic_perm=guard.SCHEDULE_CHANGE_ACADEMIC_PERM,
            subject="调停课单",
        )

    assert exc.value.http_status == 409
    assert "调停课单审批节点没有唯一真实受理人" in exc.value.message
    assert exc.value.details["subject"] == "调停课单"


def test_academic_node_prefers_domain_owner_before_unique_check(monkeypatch):
    """SCHOOL_ADMIN fallback must not make a concrete ACADEMIC_ADMIN assignment ambiguous."""
    monkeypatch.setattr(guard, "_runtime_permission_holder_ids", lambda db, permission: [101, 202])
    monkeypatch.setattr(guard, "_college_bound_user_ids", lambda db: set())

    seen = {}

    def prefer(db, candidates, role):
        seen["candidates"] = list(candidates)
        seen["role"] = role
        return [202]

    monkeypatch.setattr(guard, "_preferred_role_candidates", prefer)
    assert guard.resolve_grade_task_assignee(object(), guard.ACADEMIC_NODE, object()) == 202
    assert seen == {"candidates": [101, 202], "role": "ACADEMIC_ADMIN"}
