"""Yiyang C08 notice contracts: SM01 / TM01 / AP06."""
from app.api.v1.mobile_internship_student import router as student_router
from app.api.v1.teacher_mobile_internship import EmergencyNoticeBody, router as teacher_router
from app.models import InternshipEmergencyNotice, InternshipEmergencyNoticeTeacherReceipt
from app.models.internship import InternshipEmergencyNoticeReceipt
from app.modules.internship.services import internship_teacher_activity_service as notice_svc


def _methods(router):
    return {
        (route.path, method)
        for route in router.routes
        for method in (getattr(route, "methods", set()) or set())
    }


def test_sm01_notice_fact_covers_procurement_fields():
    table = InternshipEmergencyNotice.__table__
    for name in (
        "notice_type", "urgency", "valid_from", "valid_until",
        "attachment_file_ids_json", "audience_scope",
        "recipient_college_ids_json", "sender_name_snapshot",
    ):
        assert name in table.c
    assert notice_svc.NOTICE_TYPES == {
        "AGREEMENT", "TRAINING", "SAFETY", "NOTICE", "OTHER"
    }
    assert notice_svc.NOTICE_URGENCY == {"NORMAL", "IMPORTANT", "URGENT"}
    assert notice_svc.NOTICE_ATTACHMENT_EXTENSIONS == {
        "rar", "zip", "doc", "docx", "pdf", "xls", "xlsx"
    }


def test_ap06_notice_body_accepts_full_admin_publish_contract():
    fields = set(EmergencyNoticeBody.model_fields)
    assert {
        "batchId", "title", "content", "noticeType", "urgency",
        "validFrom", "validUntil", "attachmentFileIds",
        "audienceScope", "recipientCollegeIds",
    } <= fields
    assert notice_svc._notice_audience({"audienceScope": "ALL"}) == ("ALL", [])
    assert notice_svc._notice_audience({
        "audienceScope": "COLLEGE",
        "recipientCollegeIds": [3, "3", 7],
    }) == ("COLLEGE", [3, 7])


def test_student_and_teacher_force_popup_have_explicit_receipts():
    student_table = InternshipEmergencyNoticeReceipt.__table__
    teacher_table = InternshipEmergencyNoticeTeacherReceipt.__table__
    assert "student_id" in student_table.c
    assert "teacher_user_id" in teacher_table.c

    student_methods = _methods(student_router)
    teacher_methods = _methods(teacher_router)
    assert ("/mobile/internship/emergency-notices/pending", "GET") in student_methods
    assert ("/mobile/internship/emergency-notices/{notice_id}/ack", "POST") in student_methods
    assert ("/internship/emergency-notices/pending", "GET") in teacher_methods
    assert ("/internship/emergency-notices/{notice_id}/ack", "POST") in teacher_methods
