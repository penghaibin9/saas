"""Regression locks for teacher mini-program internship permission routing."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.core.mobile_internship_permission_gate import (
    _reject_legacy_teacher_write,
    resolve_teacher_internship_permission,
)
from app.api.v1.mobile_internship_context import _choose_default_batch
from app.modules.internship.services.internship_batch_context import assert_record_batch

ROOT = Path(__file__).resolve().parents[1]
TID = 1000000000000000001


def _teacher_token(role: str):
    from app.core.security import create_access_token

    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"mobile-{role}",
        "realName": role,
        "userType": "TEACHER",
        "tid": "x",
        "tenantId": str(TID),
        "activeContextId": "ctx",
        "currentRoleCode": role,
        "clientType": "MINIAPP",
    })}


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
    ("POST", "/api/v1/mobile/teacher/internship/context/makeups/12/evidence-viewed", "internship.makeup.view"),
    ("POST", "/api/v1/mobile/teacher/internship/context/leaves/12/evidence-viewed", "internship.leave.view"),
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


def test_permission_gate_is_installed_on_real_mobile_router():
    source = (ROOT / "app/api/v1/route_registration.py").read_text(encoding="utf-8")
    start = source.index("api_router.include_router(\n        mobile.router,")
    end = source.index("\n    from app.core.student_portal_module_gate", start)
    registration = source[start:end]
    assert "Depends(enforce_teacher_internship_mobile_permission)" in registration


def test_view_only_teacher_cannot_review_weekly_report_via_real_route(client, db_mode):
    response = client.post(
        "/api/v1/mobile/teacher/internship/weekly/999999/review",
        headers=_teacher_token("COUNSELOR"),
        json={"action": "APPROVE", "comment": "越权审核"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == 403001


def test_view_only_teacher_cannot_handle_attendance_via_real_route(client, db_mode):
    response = client.post(
        "/api/v1/mobile/teacher/internship/exception/999999/handle",
        headers=_teacher_token("COUNSELOR"),
        json={"action": "REASONABLE", "comment": "越权处置"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == 403001


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


def test_teacher_context_lists_are_real_paginated_contracts():
    source = (ROOT / "app/api/v1/mobile_internship_context.py").read_text(encoding="utf-8")
    assert "list_scores(1, 200" not in source
    assert "list_agreements(\n        1, 200" not in source
    assert "list_evals(1, 200" not in source
    assert "list_makeups(1, 200" not in source
    assert "list_leaves(1, 200" not in source
    assert "list_progress(1, 200" not in source
    assert "list_applications(\n        1, 200" not in source
    assert '"items": items' in source
    assert '"hasMore": int(page) * int(page_size) < int(total or 0)' in source


def test_current_batch_record_is_accepted():
    assert assert_record_batch(SimpleNamespace(batch_id=8), 8) == 8


def test_old_id_from_previous_batch_is_rejected():
    with pytest.raises(AppException) as exc:
        assert_record_batch(SimpleNamespace(batch_id=7), 8)
    assert exc.value.code == "DATA_CONFLICT"
    assert "不属于当前实习批次" in exc.value.message


def test_teacher_pages_append_next_page_on_reach_bottom():
    pages = [
        "agreement-confirm/index.vue",
        "enterprise-eval/index.vue",
        "internship-application/index.vue",
        "process-report-review/index.vue",
        "plan-task-review/index.vue",
        "student-eval/index.vue",
        "internship-score/index.vue",
    ]
    for relative in pages:
        source = (ROOT.parent / "miniapp/src/pages/teacher" / relative).read_text(encoding="utf-8")
        assert "onReachBottom()" in source, relative
        assert "hasMore" in source, relative
        assert "loadMore()" in source, relative
    approval = (ROOT.parent / "miniapp/src/pages/teacher/internship-approval/index.vue").read_text(
        encoding="utf-8"
    )
    assert "onReachBottom()" in approval


def test_student_portal_uses_context_writes_and_upload_controls():
    view = (ROOT.parent / "student-portal/src/views/internship/InternshipView.vue").read_text(
        encoding="utf-8"
    )
    assert "internshipCoreApi.saveApplication(body)" in view
    assert "internshipCoreApi.submitApplication(saved.id, {" in view
    assert "internshipCoreApi.withdrawLeave(item.id, {" in view
    assert "internshipCoreApi.withdrawMakeup(item.id, {" in view
    assert "internshipCoreApi.acknowledgePlan({" in view
    assert "internshipCoreApi.applyChange({" in view
    assert "internshipCoreApi.submitWeeklyReport({" in view
    assert "internshipCoreApi.submitReport({" in view
    assert "portalApi.internshipChangeApply(" not in view
    assert "portalApi.internshipWeeklySubmit(" not in view
    assert "portalApi.internshipReportSubmit(" not in view
    assert "...currentInternshipContext()" in view
    assert "expectedVersion: existing?.version ?? 0" in view
    assert "expectedVersion: detail.version" in view
    assert "岗位 ID" not in view
    assert "证明材料文件 ID" not in view
    assert "保单扫描件文件 ID" not in view
