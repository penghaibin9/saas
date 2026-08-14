"""PR #101 production audit: graduation stats remain truth-preserving and scale-safe."""
from __future__ import annotations

import inspect

from app.modules.academic_affairs.services import academic_affairs_graduation_stats_scale_guard as guard
from app.modules.academic_affairs.services import academic_affairs_stats_service as legacy


def test_graduation_stats_scale_guard_is_installed_at_package_import():
    assert legacy.graduation_stats is guard.graduation_stats
    assert legacy.graduation_abnormal is guard.graduation_abnormal
    assert getattr(legacy.graduation_stats, "_graduation_stats_scale_guard", False) is True
    assert getattr(legacy.graduation_abnormal, "_graduation_stats_scale_guard", False) is True


def test_fail_items_preserve_three_state_truth_and_ignore_bad_legacy_json():
    payload = (
        '[{"item":"CREDIT","result":"FAIL"},'
        '{"item":"INTERNSHIP","result":"PASS"},'
        '{"item":"THESIS","result":"UNKNOWN"}]'
    )
    assert guard._fail_items(payload) == ["CREDIT"]
    assert guard._fail_items("not-json") == []
    assert guard._fail_items('{"item":"CREDIT","result":"FAIL"}') == []


def test_graduation_stats_aggregate_in_sql_without_changing_pass_truth():
    source = inspect.getsource(guard.graduation_stats)
    assert "func.count(AaGraduationAuditResult.id)" in source
    assert 'AaGraduationAuditResult.overall == "SYSTEM_PASSED"' in source
    assert 'AaGraduationAuditResult.conclusion == "GRADUATED"' in source
    assert ".execution_options(yield_per=500)" in source
    assert "db.scalars(q).all()" not in source


def test_graduation_abnormal_default_is_sql_paged_and_item_filter_is_streamed():
    source = inspect.getsource(guard.graduation_abnormal)
    assert "select(func.count()).select_from(q.subquery())" in source
    assert ".offset((page_no - 1) * size)" in source
    assert ".limit(size)" in source
    assert ".execution_options(yield_per=500)" in source
    assert 'abnormal_only=True' in source
    assert 'AaGraduationAuditResult.overall == "SYSTEM_ABNORMAL"' in inspect.getsource(guard._scope_conditions)


def test_graduation_stat_student_number_is_masked():
    assert guard._mask_student_no("2026123456") == "20******56"
    assert guard._mask_student_no("1234") == "****"
