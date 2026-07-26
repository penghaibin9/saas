"""Regression locks for teacher mini-program internship permission routing."""
import pytest

from app.core.exceptions import AppException
from app.core.mobile_internship_permission_gate import (
    _reject_legacy_teacher_write,
    resolve_teacher_internship_permission,
)
from app.api.v1.mobile_internship_context import _choose_default_batch


@pytest.mark.parametrize(("method", "path", "expected"), [
    ("GET", "/api/v1/mobile/teacher/internship", "internship.dashboard.view"),
    ("POST", "/api/v1/mobile/teacher/internship/weekly/12/review", "internship.report.review"),
    ("POST", "/api/v1/mobile/teacher/internship/makeups/12/review", "internship.makeup.review"),
    ("POST", "/api/v1/mobile/teacher/internship/leaves/12/review", "internship.leave.review"),
    ("POST", "/api/v1/mobile/teacher/internship/risks/12/close", "internship.risk.handle"),
    ("POST", "/api/v1/mobile/teacher/internship/guidance", "internship.guidance.manage"),
    ("POST", "/api/v1/mobile/teacher/internship/student-evals/12/advisor-comment", "internship.eval.advisor.manage"),
    ("POST", "/api/v1/mobile/teacher/internship/context/enterprise-evals", "internship.eval.enterprise.manage"),
    ("POST", "/api/v1/mobile/teacher/internship/context/enterprise-evals/12/review", "internship.eval.enterprise.review"),
    ("POST", "/api/v1/mobile/teacher/internship/insurances/12/verify", "internship.insurance.verify"),
    ("POST", "/api/v1/mobile/teacher/internship/change-requests/12/review", "internship.change.review"),
    ("POST", "/api/v1/mobile/teacher/internship/scores/compute", "internship.score.manage"),
    ("GET", "/api/v1/mobile/teacher/internship/agreements/pending-school", "internship.agreement.view"),
    ("GET", "/api/v1/mobile/teacher/internship/context/process-reports", "internship.report.view"),
    ("GET", "/api/v1/mobile/teacher/internship/context/process-reports/12", "internship.report.view"),
    ("POST", "/api/v1/mobile/teacher/internship/context/process-reports/12/review", "internship.report.review"),
    ("GET", "/api/v1/mobile/teacher/internship/context/plan-tasks", "internship.task.view"),
    ("POST", "/api/v1/mobile/teacher/internship/context/plan-tasks/12/review", "internship.task.review"),
    ("GET", "/api/v1/mobile/teacher/internship/context/applications", "internship.application.view"),
    ("POST", "/api/v1/mobile/teacher/internship/context/applications/12/review", "internship.application.review"),
])
def test_route_permission_mapping(method, path, expected):
    assert resolve_teacher_internship_permission(method, path) == expected


def test_non_internship_mobile_route_is_ignored():
    assert resolve_teacher_internship_permission(
        "GET", "/api/v1/mobile/orientation/batch-status") is None


@pytest.mark.parametrize("path", [
    "/api/v1/mobile/teacher/internship/scores/12/publish",
    "/api/v1/mobile/teacher/internship/agreements/12/school-confirm",
    "/api/v1/mobile/teacher/internship/new-write-endpoint",
])
def test_unregistered_teacher_internship_route_fails_closed(path):
    with pytest.raises(AppException) as exc:
        resolve_teacher_internship_permission("POST", path)
    assert exc.value.code == "NO_PERMISSION"


@pytest.mark.parametrize("path", [
    "/api/v1/mobile/teacher/internship/process-reports/12/review",
    "/api/v1/mobile/teacher/internship/plan-tasks/12/review",
    "/api/v1/mobile/teacher/internship/applications/12/review",
])
def test_legacy_unversioned_teacher_review_is_rejected(path):
    with pytest.raises(AppException) as exc:
        _reject_legacy_teacher_write("POST", path)
    assert exc.value.code == "DATA_CONFLICT"


def test_running_batch_is_preferred():
    items = [
        {"id": "9", "status": "CLOSED"},
        {"id": "8", "status": "RUNNING"},
    ]
    assert _choose_default_batch(items) == "8"


def test_latest_non_voided_batch_is_fallback():
    items = [
        {"id": "9", "status": "CLOSED"},
        {"id": "8", "status": "VOIDED"},
    ]
    assert _choose_default_batch(items) == "9"
