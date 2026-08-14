"""PR #101 production audit: high-volume stats drilldowns stay SQL-paged and N+1-free."""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_stats_detail_scale_guard as guard
from app.modules.academic_affairs.services import academic_affairs_stats_service as legacy


def test_schedule_conflict_guard_is_installed_at_package_import():
    assert legacy.schedule_conflicts is guard.schedule_conflicts
    assert getattr(legacy.schedule_conflicts, "_stats_detail_sql_paging_guard", False) is True
    assert hasattr(legacy, "_stats_detail_scale_original_schedule_conflicts")


@pytest.mark.parametrize(
    ("page", "page_size"),
    [(0, 20), (-1, 20), ("bad", 20), (1, 0), (1, 201), (1, "bad")],
)
def test_schedule_conflict_guard_rejects_invalid_paging_before_db(page, page_size):
    with pytest.raises(AppException) as exc:
        guard._page_values(page, page_size)
    assert exc.value.code == "VALIDATION_ERROR"


def test_schedule_conflicts_use_sql_group_count_and_sql_page():
    source = inspect.getsource(guard.schedule_conflicts)
    assert "batch_ids = select(AaScheduleBatch.id)" in source
    assert "select(func.count()).select_from(group_query.subquery())" in source
    assert ".offset((page_no - 1) * size)" in source
    assert ".limit(size)" in source
    assert "page_rows = groups[" not in source
    assert "batch_ids = db.scalars" not in source


def test_schedule_conflict_key_matches_overview_and_class_name_is_display_only():
    source = inspect.getsource(guard.schedule_conflicts)
    group_body = source[source.index("group_query = ("):source.index("total = int(")]
    assert "func.max(AaScheduleItem.class_name).label(\"class_name\")" in group_body
    group_by_body = group_body[group_body.index(".group_by("):group_body.index(".having(")]
    assert "AaScheduleItem.class_id" in group_by_body
    assert "AaScheduleItem.weekday" in group_by_body
    assert "AaScheduleItem.slot_no" in group_by_body
    assert "AaScheduleItem.week_parity" in group_by_body
    assert "AaScheduleItem.class_name" not in group_by_body


def test_schedule_conflict_page_details_are_fetched_once_not_per_group():
    source = inspect.getsource(guard.schedule_conflicts)
    assert "detail_predicates = []" in source
    assert "detail_rows = db.scalars(" in source
    assert "details_by_key = defaultdict(list)" in source
    assert "for group in page_groups:" in source
    # The page loop only builds predicates/items; it must not execute a DB query per group.
    page_loop = source[source.index("for group in page_groups:"):source.index("detail_rows = db.scalars(")]
    assert "db.scalars" not in page_loop
