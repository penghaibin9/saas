from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace


def _fake_service():
    rows = [
        {"batchId": "3", "batchName": "tenant-hidden-newest", "total": 30, "systemPassed": 30, "systemAbnormal": 0, "finalized": 30},
        {"batchId": "2", "batchName": "tenant-hidden-middle", "total": 20, "systemPassed": 20, "systemAbnormal": 0, "finalized": 20},
        {"batchId": "1", "batchName": "college-visible-oldest", "total": 10, "systemPassed": 10, "systemAbnormal": 0, "finalized": 10},
    ]

    def list_batches(_user, status=None, page=1, page_size=50):
        del status
        start = (int(page) - 1) * int(page_size)
        end = start + int(page_size)
        return [dict(item) for item in rows[start:end]], len(rows)

    return SimpleNamespace(
        list_batches=list_batches,
        get_result=lambda *args, **kwargs: {"resultId": "1"},
        list_results=lambda *args, **kwargs: ([], 0),
        rosters=lambda *args, **kwargs: [],
        final=lambda *args, **kwargs: {"resultId": "1"},
    )


def test_college_scope_paginates_after_scope_filter_not_before(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard

    service = _fake_service()

    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(guard, "session", fake_session)
    monkeypatch.setattr(
        guard,
        "_resolve_scope",
        lambda _db, _user: {"scopeMode": "COLLEGE", "collegeIds": [101]},
    )
    monkeypatch.setattr(
        guard,
        "_visible_batch_ids",
        lambda _db, _college_ids, batch_ids: {1}.intersection({int(value) for value in batch_ids}),
    )
    monkeypatch.setattr(
        guard,
        "_scoped_batch_stats",
        lambda _db, _college_ids, _batch_id: {
            "total": 1,
            "systemPassed": 0,
            "systemAbnormal": 1,
            "finalized": 0,
        },
    )

    guard.install(service)
    items, total = service.list_batches({"currentRoleCode": "COLLEGE_ADMIN"}, page=1, page_size=1)

    assert total == 1
    assert [item["batchId"] for item in items] == ["1"]
    assert items[0]["total"] == 1
    assert items[0]["systemPassed"] == 0
    assert items[0]["systemAbnormal"] == 1


def test_scope_empty_still_returns_zero_without_scanning_tenant_pages(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard

    service = _fake_service()
    calls = {"list": 0}
    original = service.list_batches

    def counted(*args, **kwargs):
        calls["list"] += 1
        return original(*args, **kwargs)

    service.list_batches = counted

    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(guard, "session", fake_session)
    monkeypatch.setattr(
        guard,
        "_resolve_scope",
        lambda _db, _user: {"scopeMode": "COLLEGE", "collegeIds": []},
    )

    guard.install(service)
    items, total = service.list_batches({"currentRoleCode": "COLLEGE_ADMIN"}, page=1, page_size=20)

    assert items == []
    assert total == 0
    assert calls["list"] == 0
