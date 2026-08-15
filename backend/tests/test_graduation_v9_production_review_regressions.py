"""PR #105 first production-review regression locks.

These contracts close school-scale payload/materialization debt and ensure the
StudentEval submit transition is serialized in the same database transaction.
"""
from __future__ import annotations

import inspect

from app.modules.graduation.services import graduation_guidance_stats_read_service as guidance_stats
from app.modules.graduation.services import graduation_student_eval_service as student_eval


def test_guidance_stats_keeps_exact_count_but_bounds_response_preview():
    source = inspect.getsource(guidance_stats.guidance_stats)
    assert "select(func.count()).select_from(insufficient_query.subquery())" in source
    assert ".limit(INSUFFICIENT_PREVIEW_LIMIT)" in source
    assert '"insufficientCount": insufficient_count' in source
    assert '"insufficientHasMore": insufficient_count > len(insufficient)' in source
    assert guidance_stats.INSUFFICIENT_PREVIEW_LIMIT == 200
    assert "[:50]" not in source


def test_student_eval_list_keeps_batch_and_datascope_in_sql():
    source = inspect.getsource(student_eval.list_evals)
    assert "student_scope_select" in source
    assert "batch_id=expected_batch" in source
    assert "GraduationStudent.id.in_(scope_select)" in source
    assert "accessible_student_ids" not in source


def test_student_eval_submit_transition_is_row_locked():
    source = inspect.getsource(student_eval.submit_eval)
    assert ".with_for_update()" in source
    assert "GraduationStudentEval.tenant_id == _tid()" in source
    assert "GraduationStudentEval.is_deleted.is_(False)" in source
    assert "tenant_get(db, GraduationStudentEval" not in source
