from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_change_approval_is_single_transaction_without_compensation():
    text = _read("backend/app/modules/internship/services/internship_change_service.py")
    block = text[text.index("def review_change"):]
    assert "_rollback_approved_change" not in text
    assert block.count("db.commit()") == 1
    assert "assign_position_in_tx" in block
    assert "unassign_position_in_tx" in block
    assert '"atomic": True' in block


def test_change_request_freezes_record_version():
    model = _read("backend/app/models/internship.py")
    assert "record_version_snapshot" in model
    legacy = _read("backend/app/modules/internship/services/internship_change_service.py")
    context = _read("backend/app/modules/internship/services/internship_student_change_context_service.py")
    assert "record_version_snapshot=int(rec.version or 0)" in legacy
    assert "record_version_snapshot=int(record.version or 0)" in context


def test_change_list_uses_database_pagination_and_scope():
    text = _read("backend/app/modules/internship/services/internship_change_service.py")
    block = text[text.index("def list_changes"):text.index("def get_change")]
    assert "apply_internship_record_scope" in block
    assert ".offset(" in block and ".limit(" in block
    assert "db.get(InternshipRecord" not in block
