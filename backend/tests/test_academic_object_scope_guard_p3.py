"""包 3：教务成绩对象范围与无行政班任务范围回归。"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_object_scope_guard as guard


class _Scope:
    def __init__(self, *, classes=None, colleges=None, deny_student=False):
        self._classes = classes
        self.college_ids = set(colleges or [])
        self.deny_student = deny_student
        self.checked_student_id = None

    def allowed_class_ids(self, _db):
        return self._classes

    def require_student(self, _db, student_id):
        self.checked_student_id = int(student_id)
        if self.deny_student:
            raise AppException("NO_DATA_SCOPE", "越权学生")
        return SimpleNamespace(id=int(student_id))


@contextmanager
def _session(db):
    yield db


def test_transcript_checks_student_scope_before_read(monkeypatch):
    db = object()
    scope = _Scope(deny_student=True)
    called = {"original": False}

    monkeypatch.setattr(guard.grade_core, "session", lambda: _session(db))
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: scope)

    def original(_student_id, _user):
        called["original"] = True
        return {"items": []}

    monkeypatch.setattr(guard, "_ORIGINAL_TRANSCRIPT", original)
    with pytest.raises(AppException) as exc:
        guard.scoped_transcript(99, {"currentRoleCode": "COLLEGE_ADMIN"})
    assert getattr(exc.value, "code", None) == "NO_DATA_SCOPE"
    assert scope.checked_student_id == 99
    assert called["original"] is False


def test_transcript_allows_authorized_target(monkeypatch):
    db = object()
    scope = _Scope()
    monkeypatch.setattr(guard.grade_core, "session", lambda: _session(db))
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: scope)
    monkeypatch.setattr(
        guard,
        "_ORIGINAL_TRANSCRIPT",
        lambda student_id, _user: {"studentId": int(student_id), "items": []},
    )

    result = guard.scoped_transcript("12", {"currentRoleCode": "STUDENT"})
    assert result["studentId"] == 12
    assert scope.checked_student_id == 12


@pytest.mark.parametrize("student_id", [None, "", "bad", 0, -1])
def test_transcript_rejects_invalid_student_id(student_id):
    with pytest.raises(AppException) as exc:
        guard._positive_id(student_id, "studentId")
    assert getattr(exc.value, "code", None) == "VALIDATION_ERROR"


def test_college_task_with_class_must_be_in_allowed_classes(monkeypatch):
    scope = _Scope(classes={10, 11}, colleges={3})
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: scope)

    guard.strict_check_college_scope(
        object(),
        SimpleNamespace(class_id=10),
        {"currentRoleCode": "COLLEGE_ADMIN"},
    )
    with pytest.raises(AppException) as exc:
        guard.strict_check_college_scope(
            object(),
            SimpleNamespace(class_id=99),
            {"currentRoleCode": "COLLEGE_ADMIN"},
        )
    assert getattr(exc.value, "code", None) in {"NO_DATA_SCOPE", "NO_PERMISSION"}


def test_classless_task_requires_matching_stable_college(monkeypatch):
    scope = _Scope(classes={10}, colleges={3})
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: scope)
    monkeypatch.setattr(guard, "_resolve_target_college_ids", lambda _db, _task: {3})

    guard.strict_check_college_scope(
        object(),
        SimpleNamespace(class_id=None, teaching_task_id=8, course_id=9),
        {"currentRoleCode": "COLLEGE_ADMIN"},
    )


def test_classless_task_without_or_outside_college_fails_closed(monkeypatch):
    scope = _Scope(classes={10}, colleges={3})
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: scope)

    monkeypatch.setattr(guard, "_resolve_target_college_ids", lambda _db, _task: set())
    with pytest.raises(AppException):
        guard.strict_check_college_scope(
            object(), SimpleNamespace(class_id=None),
            {"currentRoleCode": "COLLEGE_ADMIN"},
        )

    monkeypatch.setattr(guard, "_resolve_target_college_ids", lambda _db, _task: {4})
    with pytest.raises(AppException):
        guard.strict_check_college_scope(
            object(), SimpleNamespace(class_id=None),
            {"currentRoleCode": "COLLEGE_ADMIN"},
        )


def test_tenant_review_roles_keep_explicit_full_school_scope(monkeypatch):
    monkeypatch.setattr(
        guard,
        "build_affairs_context",
        lambda *_args, **_kwargs: pytest.fail("full-school reviewer should not resolve college scope"),
    )
    guard.strict_check_college_scope(
        object(), SimpleNamespace(class_id=None),
        {"currentRoleCode": "ACADEMIC_ADMIN"},
    )
