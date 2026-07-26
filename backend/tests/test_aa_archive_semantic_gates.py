"""教务归档语义门禁回归测试。"""
from contextlib import contextmanager
from datetime import date, datetime
from importlib import import_module
from types import SimpleNamespace

import pytest


class _FakeQuery:
    def __init__(self, *, rows=None, count=0, first=None):
        self._rows = list(rows or [])
        self._count = count
        self._first = first

    def filter(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._rows)

    def count(self):
        return self._count

    def first(self):
        return self._first


class _ArchiveDb:
    def __init__(self, *, term=None, grade_tasks=None, active_rechecks=0, graduation_batches=None):
        self.term = term
        self.grade_tasks = list(grade_tasks or [])
        self.active_rechecks = active_rechecks
        self.graduation_batches = list(graduation_batches or [])

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "AaTerm":
            return _FakeQuery(first=self.term)
        if name == "AaGradeTask":
            return _FakeQuery(rows=self.grade_tasks)
        if name == "AaGradeRecheck":
            return _FakeQuery(count=self.active_rechecks)
        if name == "AaGraduationAuditBatch":
            return _FakeQuery(rows=self.graduation_batches)
        raise AssertionError(f"unexpected model: {name}")


def _term():
    return SimpleNamespace(
        id=9,
        tenant_id=1,
        start_date=date(2026, 2, 20),
        end_date=date(2026, 7, 10),
        is_deleted=False,
    )


def test_grade_gate_uses_review_status_and_current_term_join():
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    db = _ArchiveDb(
        grade_tasks=[SimpleNamespace(status="PUBLISHED")],
        active_rechecks=1,
    )
    result = service._evaluate_grade(db, "2025-2026-2")

    assert result["present"] is False
    assert "本学期在途复查 1 条" in result["remark"]


def test_graduation_gate_ignores_historical_batches_outside_term():
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    historical = SimpleNamespace(
        status="GENERATED",
        generate_at=datetime(2025, 6, 1),
        created_at=datetime(2025, 5, 1),
    )
    current = SimpleNamespace(
        status="ARCHIVED",
        generate_at=datetime(2026, 5, 1),
        created_at=datetime(2026, 4, 1),
    )
    result = service._evaluate_graduation(
        _ArchiveDb(term=_term(), graduation_batches=[historical, current]),
        9,
    )

    assert result["present"] is True
    assert result["recordCount"] == 1
    assert "本学期" in result["remark"]


def test_graduation_gate_blocks_current_term_unfinished_batch():
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    current = SimpleNamespace(
        status="PRECHECKED",
        generate_at=datetime(2026, 5, 1),
        created_at=datetime(2026, 4, 1),
    )
    result = service._evaluate_graduation(
        _ArchiveDb(term=_term(), graduation_batches=[current]),
        9,
    )

    assert result["present"] is False
    assert "1 个毕业审核批次未归档" in result["remark"]


def test_graduation_gate_does_not_cross_term_when_dates_missing():
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    term = SimpleNamespace(id=9, tenant_id=1, start_date=None, end_date=None, is_deleted=False)
    result = service._evaluate_graduation(
        _ArchiveDb(term=term, graduation_batches=[SimpleNamespace(status="DRAFT")]),
        9,
    )

    assert result["present"] is True
    assert "停止使用全校历史批次作阻断" in result["remark"]


def test_force_cannot_bypass_missing_archive_gate(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as facade

    legacy = import_module(
        "app.modules.academic_affairs.services.academic_affairs_archive_service"
    )
    batch = SimpleNamespace(id=1, status="MISSING_ITEMS", missing_count=2)
    fake_db = SimpleNamespace()

    @contextmanager
    def fake_session():
        yield fake_db

    monkeypatch.setattr(legacy, "session", fake_session)
    monkeypatch.setattr(legacy, "_ctx", lambda _user, _db: SimpleNamespace(scope_type="TENANT_ALL"))
    monkeypatch.setattr(legacy, "_require_school", lambda _ctx: None)
    monkeypatch.setattr(legacy, "_get_batch", lambda _db, _bid: batch)

    with pytest.raises(AppException) as exc:
        facade.confirm_archive({"currentRoleCode": "ACADEMIC_ADMIN"}, 1, force=True)

    assert exc.value.http_status == 409
    assert "整体强制归档已停用" in exc.value.message
