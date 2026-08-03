from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_student_portal_uses_authoritative_file_upload_route():
    text = _read("student-portal/src/services/internshipCoreApi.js")
    assert "/files/upload" not in text
    assert "/files?bizType=INTERNSHIP_APPLICATION_EVIDENCE" in text
    assert "/files?bizType=INTERNSHIP_INSURANCE_POLICY" in text


def test_complaint_contact_is_encrypted_and_risk_source_is_exact():
    text = _read("backend/app/modules/internship/services/internship_complaint_service.py")
    assert "encrypt_sensitive" in text
    assert "decrypt_sensitive" in text
    assert "complainant_contact_hash" in text
    assert "投诉未精确关联实习记录" in text
    assert 'source_type="COMPLAINT"' in text
    assert "order_by(InternshipRecord.id.desc())" not in text[text.index("def to_risk"):text.index("def followup")]


def test_active_students_cannot_bypass_change_workflow():
    text = _read("backend/app/modules/internship/services/internship_student_service.py")
    assert "在岗或考核中的学生禁止直接换岗/退岗" in text
    change = _read("backend/app/modules/internship/services/internship_change_service.py")
    assert change.count("allow_active_change=True") >= 2


def test_leave_risks_are_bound_to_leave_id():
    legacy = _read("backend/app/modules/internship/services/internship_leave_service.py")
    versioned = _read("backend/app/modules/internship/services/internship_student_leave_context_service.py")
    assert 'source_type="LEAVE"' in legacy
    assert "RiskRecord.source_id == lv.id" in legacy
    assert "RiskRecord.source_id == row.id" in versioned


def test_core_database_invariants_are_declared():
    model = _read("backend/app/models/internship.py")
    assert "uk_risk_source" in model
    assert "uk_internship_final_score_record" in model
    assert "uk_internship_archive_record" in model
