"""PR #101 production audit: canonical stats 08/09/14 stay SQL-scaled and single-owned."""
from __future__ import annotations

import inspect

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_stats_contract_facade as canonical
from app.modules.academic_affairs.services import academic_affairs_stats_public_service as public
from app.modules.academic_affairs.services import academic_affairs_stats_service as legacy


def test_canonical_stats_contract_remains_the_runtime_owner():
    assert legacy.course_selection_stats is canonical.course_selection_stats
    assert legacy.course_selection_detail is canonical.course_selection_detail
    assert legacy.exam_stats is canonical.exam_stats
    assert legacy.exam_detail is canonical.exam_detail
    assert legacy.resource_stats is canonical.resource_stats
    assert legacy.resource_detail is canonical.resource_detail
    assert public.resource_stats is canonical.resource_stats
    assert public.resource_detail is canonical.resource_detail


@pytest.mark.parametrize(
    ("page", "page_size"),
    [
        (0, 20),
        (-1, 20),
        ("bad", 20),
        (1, 0),
        (1, 201),
        (1, "bad"),
    ],
)
def test_canonical_stats_reject_invalid_paging(page, page_size):
    with pytest.raises(AppException) as exc:
        canonical._page_values(page, page_size)
    assert exc.value.code == "VALIDATION_ERROR"


def test_selection_stats_aggregate_in_sql_and_keep_id_ranges_as_subqueries():
    stats_source = inspect.getsource(canonical.course_selection_stats)
    detail_source = inspect.getsource(canonical.course_selection_detail)
    helper_source = inspect.getsource(canonical._selection_scope_queries)

    assert "func.sum(AaSelectionCourse.capacity)" in stats_source
    assert "func.sum(AaSelectionCourse.selected_count)" in stats_source
    assert "case((" in stats_source
    assert "selection_course_ids = select(AaSelectionCourse.id)" in stats_source
    assert "group_by(AaSelectionBatch.status)" in stats_source
    assert "rows = list(db.scalars(cq).all())" not in stats_source
    assert "selection_course_ids = [" not in stats_source

    assert "batch_ids = select(AaSelectionBatch.id)" in helper_source
    assert "course_ids = select(AaCourse.id)" in helper_source
    assert "db.scalars" not in helper_source
    assert ".offset((page_no - 1) * size)" in detail_source
    assert ".limit(size)" in detail_source
    assert "batch_ids = list(" not in detail_source
    assert "course_ids = set(" not in detail_source


def test_selection_batch_status_respects_college_course_scope():
    stats_source = inspect.getsource(canonical.course_selection_stats)
    assert "grouped_conditions = list(batch_conditions)" in stats_source
    assert "if colleges is not None:" in stats_source
    assert "scoped_batch_ids = select(AaSelectionCourse.batch_id)" in stats_source
    assert ").distinct()" in stats_source
    assert "AaSelectionBatch.id.in_(scoped_batch_ids)" in stats_source


def test_exam_stats_aggregate_in_sql_and_detail_uses_course_subquery():
    stats_source = inspect.getsource(canonical.exam_stats)
    detail_source = inspect.getsource(canonical.exam_detail)
    helper_source = inspect.getsource(canonical._exam_course_conditions)

    assert "func.count(AaExamCourse.id)" in stats_source
    assert "AaExamCourse.status == \"CONFIRMED\"" in stats_source
    assert "AaExamIncident.incident_type == \"ABSENT\"" in stats_source
    assert "course_ids = select(AaExamCourse.id)" in stats_source
    assert "courses = list(" not in stats_source
    assert "incidents = list(" not in stats_source

    assert "batch_ids = select(AaExamBatch.id)" in helper_source
    assert "db.scalars" not in helper_source
    assert "course_ids = select(AaExamCourse.id)" in detail_source
    assert ".offset((page_no - 1) * size)" in detail_source
    assert ".limit(size)" in detail_source
    assert "course_ids = list(" not in detail_source


def test_resource_stats_group_in_sql_and_detail_is_bounded():
    stats_source = inspect.getsource(canonical.resource_stats)
    detail_source = inspect.getsource(canonical.resource_detail)

    assert "group_by(AaClassroom.status)" in stats_source
    assert "func.count(AaClassroom.id)" in stats_source
    assert "rooms = list(" not in stats_source
    assert ".offset((page_no - 1) * size)" in detail_source
    assert ".limit(size)" in detail_source
