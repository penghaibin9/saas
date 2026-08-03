from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_position_services_have_no_active_change_bypass():
    source = _read(
        "backend/app/modules/internship/services/internship_student_service.py"
    )
    assert "allow_active_change" not in source
    assert "def assign_position_in_tx" in source
    assert "def unassign_position_in_tx" in source
    assert "在岗或考核中的学生禁止直接换岗/退岗" in source


def test_complaint_scope_never_guesses_latest_record():
    source = _read(
        "backend/app/modules/internship/services/internship_complaint_service.py"
    )
    block = source[source.index("def _complaint_in_scope"):source.index("def list_complaints")]
    assert "c.internship_id" in block
    assert "c.batch_id" in block
    assert "order_by(InternshipRecord.id.desc())" not in block


def test_confidential_complaint_details_are_permission_gated():
    source = _read(
        "backend/app/modules/internship/services/internship_complaint_service.py"
    )
    block = source[source.index("def _row"):source.index("def _assert_complaint_writable")]
    assert "internship.complaint.sensitive" in block
    assert "hide_business_detail" in block
    assert '"contentMasked"' in block
    assert '"evidenceMasked"' in block
    assert "complaint_contact_decrypt_failed" in block
