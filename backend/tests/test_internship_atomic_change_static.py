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
    assert "record.intern_start_date = None" in block
    assert "record.status = _next_record_status(record)" in block
    assert "_void_prior_compliance(db, record, change" in block


def test_change_targets_are_canonical_and_change_enterprise_requires_a_position():
    legacy = _read("backend/app/modules/internship/services/internship_change_service.py")
    context = _read("backend/app/modules/internship/services/internship_student_change_context_service.py")
    assert 'ctype in ("CHANGE_POSITION", "CHANGE_ENTERPRISE")' in legacy
    assert 'change_type in ("CHANGE_POSITION", "CHANGE_ENTERPRISE")' in context
    assert "validate_target_position(" in legacy and "validate_target_position(" in context
    assert "target_company.name" in context and "target_position.title" in context
    assert "list_target_positions" in context


def test_unassign_clears_current_relationship_snapshot():
    text = _read("backend/app/modules/internship/services/internship_student_service.py")
    block = text[text.index("def unassign_position_in_tx"):text.index("def unassign_position(")]
    assert "record.current_placement_snapshot_id = None" in block


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
