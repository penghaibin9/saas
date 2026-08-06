from app.core.permissions import ROLE_PERMISSIONS, has_permission


def test_gd_mentor_can_read_batch_context_without_batch_write_rights():
    mentor_permissions = ROLE_PERMISSIONS["GD_MENTOR"]

    assert "graduationDesign.batch.view" in mentor_permissions
    assert has_permission(
        {"currentRoleCode": "GD_MENTOR", "userType": "TEACHER"},
        "graduationDesign.batch.view",
    )

    forbidden_batch_writes = {
        "graduationDesign.batch.create",
        "graduationDesign.batch.manage",
        "graduationDesign.batch.activate",
        "graduationDesign.batch.close",
        "graduationDesign.batch.archive",
        "graduationDesign.batch.void",
    }
    assert mentor_permissions.isdisjoint(forbidden_batch_writes)
    for permission in forbidden_batch_writes:
        assert not has_permission(
            {"currentRoleCode": "GD_MENTOR", "userType": "TEACHER"},
            permission,
        )
