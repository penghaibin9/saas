from __future__ import annotations

import pytest

from app.modules.academic_affairs.services.academic_affairs_graduation_scope_pagination import (
    collect_scoped_batch_page,
)


def _reader(rows):
    calls = []

    def read(_user, *, status=None, page=1, page_size=200):
        calls.append((status, page, page_size))
        start = (page - 1) * page_size
        return [dict(item) for item in rows[start:start + page_size]], len(rows)

    return read, calls


def test_scope_filter_happens_before_requested_page_window():
    rows = [{"batchId": str(value), "total": 999} for value in range(9, 0, -1)]
    reader, calls = _reader(rows)
    visible = {7, 4, 1}

    page1, total1 = collect_scoped_batch_page(
        user={},
        status=None,
        page=1,
        page_size=2,
        original_list_batches=reader,
        visible_ids_for_candidates=lambda ids: visible.intersection(ids),
        scoped_stats_for_batch=lambda batch_id: {"total": batch_id},
        scan_page_size=2,
    )
    page2, total2 = collect_scoped_batch_page(
        user={},
        status=None,
        page=2,
        page_size=2,
        original_list_batches=reader,
        visible_ids_for_candidates=lambda ids: visible.intersection(ids),
        scoped_stats_for_batch=lambda batch_id: {"total": batch_id},
        scan_page_size=2,
    )

    assert [row["batchId"] for row in page1] == ["7", "4"]
    assert [row["total"] for row in page1] == [7, 4]
    assert [row["batchId"] for row in page2] == ["1"]
    assert total1 == total2 == 3
    assert all(size <= 200 for _status, _page, size in calls)


def test_total_drift_mid_scan_is_fail_closed():
    calls = 0

    def reader(_user, *, status=None, page=1, page_size=200):
        nonlocal calls
        del status, page_size
        calls += 1
        return ([{"batchId": str(page)}], 3 if calls == 1 else 4)

    with pytest.raises(RuntimeError, match="total changed"):
        collect_scoped_batch_page(
            user={},
            status=None,
            page=1,
            page_size=20,
            original_list_batches=reader,
            visible_ids_for_candidates=lambda ids: set(ids),
            scoped_stats_for_batch=lambda _batch_id: {"total": 1},
            scan_page_size=1,
        )


def test_scope_resolver_cannot_escape_candidate_chunk():
    reader, _calls = _reader([{"batchId": "3"}])
    with pytest.raises(RuntimeError, match="outside the candidate chunk"):
        collect_scoped_batch_page(
            user={},
            status=None,
            page=1,
            page_size=20,
            original_list_batches=reader,
            visible_ids_for_candidates=lambda _ids: {999},
            scoped_stats_for_batch=lambda _batch_id: {"total": 1},
        )
