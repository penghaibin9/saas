from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_core_service as core
from app.modules.academic_affairs.services import academic_affairs_selection_service as service
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as final


def _student():
    return SimpleNamespace(student_status="REGISTERED", college_id=1, major_id=2, class_id=3, grade="2025")


def test_w1_final_validator_rejects_broken_scope_json_before_any_db_query():
    batch = SimpleNamespace(id=7, status="OPEN", apply_scope_json="{broken")
    course = SimpleNamespace(id=9, credit=2, selected_count=0, capacity=30)
    with pytest.raises(AppException) as exc:
        service._validate_enroll(object(), batch, course, _student(), [], 2)
    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.http_status == 409
    assert "适用范围JSON损坏" in exc.value.message


def test_w1_core_rule_rejects_broken_rule_json_instead_of_defaulting():
    batch = SimpleNamespace(id=7, rule_json="{broken")
    with pytest.raises(AppException) as exc:
        core._rule(object(), batch, "maxCredits", 0)
    assert exc.value.code == "DATA_CONFLICT"
    assert exc.value.http_status == 409
    assert "规则JSON损坏" in exc.value.message


def test_w1_validator_is_pure_and_conflict_reject_is_owned_by_command_exit():
    validator = inspect.getsource(core._validate_enroll)
    assert ".commit(" not in validator
    assert "_record_conflict_reject" not in validator

    wrapper_source = inspect.getsource(final.student_enroll)
    assert "_selection_course_admission" in wrapper_source
    assert "_student_enroll_guarded" in wrapper_source
    guarded_source = inspect.getsource(final._student_enroll_guarded)
    assert guarded_source.count("_record_conflict_reject") == 1
    reject_at = guarded_source.index("_record_conflict_reject")
    assert "db.commit()" in guarded_source[reject_at:reject_at + 240]


def test_w1_preflight_source_has_no_mutation_audit_or_commit():
    source = inspect.getsource(final.student_preflight)
    forbidden = ["db.commit(", "db.add(", ".update(", "_audit(", "_record_conflict_reject"]
    for token in forbidden:
        assert token not in source, token
    assert "_evaluate_student_course(" in source

    evaluator = inspect.getsource(final._evaluate_student_course)
    for token in forbidden:
        assert token not in evaluator, token
    assert "_base._validate_enroll(" in evaluator
    assert '"decisionTrace"' in evaluator
