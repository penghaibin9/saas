"""Stage D student graduation boundary must not leak raw evaluator internals."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services.academic_affairs_graduation_decision_trace import (
    build_graduation_decision_trace,
)
from app.modules.academic_affairs.services.mobile_academic_affairs_public_service import (
    _student_graduation_items,
)


def test_student_graduation_projection_drops_internal_evaluator_metadata():
    raw = [
        {
            "item": "CREDIT",
            "result": "FAIL",
            "owner": "AA_STAFF",
            "evidence": "已得 100.0/120.0 学分",
            "programId": "12",
            "programBindingId": "34",
            "refId": "56",
        },
        {
            "item": "STATUS",
            "result": "FAIL",
            "owner": "COLLEGE_STAFF",
            "evidence": "student_status=SUSPENDED",
            "refId": "99",
        },
        {
            "item": "INTERNSHIP",
            "result": "UNKNOWN",
            "owner": "AA_STAFF",
            "evidence": "供数查询失败：OperationalError",
            "refId": "100",
        },
    ]

    safe = _student_graduation_items(raw)
    assert safe[0] == {
        "item": "CREDIT",
        "result": "FAIL",
        "evidence": "已得 100.0/120.0 学分",
    }
    assert safe[1]["evidence"] == "当前学籍状态暂不满足毕业资格核验要求，请联系教务老师核对。"
    assert safe[2]["evidence"] == "相关业务数据暂时无法完成核验，请稍后重试或联系负责老师。"

    text = str(safe)
    for forbidden in (
        "programId", "programBindingId", "refId", "AA_STAFF", "COLLEGE_STAFF",
        "SUSPENDED", "OperationalError",
    ):
        assert forbidden not in text


def _evaluated_snapshot(**snapshot_overrides):
    snapshot = {
        "evaluatorVersion": "STAGE_C3_V1",
        "evaluatedAt": "2026-08-10T00:20:00",
    }
    snapshot.update(snapshot_overrides)
    return {
        "overall": "SYSTEM_ABNORMAL",
        "items": [{
            "item": "INTERNSHIP",
            "result": "FAIL",
            "owner": "AA_STAFF",
            "evidence": "供数查询失败：OperationalError",
            "refId": "internal-model-id",
        }],
        "inputSnapshot": snapshot,
    }


def test_student_graduation_decision_trace_drops_raw_evidence_and_owner_codes():
    trace = build_graduation_decision_trace(
        SimpleNamespace(student_no="2024012301"),
        _evaluated_snapshot(),
    )
    failed = trace["failedNodes"][0]
    assert failed == {"item": "INTERNSHIP", "result": "FAIL"}
    text = str(trace)
    for forbidden in ("OperationalError", "internal-model-id", "AA_STAFF", "refId", "evidence"):
        assert forbidden not in text


def test_graduation_trace_refuses_to_invent_missing_evaluator_identity():
    student = SimpleNamespace(student_no="2024012301")

    no_snapshot = _evaluated_snapshot()
    no_snapshot.pop("inputSnapshot")
    with pytest.raises(AppException):
        build_graduation_decision_trace(student, no_snapshot)

    missing_time = _evaluated_snapshot(evaluatedAt="")
    with pytest.raises(AppException):
        build_graduation_decision_trace(student, missing_time)

    missing_version = _evaluated_snapshot(evaluatorVersion="")
    with pytest.raises(AppException):
        build_graduation_decision_trace(student, missing_version)
