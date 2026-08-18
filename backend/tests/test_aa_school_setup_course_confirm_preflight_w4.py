"""A-W4 confirm must reuse the exact Course preflight inside one locked transaction."""
from __future__ import annotations

from types import SimpleNamespace


def _bridge():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_preflight_service as bridge
    return bridge


def _row():
    return {
        "courseCode": "CS101",
        "version": "1",
        "courseName": "Python程序设计",
        "category": "MAJOR_CORE",
        "nature": "REQUIRED",
        "credit": "3",
        "hoursTotal": "48",
        "hoursTheory": "32",
        "hoursPractice": "16",
        "hoursExperiment": "",
        "hoursComputer": "",
        "examMode": "EXAM",
        "ownerCollegeId": "17",
        "ownerTeacherId": "81",
        "isCore": "是",
        "prerequisiteCodes": "",
    }


class _ScalarResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _CapturingDb:
    def __init__(self, answers):
        self.answers = list(answers)
        self.statements = []

    def scalars(self, stmt):
        self.statements.append(str(stmt))
        if len(self.statements) > len(self.answers):
            raise AssertionError("unexpected additional SQL")
        return _ScalarResult(self.answers[len(self.statements) - 1])


def _college():
    return SimpleNamespace(id=17, status="ACTIVE")


def _teacher():
    return SimpleNamespace(id=81, user_type="TEACHER", status="ACTIVE")


def _prepare(monkeypatch, answers):
    bridge = _bridge()
    db = _CapturingDb(answers)
    monkeypatch.setattr(bridge, "_tid", lambda: 1001)
    monkeypatch.setattr(
        bridge,
        "build_affairs_context",
        lambda _user, _db: SimpleNamespace(scope_type="TENANT_ALL", college_ids=set()),
    )
    return bridge, db


def test_confirm_preflight_locks_course_college_and_teacher_queries(monkeypatch):
    bridge, db = _prepare(monkeypatch, [[], [_college()], [_teacher()]])
    result = bridge._course_catalog_dry_run_with_db(
        [_row()],
        {"currentRoleCode": "ACADEMIC_ADMIN"},
        db,
        lock_rows=True,
    )
    assert result["createRows"] == 1
    assert len(db.statements) == 3
    assert all("FOR UPDATE" in statement.upper() for statement in db.statements)


def test_plain_dry_run_core_keeps_same_query_shape_without_write_locks(monkeypatch):
    bridge, db = _prepare(monkeypatch, [[], [_college()], [_teacher()]])
    result = bridge._course_catalog_dry_run_with_db(
        [_row()],
        {"currentRoleCode": "ACADEMIC_ADMIN"},
        db,
        lock_rows=False,
    )
    assert result["createRows"] == 1
    assert len(db.statements) == 3
    assert all("FOR UPDATE" not in statement.upper() for statement in db.statements)


def test_locking_query_order_is_course_then_college_then_user(monkeypatch):
    bridge, db = _prepare(monkeypatch, [[], [_college()], [_teacher()]])
    bridge._course_catalog_dry_run_with_db(
        [_row()],
        {"currentRoleCode": "ACADEMIC_ADMIN"},
        db,
        lock_rows=True,
    )
    normalized = [statement.lower() for statement in db.statements]
    assert "t_aa_course" in normalized[0]
    assert "t_college" in normalized[1]
    assert "t_user" in normalized[2]


def test_confirm_preflight_keeps_duplicate_rejection_before_any_db_query(monkeypatch):
    bridge, db = _prepare(monkeypatch, [])
    duplicate = [_row(), _row()]
    result = bridge._course_catalog_dry_run_with_db(
        duplicate,
        {"currentRoleCode": "ACADEMIC_ADMIN"},
        db,
        lock_rows=True,
    )
    assert result["rejectRows"] == 2
    assert result["validRows"] == 0
    assert db.statements == []


def test_public_wrapper_delegates_to_same_db_core_without_locks(monkeypatch):
    bridge = _bridge()
    captured = {}
    sentinel_db = object()

    class _Session:
        def __enter__(self):
            return sentinel_db

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_core(rows, user, db, *, lock_rows=False):
        captured.update(rows=rows, user=user, db=db, lock_rows=lock_rows)
        return {"totalRows": len(rows)}

    monkeypatch.setattr(bridge, "session", lambda: _Session())
    monkeypatch.setattr(bridge, "_course_catalog_dry_run_with_db", fake_core)
    rows = [_row()]
    user = {"currentRoleCode": "ACADEMIC_ADMIN"}
    assert bridge.course_catalog_dry_run(rows, user) == {"totalRows": 1}
    assert captured == {
        "rows": rows,
        "user": user,
        "db": sentinel_db,
        "lock_rows": False,
    }
