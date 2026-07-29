"""评教申诉理由不得跨学院、跨教师泄漏。"""
from types import SimpleNamespace

import pytest


class _Query:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.filters = []

    def join(self, *_args, **_kwargs):
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def filter(self, *args, **_kwargs):
        self.filters.extend(args)
        return self

    def count(self):
        return len(self.rows)

    def order_by(self, *_args, **_kwargs):
        return self

    def offset(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, rows=None):
        self.query_obj = _Query(rows)

    def query(self, _model):
        return self.query_obj


class _Session:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *_args):
        return False


def _row():
    return SimpleNamespace(
        id=1,
        result_id=2,
        teacher_key="T001",
        reason="评分依据需要复核",
        status="COLLEGE_REVIEW",
    )


def _prepare(monkeypatch, scope_type, *, college_ids=None, keys=None):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_facade as service

    db = _Db([_row()])
    monkeypatch.setattr(service, "session", lambda: _Session(db))
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(
        service,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(
            scope_type=scope_type,
            college_ids=college_ids or [],
        ),
    )
    monkeypatch.setattr(service, "_derive_keys", lambda _user: set(keys or []))
    return service, db


def test_school_scope_can_view_tenant_appeals(monkeypatch):
    service, _db = _prepare(monkeypatch, "TENANT_ALL")

    rows, total = service.list_appeals({"currentRoleCode": "ACADEMIC_ADMIN"})

    assert total == 1
    assert rows[0]["reason"] == "评分依据需要复核"


def test_college_scope_requires_explicit_college_ids(monkeypatch):
    from app.core.exceptions import AppException

    service, _db = _prepare(monkeypatch, "COLLEGE", college_ids=[])

    with pytest.raises(AppException):
        service.list_appeals({"currentRoleCode": "COLLEGE_ADMIN"})


def test_college_scope_adds_teaching_task_college_filter(monkeypatch):
    service, db = _prepare(monkeypatch, "COLLEGE", college_ids=[10])

    rows, total = service.list_appeals({"currentRoleCode": "COLLEGE_ADMIN"})

    assert total == 1
    assert rows[0]["teacherKey"] == "T001"
    assert any("college_id" in str(expr) for expr in db.query_obj.filters)


def test_teacher_scope_requires_stable_teacher_key(monkeypatch):
    from app.core.exceptions import AppException

    service, _db = _prepare(monkeypatch, "COURSE", keys=[])

    with pytest.raises(AppException):
        service.list_appeals({"currentRoleCode": "ACADEMIC_TEACHER"})


def test_unknown_scope_is_fail_closed(monkeypatch):
    from app.core.exceptions import AppException

    service, _db = _prepare(monkeypatch, "NONE")

    with pytest.raises(AppException):
        service.list_appeals({"currentRoleCode": "STAFF"})
