from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_change_safety_guard as guard
from app.modules.academic_affairs.services import academic_affairs_change_service as service


class _ScalarResult:
    def __init__(self, rows):
        self.rows = list(rows)

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _FakeDb:
    def __init__(self, *responses):
        self.responses = list(responses)

    def scalars(self, _statement):
        if not self.responses:
            raise AssertionError("unexpected scalar query")
        return _ScalarResult(self.responses.pop(0))


def _row(**kwargs):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "is_deleted": False,
        "year_code": "2026-2027",
        "term_no": 1,
        "status": "PUBLISHED",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.fixture(autouse=True)
def _tenant(monkeypatch):
    monkeypatch.setattr(guard, "_tid", lambda: 1)


def test_safety_guard_is_installed_on_public_change_service():
    # Stage C1 temporal guard is intentionally the outer public wrapper; its frozen
    # inner entry must still be the Package 5 strict safety guard.
    assert getattr(service.submit, "_stage_c1_temporal_guard", False)
    assert service._stage_c1_pre_temporal_submit is guard.strict_submit
    assert service.review is guard.strict_review
    assert service.get_change is guard.strict_get_change
    assert service._assignee_for is guard.strict_assignee_for


def test_canonical_term_code_matches_archive_contract():
    assert guard._canonical_term_code(_row()) == "2026-2027-1"


class _FakeConnection:
    """伪连接：只回答"这个学生主档当前 version 是多少"。"""

    def __init__(self, version):
        self.version = version

    def execute(self, _statement):
        return _ScalarResult([SimpleNamespace(version=self.version)])


def test_new_status_change_freezes_selected_term_code():
    change = _row(term_code=None, student_id=None, idempotency_key=None,
                  expected_student_version=None)
    token = guard._SELECTED_TERM_CODE.set("2026-2027-1")
    try:
        guard._freeze_term_code(None, None, change)
    finally:
        guard._SELECTED_TERM_CODE.reset(token)
    assert change.term_code == "2026-2027-1"


def test_new_status_change_freezes_student_version_and_idempotency_key():
    """异动行落库时必须同时冻结主档 version 快照与幂等键，供终审条件更新和重复提交判定。"""
    change = _row(term_code=None, student_id=42, idempotency_key=None,
                  expected_student_version=None)
    term_token = guard._SELECTED_TERM_CODE.set("2026-2027-1")
    key_token = guard._SELECTED_IDEMPOTENCY_KEY.set("idem-1")
    try:
        guard._freeze_term_code(None, _FakeConnection(7), change)
    finally:
        guard._SELECTED_IDEMPOTENCY_KEY.reset(key_token)
        guard._SELECTED_TERM_CODE.reset(term_token)
    assert change.expected_student_version == 7
    assert change.idempotency_key == "idem-1"


def test_term_code_conflict_fails_closed():
    change = _row(term_code="2025-2026-2")
    token = guard._SELECTED_TERM_CODE.set("2026-2027-1")
    try:
        with pytest.raises(AppException):
            guard._freeze_term_code(None, None, change)
    finally:
        guard._SELECTED_TERM_CODE.reset(token)


def test_current_term_must_be_unique():
    db = _FakeDb([])
    with pytest.raises(AppException) as exc:
        guard._current_writable_term(db)
    assert exc.value.code == "CURRENT_TERM_NOT_UNIQUE"


def test_requested_term_must_match_current_term():
    db = _FakeDb([_row()])
    with pytest.raises(AppException) as exc:
        guard._current_writable_term(db, "2025-2026-2")
    assert exc.value.code == "TERM_MISMATCH"


def test_archived_target_term_cannot_be_reviewed():
    db = _FakeDb([_row(status="ARCHIVED")])
    with pytest.raises(AppException) as exc:
        guard._term_for_change(db, "2026-2027-1")
    assert exc.value.code == "TERM_ARCHIVED"


def test_missing_change_term_cannot_fall_back_to_current_term():
    db = _FakeDb([])
    with pytest.raises(AppException) as exc:
        guard._term_for_change(db, None)
    assert exc.value.code == "STATUS_CHANGE_TERM_MISSING"


def test_self_scope_only_allows_own_change(monkeypatch):
    monkeypatch.setattr(
        guard,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(scope_type="SELF"),
    )
    guard.require_change_scope(object(), {"studentId": "9"}, _row(student_id=9))
    with pytest.raises(AppException):
        guard.require_change_scope(object(), {"studentId": "8"}, _row(student_id=9))


def test_non_self_scope_delegates_to_student_object_guard(monkeypatch):
    calls = []
    context = SimpleNamespace(
        scope_type="COLLEGE",
        require_student=lambda _db, student_id: calls.append(student_id),
    )
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: context)
    guard.require_change_scope(object(), {"currentRoleCode": "COLLEGE_ADMIN"}, _row(student_id=12))
    assert calls == [12]


def test_assignee_must_be_unique_and_nonzero():
    assert guard._pick_unique_assignee([7, 7], "COLLEGE_REVIEW") == 7
    with pytest.raises(AppException):
        guard._pick_unique_assignee([], "COLLEGE_REVIEW")
    with pytest.raises(AppException):
        guard._pick_unique_assignee([7, 8], "AA_OFFICE_FINAL")
