"""Yiyang C08/SM17 procurement contract: student feedback fields and two-level routing."""
from app.api.v1.mobile_internship_student import router as student_router
from app.models.internship import InternshipComplaint
from app.modules.internship.services import internship_student_feedback_service as feedback


def _routes():
    return {
        (route.path, method)
        for route in student_router.routes
        for method in (getattr(route, "methods", set()) or set())
    }


def test_sm17_feedback_fields_match_procurement_contract():
    table = InternshipComplaint.__table__
    for name in ("title", "feedback_level", "content", "image_file_ids"):
        assert name in table.c
    assert feedback.FEEDBACK_LEVELS == {
        "COLLEGE": "学院级",
        "DEPARTMENT": "系部级",
    }
    assert feedback._MAX_IMAGES == 9


def test_sm17_student_routes_cover_create_read_and_early_withdraw():
    methods = _routes()
    assert ("/mobile/internship/context/feedback", "GET") in methods
    assert ("/mobile/internship/context/feedback", "POST") in methods
    assert ("/mobile/internship/context/feedback/{feedback_id}/withdraw", "POST") in methods
