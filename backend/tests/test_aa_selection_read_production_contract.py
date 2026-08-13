"""D6 选课读侧：SQL 分页/批量加载/学院 fail-closed/唯一事实 owner 合同。"""
from __future__ import annotations

import importlib
import inspect

from app.modules.academic_affairs.routers import course_selection_router
from app.modules.academic_affairs.services import academic_affairs_selection_service as selection
from app.modules.academic_affairs.services import academic_affairs_selection_round_service as rounds


read = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_selection_read_service"
)


def test_public_selection_owner_stays_selection_final():
    assert course_selection_router.selection_svc is selection
    assert selection.__name__.endswith("academic_affairs_selection_final_service")
    for name in (
        "list_batches", "get_batch", "list_courses", "course_roster", "student_courses",
        "reselect_guide", "batch_stats", "get_conflict_report", "export_conflict_report_xlsx",
        "list_archived_batches", "archive_detail", "export_archive_xlsx",
    ):
        assert getattr(selection, name) is getattr(read, name)
    assert rounds.__name__.endswith("academic_affairs_selection_round_facade")
    assert rounds.list_rounds is read.list_rounds


def test_large_selection_lists_page_in_sql():
    for func in (read.list_batches, read.list_courses, read.course_roster):
        source = inspect.getsource(func)
        assert ".count()" in source
        assert ".offset(" in source
        assert ".limit(" in source
        assert "rows[(page" not in source
        assert "rows[(safe_page" not in source


def test_student_courses_bulk_loads_supply_without_batch_n_plus_one():
    source = inspect.getsource(read.student_courses)
    assert "AaSelectionCourse.batch_id.in_(batch_ids)" in source
    assert "by_batch" in source
    assert "db.add(" not in source
    assert ".update(" not in source


def test_college_scope_reuses_teaching_task_and_existing_affairs_context():
    source = inspect.getsource(read._scope_course_query)
    values_source = inspect.getsource(read._scope_values)
    assert "AaTeachingTask.class_id" in source
    assert "AaTeachingTaskBatch.college_id" in source
    assert "ctx.allowed_class_ids(db)" in values_source
    assert "college_ids" in values_source
    assert "no_data_scope" in values_source


def test_aggregates_filter_by_scoped_course_ids_not_only_batch_visibility():
    stats_source = inspect.getsource(read.batch_stats)
    conflict_source = inspect.getsource(read.get_conflict_report)
    archive_source = inspect.getsource(read.export_archive_xlsx)
    assert "selection_course_id.in_(course_ids)" in stats_source
    assert "_course_query(db, int(batch.id), scoped)" in conflict_source
    assert "AffairsAuditTrail.biz_id.in_(course_ids)" in conflict_source
    assert "_course_query(db, int(batch.id), scoped)" in archive_source


def test_conflict_student_drilldown_is_audited_and_linear_counted():
    source = inspect.getsource(read.get_conflict_report)
    assert "SELECTION_CONFLICT_QUERY" in source
    assert "counts[cid] += 1" in source
    assert "sum(1 for" not in source


def test_selection_read_layer_never_creates_second_selection_fact():
    source = inspect.getsource(read)
    assert "AaSelectionRecord(" not in source
    assert "TeachingRoster" in (read.__doc__ or "")
    assert "db.add(" not in source
    assert ".update(" not in source
