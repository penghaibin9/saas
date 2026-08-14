"""PR #101 production audit: workload stats/drilldown keep one term scope and SQL aggregation."""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.routers import stats_core_router
from app.modules.academic_affairs.services import academic_affairs_stats_public_service as public
from app.modules.academic_affairs.services import academic_affairs_stats_service as legacy
from app.modules.academic_affairs.services import academic_affairs_workload_stats_guard as guard


def test_workload_guard_is_installed_at_package_import():
    assert legacy.workload_stats is guard.workload_stats
    assert legacy.workload_detail is guard.workload_detail
    assert getattr(legacy.workload_stats, "_workload_term_sql_guard", False) is True
    assert getattr(legacy.workload_detail, "_workload_term_sql_guard", False) is True


def test_workload_stats_filter_tasks_by_batch_term_and_aggregate_in_sql():
    helper = inspect.getsource(guard._task_conditions)
    source = inspect.getsource(guard.workload_stats)
    assert "batch_ids = select(AaTeachingTaskBatch.id)" in helper
    assert "AaTeachingTaskBatch.term_id == int(term_id)" in helper
    assert "AaTeachingTask.batch_id.in_(batch_ids)" in helper
    assert "func.sum(AaTeachingTask.total_hours)" in source
    assert "group_by(AaTeachingTask.teacher_key)" in source
    assert "rows = db.scalars(q).all()" not in source


def test_workload_declared_hours_are_term_scoped_and_sql_grouped():
    source = inspect.getsource(guard._declared_hours_by_teacher)
    assert "term_codes = stats._term_codes(db, term_id)" in source
    assert "AaWorkloadDeclaration.term_code.in_(list(term_codes))" in source
    assert "func.sum(AaWorkloadDeclaration.hours)" in source
    assert "group_by(AaWorkloadDeclaration.teacher_key)" in source
    assert "for r in q.all()" not in source


@pytest.mark.parametrize(
    ("page", "page_size"),
    [(0, 20), (-1, 20), ("bad", 20), (1, 0), (1, 201), (1, "bad")],
)
def test_workload_detail_rejects_invalid_paging(page, page_size):
    with pytest.raises(AppException) as exc:
        guard._page_values(page, page_size)
    assert exc.value.code == "VALIDATION_ERROR"


def test_workload_detail_term_is_exposed_without_breaking_old_positionals():
    public_sig = inspect.signature(public.workload_detail)
    guard_sig = inspect.signature(guard.workload_detail)
    assert list(public_sig.parameters)[-1] == "term_id"
    assert list(guard_sig.parameters)[-1] == "term_id"

    route_source = inspect.getsource(stats_core_router.stats_workload_detail)
    assert "termId: Optional[int] = None" in route_source
    assert "stats_svc.workload_detail(user, teacherKey, collegeId, page, pageSize, termId)" in route_source
