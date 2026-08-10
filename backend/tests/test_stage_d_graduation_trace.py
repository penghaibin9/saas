"""Stage D graduation DecisionTrace consumes the shared evaluator result only."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.academic_affairs.services.academic_affairs_graduation_decision_trace import (
    build_graduation_decision_trace,
    build_graduation_student_explanation,
)


STUDENT = SimpleNamespace(student_no="2024012301")
AT = "2026-08-09T15:45:00"


def _evaluated(items, overall="SYSTEM_ABNORMAL"):
    return {
        "overall": overall,
        "items": items,
        "inputHash": "hash-does-not-decide",
        "inputSnapshot": {
            "evaluatorVersion": "STAGE_C3_V1",
            "evaluatedAt": AT,
        },
    }


def _item(code, result, evidence="evidence", **extra):
    return {"item": code, "result": result, "owner": "AA_STAFF", "evidence": evidence, **extra}


def test_all_pass_has_no_denial_trace():
    evaluated = _evaluated([_item("STATUS", "PASS"), _item("CREDIT", "PASS")], overall="SYSTEM_PASSED")
    trace, text = build_graduation_student_explanation(STUDENT, evaluated)
    assert trace is None
    assert text is None


@pytest.mark.parametrize(
    ("item", "extra", "rule"),
    [
        ("CREDIT", {}, "TOTAL_CREDITS_INSUFFICIENT"),
        ("COURSE_REQUIRED", {}, "REQUIRED_COURSE_FAILED"),
        ("COURSE_ELECTIVE", {}, "ELECTIVE_CREDITS_INSUFFICIENT"),
        ("PRACTICE", {}, "PRACTICE_CREDITS_INSUFFICIENT"),
        ("INTERNSHIP", {}, "INTERNSHIP_INCOMPLETE"),
        ("GRADUATION_DESIGN", {}, "GRADUATION_DESIGN_INCOMPLETE"),
        ("DISCIPLINE", {}, "DISCIPLINE_BLOCK"),
        ("CREDIT", {"programResolutionStatus": "AMBIGUOUS"}, "PROGRAM_UNRESOLVED"),
    ],
)
def test_existing_fail_item_maps_to_frozen_rule_code(item, extra, rule):
    trace = build_graduation_decision_trace(STUDENT, _evaluated([_item(item, "FAIL", **extra)]))
    assert trace["ruleCode"] == rule
    assert trace["domain"] == "GRADUATION"
    assert trace["action"] == "EVALUATE"
    assert trace["decision"] == "DENIED"
    assert trace["evaluatedAt"] == AT
    assert trace["ruleVersion"] == "STAGE_C3_V1"


def test_unknown_never_becomes_a_specific_pass_or_invented_rule():
    trace = build_graduation_decision_trace(STUDENT, _evaluated([
        _item("EMPLOYMENT", "UNKNOWN", "该域当前仅人工复核"),
    ]))
    assert trace["ruleCode"] == "ACADEMIC_DATA_UNKNOWN"
    assert trace["decision"] == "DENIED"


def test_program_unresolved_precedes_credit_result_explanation():
    trace = build_graduation_decision_trace(STUDENT, _evaluated([
        _item("CREDIT", "UNKNOWN", "培养方案存在歧义", programResolutionStatus="AMBIGUOUS"),
    ]))
    assert trace["ruleCode"] == "PROGRAM_UNRESOLVED"


def test_same_evaluator_snapshot_produces_same_trace_and_masks_student_identity():
    evaluated = _evaluated([
        _item("STATUS", "PASS"),
        _item("INTERNSHIP", "FAIL", "岗位实习正式完成事实未满足", refId="internal-should-not-leak"),
    ])
    first = build_graduation_decision_trace(STUDENT, evaluated)
    second = build_graduation_decision_trace(STUDENT, evaluated)
    assert first == second
    assert first["subject"]["studentId"].startswith("masked:")
    assert "internal-should-not-leak" not in str(first)
    assert "refId" not in str(first)


def test_student_explanation_uses_business_resolution_and_hides_trace_metadata():
    trace, text = build_graduation_student_explanation(
        STUDENT,
        _evaluated([_item("COURSE_REQUIRED", "FAIL", "仍有必修未通过")]),
    )
    assert trace["availableResolutions"][0]["code"] == "COMPLETE_REQUIRED_COURSES"
    assert text["nextStep"] == trace["availableResolutions"][0]["label"]
    assert text["ruleCode"] == "REQUIRED_COURSE_FAILED"
    assert "traceId" not in text
    assert "target" not in text
