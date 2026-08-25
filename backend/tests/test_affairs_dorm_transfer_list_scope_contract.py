from pathlib import Path


def test_dorm_transfer_list_scope_keeps_counselor_student_scope_and_dorm_manager_building_scope():
    source = (Path(__file__).resolve().parents[1] / "app/services/affairs_dorm_transfer_scope_guard.py").read_text(
        encoding="utf-8"
    )

    assert 'context.scope_type in ("TENANT_ALL", "DORM_BUILDING")' in source
    assert 'context.scope_type not in ("CLASS", "COLLEGE")' in source
    assert "allowed_classes = context.allowed_class_ids(db)" in source
    assert "StudentProfile.class_id.in_(list(allowed_classes))" in source
    assert "return [], 0" in source


def test_dorm_transfer_approval_guard_remains_assignee_bound():
    source = (Path(__file__).resolve().parents[1] / "app/services/affairs_dorm_node_guard.py").read_text(
        encoding="utf-8"
    )

    assert 'node == "COUNSELOR_REVIEW"' in source
    assert 'context.scope_type not in ("CLASS", "COLLEGE")' in source
    assert "_require_pending_assignee(db, transfer.id, user, dorm.TODO_TRANSFER)" in source
    assert 'node == "DORM_MANAGER_REVIEW"' in source
    assert 'context.scope_type != "DORM_BUILDING"' in source
