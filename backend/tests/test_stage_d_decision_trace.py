"""Stage D deterministic DecisionTrace schema/rendering contracts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services.academic_affairs_decision_trace import (
    GRADUATION_RULE_CODES,
    SELECTION_RULE_CODES,
    build_decision_trace,
    render_zh_cn,
    validate_decision_trace,
)


def _trace(**overrides):
    payload = dict(
        domain="SELECTION",
        action="ENROLL",
        decision="DENIED",
        rule_code="PREREQUISITE_NOT_MET",
        subject={"studentId": "masked:2023****01"},
        target={"courseId": "31", "courseCode": "DB201", "courseName": "数据库"},
        failed_nodes=[{"code": "PREREQUISITE", "requiredCourseCode": "CS101"}],
        passed_nodes=[{"code": "STUDENT_STATUS"}],
        available_resolutions=[
            {"code": "VIEW_PREREQUISITES", "label": "查看先修课程要求", "route": "/academic/prerequisites"}
        ],
        evaluated_at=datetime(2026, 8, 9, 15, 30, 0),
        rule_version="selection-v1",
    )
    payload.update(overrides)
    return build_decision_trace(**payload)


def test_v1_rule_code_inventory_is_frozen():
    assert SELECTION_RULE_CODES == {
        "STUDENT_STATUS_NOT_ELIGIBLE", "BATCH_NOT_OPEN", "OUT_OF_COLLEGE_SCOPE",
        "OUT_OF_MAJOR_SCOPE", "OUT_OF_GRADE_SCOPE", "ALREADY_SELECTED",
        "COURSE_ALREADY_PASSED", "PREREQUISITE_NOT_MET", "MAX_CREDITS_EXCEEDED",
        "TIME_CONFLICT", "COURSE_FULL", "COURSE_MASTER_MISSING", "COURSE_RULE_BROKEN",
        "TERM_ARCHIVED", "SELECTION_LOCKED", "LOTTERY_PENDING",
    }
    assert GRADUATION_RULE_CODES == {
        "PROGRAM_UNRESOLVED", "TOTAL_CREDITS_INSUFFICIENT", "REQUIRED_COURSE_FAILED",
        "ELECTIVE_CREDITS_INSUFFICIENT", "PRACTICE_CREDITS_INSUFFICIENT",
        "INTERNSHIP_INCOMPLETE", "GRADUATION_DESIGN_INCOMPLETE", "DISCIPLINE_BLOCK",
        "ACADEMIC_DATA_UNKNOWN", "GRADUATION_ALREADY_FINAL",
    }


def test_trace_is_deterministic_for_the_same_business_evidence():
    first = _trace()
    second = _trace()
    assert first == second
    assert first["schemaVersion"] == "1.0"
    assert validate_decision_trace(first) is first


def test_builder_requires_explicit_time_and_rule_version_for_determinism():
    with pytest.raises(AppException):
        _trace(evaluated_at=None)
    with pytest.raises(AppException):
        _trace(rule_version=None)


def test_v1_action_and_decision_scope_is_fail_closed():
    with pytest.raises(AppException):
        _trace(action="DROP")
    with pytest.raises(AppException):
        _trace(decision="APPROVED")
    with pytest.raises(AppException):
        _trace(domain="GRADUATION", action="ENROLL", decision="DENIED", rule_code="DISCIPLINE_BLOCK")


def test_validate_recomputes_trace_id_and_rejects_tampered_business_evidence():
    trace = _trace()
    tampered = dict(trace)
    tampered["target"] = {**trace["target"], "courseCode": "MUTATED"}
    # traceId is still a syntactically valid UUID; validation must prove the evidence
    # fingerprint, not merely accept the UUID shape.
    with pytest.raises(AppException):
        validate_decision_trace(tampered)


def test_validate_rejects_unknown_fields_and_wrong_shapes():
    trace = _trace()
    extra = dict(trace)
    extra["debugSql"] = "select * from internal_table"
    with pytest.raises(AppException):
        validate_decision_trace(extra)

    wrong_shape = dict(trace)
    wrong_shape["subject"] = ["not-an-object"]
    with pytest.raises(AppException):
        validate_decision_trace(wrong_shape)


def test_renderer_uses_only_business_provided_resolution():
    trace = _trace()
    student = render_zh_cn(trace, audience="student")
    assert student["nextStep"] == "查看先修课程要求"
    assert student["ruleCode"] == "PREREQUISITE_NOT_MET"
    assert "target" not in student
    assert "traceId" not in student

    no_resolution = _trace(available_resolutions=[])
    assert render_zh_cn(no_resolution, audience="student")["nextStep"] is None


def test_teacher_rendering_keeps_support_metadata_without_changing_reason():
    trace = _trace()
    student = render_zh_cn(trace, audience="student")
    teacher = render_zh_cn(trace, audience="teacher")
    assert teacher["reason"] == student["reason"]
    assert teacher["traceId"] == trace["traceId"]
    assert teacher["target"]["courseCode"] == "DB201"
    assert teacher["ruleVersion"] == "selection-v1"


def test_invalid_domain_rule_pair_fails_closed():
    with pytest.raises(AppException):
        _trace(domain="GRADUATION", action="EVALUATE", rule_code="PREREQUISITE_NOT_MET")
    with pytest.raises(AppException):
        _trace(rule_code="NOT_A_REAL_RULE")


def test_resolution_must_be_structured_business_output():
    with pytest.raises(AppException):
        _trace(available_resolutions=[{"label": "缺 code"}])
    with pytest.raises(AppException):
        _trace(available_resolutions=["renderer should not invent this"])


def test_decision_trace_foundation_has_no_llm_dependency():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app/modules/academic_affairs/services/academic_affairs_decision_trace.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in ("openai", "anthropic", "langchain", "chatgpt", "completion.create"):
        assert forbidden not in lowered
