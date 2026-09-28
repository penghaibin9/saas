"""Yiyang C08 ordinary-clause contracts: SM14 intelligent support + SM16 exemption."""
from app.api.v1.mobile_internship_student import router as student_router
from app.models.internship import InternshipSupportSession
from app.models.internship_match import InternshipApplication
from app.modules.internship.services import internship_application_service as applications
from app.modules.internship.services import internship_student_support_service as support


def _routes():
    return {
        (route.path, method)
        for route in student_router.routes
        for method in (getattr(route, "methods", set()) or set())
    }


def test_sm14_three_unresolved_handoff_is_explicit_contract():
    assert support.TRANSFER_AFTER_UNRESOLVED == 3
    assert support._faq_answer("请假要什么材料")[0] == "LEAVE"
    assert support._faq_answer("免实习怎么申请")[0] == "EXEMPTION"
    table = InternshipSupportSession.__table__
    for name in (
        "internship_id", "batch_id", "student_id", "status", "unresolved_count",
        "context_json", "transferred_risk_id", "transferred_at",
    ):
        assert name in table.c


def test_sm14_student_routes_cover_ask_feedback_and_handoff_state():
    methods = _routes()
    assert ("/mobile/internship/context/support", "GET") in methods
    assert ("/mobile/internship/context/support/ask", "POST") in methods
    assert ("/mobile/internship/context/support/{session_id}/solved", "POST") in methods
    assert ("/mobile/internship/context/support/{session_id}/unresolved", "POST") in methods


def test_sm16_reuses_formal_application_state_machine_with_evidence_fields():
    assert applications.TYPE_LABEL["EXEMPTION"] == "免实习申请"
    table = InternshipApplication.__table__
    for name in (
        "application_type", "status", "evidence_file_id",
        "exemption_type", "exemption_reason", "exemption_destination",
    ):
        assert name in table.c
