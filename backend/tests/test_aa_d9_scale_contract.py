"""D9-U 大校规模、canonical 与 fail-closed 生产合同。"""
from __future__ import annotations

import inspect


def test_d9_warning_hot_lists_remain_db_paginated():
    from app.modules.academic_affairs.services import academic_affairs_warning_service as warning

    for fn in (warning.list_warnings, warning.list_notifications):
        source = inspect.getsource(fn)
        assert "func.count" in source
        assert ".offset(" in source
        assert ".limit(" in source


def test_d9_student_evaluation_read_is_batched_not_per_task_n_plus_one():
    from app.modules.academic_affairs.services import academic_affairs_evaluation_student_read_service as read

    source = inspect.getsource(read.my_student_tasks)
    assert "select(AaEvaluationRecord.task_id)" in source
    assert "or_(*token_predicates)" in source
    assert source.count("AaEvaluationRecord.task_id") >= 2
    assert "for task, batch in rows:" not in source


def test_d9_textbook_hot_lists_are_db_paginated_and_stats_are_sql_aggregated():
    from app.modules.academic_affairs.services import academic_affairs_textbook_read_service as read

    for fn in (
        read.list_textbooks,
        read.list_review_batches,
        read.list_order_batches,
        read.list_distribution_records,
        read.list_fees,
    ):
        source = inspect.getsource(fn)
        assert "func.count" in source
        assert ".offset(" in source
        assert ".limit(" in source

    stock_source = inspect.getsource(read.textbook_stock)
    assert "func.sum" in stock_source
    assert ".group_by(" in stock_source
    stats_source = inspect.getsource(read.stats)
    assert "func.sum" in stats_source
    assert "func.count" in stats_source


def test_d9_archive_remains_immutable_and_stats_export_remains_canonical():
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_archive_immutable_guard as immutable
    from app.modules.academic_affairs.services import academic_affairs_stats_public_service as stats

    assert services.academic_affairs_archive_service.unfreeze is immutable.reject_archive_unfreeze
    export_source = inspect.getsource(stats.export_stats_xlsx)
    canonical_source = inspect.getsource(stats._canonical_export)
    assert "_canonical_export" in export_source
    assert "academic_affairs_stats_contract_facade" in canonical_source
    assert "courseSelection" in canonical_source
    assert "exam" in canonical_source
    assert "resource" in canonical_source
