"""学籍异动归档门禁必须与真实状态机一致。"""
from datetime import date, datetime
from types import SimpleNamespace


class _Query:
    def __init__(self, *, first=None, rows=None):
        self._first = first
        self._rows = list(rows or [])

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, term, rows):
        self.term = term
        self.rows = rows

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "AaTerm":
            return _Query(first=self.term)
        if name == "AaStatusChange":
            return _Query(rows=self.rows)
        raise AssertionError(f"unexpected model: {name}")


def _term():
    return SimpleNamespace(
        id=9,
        tenant_id=1,
        start_date=date(2026, 2, 20),
        end_date=date(2026, 7, 10),
        is_deleted=False,
    )


def _change(status, *, term_code="2025-2026-2", created_at=None, effective_date=None):
    return SimpleNamespace(
        status=status,
        term_code=term_code,
        created_at=created_at,
        updated_at=created_at,
        effective_date=effective_date,
    )


def test_draft_submitted_and_in_review_block_archive(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    rows = [_change("DRAFT"), _change("SUBMITTED"), _change("IN_REVIEW")]

    result = service._evaluate_status_change(_Db(_term(), rows), 9, "2025-2026-2")

    assert result["present"] is False
    assert result["recordCount"] == 3
    assert "3 条" in result["remark"]


def test_returned_rejected_and_effective_are_terminal(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    rows = [_change("RETURNED"), _change("REJECTED"), _change("EFFECTIVE")]

    result = service._evaluate_status_change(_Db(_term(), rows), 9, "2025-2026-2")

    assert result["present"] is True
    assert result["recordCount"] == 3
    assert "无在途" in result["remark"]


def test_historical_row_without_term_code_uses_term_date_window(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    current = _change(
        "IN_REVIEW",
        term_code=None,
        created_at=datetime(2026, 4, 1, 10, 0),
    )
    old = _change(
        "IN_REVIEW",
        term_code=None,
        created_at=datetime(2025, 4, 1, 10, 0),
    )

    result = service._evaluate_status_change(_Db(_term(), [current, old]), 9, "2025-2026-2")

    assert result["present"] is False
    assert result["recordCount"] == 1


def test_other_term_rows_do_not_block_current_term(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    rows = [_change("IN_REVIEW", term_code="2024-2025-2")]

    result = service._evaluate_status_change(_Db(_term(), rows), 9, "2025-2026-2")

    assert result["present"] is True
    assert result["recordCount"] == 0


def test_unscoped_legacy_rows_are_reported_as_migration_debt(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_facade as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    unknown = _change("EFFECTIVE", term_code=None, created_at=None, effective_date=None)
    term = SimpleNamespace(id=9, tenant_id=1, start_date=None, end_date=None, is_deleted=False)

    result = service._evaluate_status_change(_Db(term, [unknown]), 9, "2025-2026-2")

    assert result["present"] is True
    assert "待迁移补齐" in result["remark"]
