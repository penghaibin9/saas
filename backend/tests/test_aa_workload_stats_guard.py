"""PR #101 production audit: workload stats/drilldown keep one term scope and SQL aggregation."""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.routers import stats_core_router
from app.modules.academic_affairs.services import academic_affairs_stats_public_service as public
from app.modules.academic_affairs.services import academic_affairs_workload_stats_guard as guard

legacy = public._legacy


def test_workload_guard_is_installed_behind_public_scope_owner():
    public_source = inspect.getsource(public.workload_stats)
    precheck_source = inspect.getsource(public._precheck)
    assert "_precheck(user, college_id)" in public_source
    assert "_resolve_scope" in precheck_source
    assert "_validate_college_param" in precheck_source
    assert public.workload_detail is guard.public_workload_detail
    assert getattr(guard.workload_stats, "_workload_term_sql_guard", False) is True
    assert getattr(guard.workload_detail, "_workload_term_sql_guard", False) is True
    assert getattr(public.workload_detail, "_workload_public_scope_guard", False) is True


def test_workload_stats_filter_tasks_by_batch_term_and_reconcile_formal_sources():
    helper = inspect.getsource(guard._task_conditions)
    source = inspect.getsource(guard.workload_stats)
    assert "batch_ids = select(AaTeachingTaskBatch.id)" in helper
    assert "AaTeachingTaskBatch.term_id == int(term_id)" in helper
    assert "AaTeachingTask.batch_id.in_(batch_ids)" in helper
    assert "select(AaTeachingTask).where(*_task_conditions(term_id, class_ids))" in source
    assert "_formal_teaching_facts(db, tasks)" in source
    assert "_formal_invigilation_facts" in source
    assert "rows = db.scalars(q).all()" not in source


def test_workload_declared_hours_are_term_scoped_and_sql_grouped():
    aggregate_source = inspect.getsource(guard._declared_facts_by_teacher)
    compat_source = inspect.getsource(guard._declared_hours_by_teacher)
    assert "term_codes = stats._term_codes(db, term_id)" in aggregate_source
    assert "AaWorkloadDeclaration.term_code.in_(list(term_codes))" in aggregate_source
    assert "func.sum(AaWorkloadDeclaration.hours)" in aggregate_source
    # 当前聚合同时保留教师总量和分类明细，因此 SQL 必须按教师+类别分组；
    # 再由 Python 汇总 approvedHours，不能退回逐行扫描。
    assert "group_by(AaWorkloadDeclaration.teacher_key, AaWorkloadDeclaration.category)" in aggregate_source
    assert "_declared_facts_by_teacher" in compat_source


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


def test_public_workload_detail_keeps_teacher_self_only_and_five_arg_compat(monkeypatch):
    monkeypatch.setattr(public, "_precheck", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        legacy,
        "workload_detail",
        lambda _user, teacher_key, _college_id, _page, _page_size: ([teacher_key], 1),
    )
    user = {
        "currentRoleCode": "ACADEMIC_TEACHER",
        "loginName": "T001",
        "userId": "u_T001",
        "activeContextId": "ctx_T001",
    }

    with pytest.raises(AppException) as exc:
        public.workload_detail(user, "T002")
    assert exc.value.http_status == 403

    items, total = public.workload_detail(user, "T001")
    assert items == ["T001"]
    assert total == 1
