"""C08/G16 contract: urgent notices survive re-login until explicit acknowledgement."""
from app.api.v1.mobile_internship_student import router as student_router
from app.models.internship import InternshipEmergencyNoticeReceipt


def test_emergency_notice_receipt_is_unique_per_student_and_notice():
    table = InternshipEmergencyNoticeReceipt.__table__
    names = {constraint.name for constraint in table.constraints if constraint.name}
    assert "uk_ix_emergency_notice_receipt" in names
    assert table.c.notice_id.nullable is False
    assert table.c.batch_id.nullable is False
    assert table.c.student_id.nullable is False
    assert table.c.acknowledged_at.nullable is False


def test_student_mobile_exposes_pending_and_explicit_ack_routes():
    methods = {
        (route.path, method)
        for route in student_router.routes
        for method in (getattr(route, "methods", set()) or set())
    }
    assert ("/mobile/internship/emergency-notices/pending", "GET") in methods
    assert ("/mobile/internship/emergency-notices/{notice_id}/ack", "POST") in methods
