from pathlib import Path


def test_dorm_transfer_list_scope_keeps_counselor_student_scope_and_dorm_manager_building_scope():
    source = (Path(__file__).resolve().parents[1] / "app/services/affairs_dorm_transfer_scope_guard.py").read_text(
        encoding="utf-8"
    )

    assert 'context.scope_type in ("TENANT_ALL", "DORM_BUILDING")' in source
    assert 'context.scope_type not in ("CLASS", "COLLEGE")' in source
    assert "allowed_classes = context.allowed_class_ids(db)" in source
    assert "StudentProfile.class_id.in_(list(allowed_classes))" in source
    assert "project_transfer_items(out, user)" in source
    assert "return [], 0" in source


def test_dorm_transfer_projection_keeps_readable_beds_and_assignee_bound_actions():
    source = (Path(__file__).resolve().parents[1] / "app/services/affairs_dorm_projection_service.py").read_text(
        encoding="utf-8"
    )

    assert '"fromBedLabel": _label(from_bed, from_room, from_building)' in source
    assert '"toBedLabel": _label(to_bed, to_room, to_building)' in source
    assert 'UnifiedTodo.source_biz_type == "DORM_TRANSFER"' in source
    assert 'UnifiedTodo.status == "PENDING"' in source
    assert 'node == "COUNSELOR_REVIEW" and context.scope_type == "CLASS"' in source
    assert 'node == "DORM_MANAGER_REVIEW" and context.scope_type == "DORM_BUILDING"' in source
    assert 'can_review = assigned_to_current' in source
    assert '"allowedActions": ["APPROVE", "REJECT"] if can_review else []' in source


def test_dorm_transfer_approval_guard_remains_assignee_bound():
    source = (Path(__file__).resolve().parents[1] / "app/services/affairs_dorm_node_guard.py").read_text(
        encoding="utf-8"
    )

    assert 'node == "COUNSELOR_REVIEW"' in source
    assert 'context.scope_type != "CLASS"' in source
    assert "_require_pending_assignee(db, transfer.id, user, dorm.TODO_TRANSFER)" in source
    assert 'node == "DORM_MANAGER_REVIEW"' in source
    assert 'context.scope_type != "DORM_BUILDING"' in source


def test_counselor_dorm_transfer_permissions_are_minimal_and_explicit():
    source = (Path(__file__).resolve().parents[1] / "app/core/permissions.py").read_text(encoding="utf-8")
    counselor = source.split('"COUNSELOR": {', 1)[1].split('\n    },', 1)[0]

    assert '"studentAffairs.dorm.view"' in counselor
    assert '"studentAffairs.dorm.transfer.create"' in counselor
    assert '"studentAffairs.dorm.transfer.approve"' in counselor
    assert '"studentAffairs.dorm.*"' not in counselor
    assert '"studentAffairs.dorm.allocation.manage"' not in counselor
    assert '"studentAffairs.dorm.building.manage"' not in counselor
