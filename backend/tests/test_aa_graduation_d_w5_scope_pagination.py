from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace


def _sql(statement) -> str:
    return str(statement).lower()


class _Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _ScopedDb:
    def __init__(self):
        self.count_query = None
        self.page_query = None
        self.aggregate_query = None

    def scalar(self, statement):
        self.count_query = statement
        return 1

    def scalars(self, statement):
        self.page_query = statement
        return _Rows(
            [
                SimpleNamespace(
                    id=1,
                    batch_name="college-visible-oldest",
                    grade_year="2026",
                    major_id=None,
                    status="OPEN",
                )
            ]
        )

    def execute(self, statement):
        self.aggregate_query = statement
        return _Rows(
            [
                SimpleNamespace(
                    batch_id=1,
                    total=1,
                    passed=0,
                    abnormal=1,
                    concluded=0,
                    archived=0,
                )
            ]
        )


class _NoQueryDb:
    def scalar(self, _statement):
        raise AssertionError("empty college scope must not count tenant batches")

    def scalars(self, _statement):
        raise AssertionError("empty college scope must not fetch tenant batches")

    def execute(self, _statement):
        raise AssertionError("empty college scope must not aggregate tenant results")


def test_college_scope_is_applied_before_count_page_and_aggregate(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as service

    db = _ScopedDb()

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(service, "session", fake_session)
    monkeypatch.setattr(service, "_tid", lambda: 7)
    monkeypatch.setattr(guard, "graduation_college_scope_ids", lambda _db, _user: {101})

    items, total = guard.graduation_list_batches(
        {"currentRoleCode": "COLLEGE_ADMIN"},
        page=1,
        page_size=1,
    )

    assert total == 1
    assert items == [
        {
            "batchId": "1",
            "batchName": "college-visible-oldest",
            "gradeYear": "2026",
            "majorId": None,
            "status": "OPEN",
            "total": 1,
            "passed": 0,
            "abnormal": 1,
            "concluded": 0,
            "archived": 0,
        }
    ]

    assert db.count_query is not None
    assert db.page_query is not None
    assert db.aggregate_query is not None

    count_sql = _sql(db.count_query)
    page_sql = _sql(db.page_query)
    aggregate_sql = _sql(db.aggregate_query)

    # The count and page statements must both carry the college-filtered visible-batch
    # subquery. Pagination is therefore applied to the scoped relation, never to a
    # tenant-wide page that would later be filtered in memory.
    for statement_sql in (count_sql, page_sql):
        assert "college_id" in statement_sql
        assert "select" in statement_sql
    assert "limit" in page_sql
    assert "offset" in page_sql

    # Per-page counters must use the same college boundary as the batch projection.
    assert "college_id" in aggregate_sql
    assert "batch_id" in aggregate_sql


def test_empty_college_scope_fails_closed_without_tenant_queries(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as service

    db = _NoQueryDb()

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(service, "session", fake_session)
    monkeypatch.setattr(
        service,
        "_tid",
        lambda: (_ for _ in ()).throw(AssertionError("tenant id lookup must not run for empty scope")),
    )
    monkeypatch.setattr(guard, "graduation_college_scope_ids", lambda _db, _user: set())

    items, total = guard.graduation_list_batches(
        {"currentRoleCode": "COLLEGE_ADMIN"},
        page=1,
        page_size=20,
    )

    assert items == []
    assert total == 0
