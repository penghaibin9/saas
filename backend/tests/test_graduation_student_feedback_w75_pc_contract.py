from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_w75_student_feedback_is_read_only_projection_of_append_only_evidence():
    service = text("backend/app/modules/graduation/services/graduation_student_feedback_service.py")
    route = text("backend/app/api/v1/student_portal_graduation_guard.py")

    assert "t_gd_review_feedback" in service
    assert "visible_to_student=1" in service
    assert "resolve_current_gd_student" in service
    assert "student_feedback_timeline" in service
    assert "FileVersion" in service and "FileObject" in service
    assert "evidenceLocked" in service and "source_sha256" in service
    assert "@router.get(\"/review-feedback\"" in route
    assert "student_feedback_svc.student_feedback_timeline(_student(user))" in route
    for forbidden in ("INSERT INTO t_gd_review_feedback", "UPDATE t_gd_review_feedback", "DELETE FROM t_gd_review_feedback"):
        assert forbidden not in service


def test_w75_derives_resubmit_closure_from_canonical_business_records():
    service = text("backend/app/modules/graduation/services/graduation_student_feedback_service.py")

    assert "GraduationProposal.id > int(source.id)" in service
    assert "GraduationFinal.id > int(source.id)" in service
    assert "GraduationFinal.final_type == source.final_type" in service
    assert '"resubmission"' in service
    assert '"actionRequired"' in service
    assert '"resubmitTarget"' in service
    assert '"latestActionable"' in service
    assert '"appendOnly": True' in service
    assert '"authority": "t_gd_review_feedback"' in service


def test_w75_student_pc_shows_frozen_feedback_timeline_and_uses_canonical_submit_paths():
    api = text("student-portal/src/services/graduationW75Api.js")
    view = text("student-portal/src/views/graduation/GraduationFeedbackResubmitView.vue")

    assert "'/portal/graduation/review-feedback'" in api
    assert "'/portal/graduation/proposal/submit'" in api
    assert "'/portal/graduation/final/submit'" in api
    assert "method: 'POST'" not in api.split("feedback:", 1)[1].split("proposal:", 1)[0]
    for token in (
        "评阅反馈与整改重交", "反馈时间线", "当前需要整改", "查看被评版本",
        "evidenceLocked", "fileVersionId", "SHA-256", "resubmission", "actionable",
        "expectedVersion", "PROPOSAL_REPORT", "THESIS_FINAL", "THESIS_DRAFT",
        "resubmitProposal", "resubmitFinal", "StudentDocumentViewer",
    ):
        assert token in view
    assert "graduationW75Api.submitProposal" in view
    assert "graduationW75Api.submitFinal" in view
    assert "graduationW75Api.issueTicket" in view
    assert "window.open" not in view
    assert "target=\"_blank\"" not in view


def test_w75_is_visible_on_primary_student_graduation_workbench_and_has_direct_route():
    wrapper = text("student-portal/src/views/graduation/GraduationStudentClosureView.vue")
    routes = text("student-portal/src/router/index.js")

    assert "GraduationFeedbackResubmitView" in wrapper
    assert "GraduationWorkbenchView" in wrapper
    assert "path: 'graduation/feedback'" in routes
    assert "GraduationFeedbackResubmitView.vue" in routes
    assert "path: 'graduation'" in routes
    assert "GraduationStudentClosureView.vue" in routes
