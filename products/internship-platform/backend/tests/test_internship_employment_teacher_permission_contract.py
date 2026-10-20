from app.core.permissions import has_permission
from app.services.system_role_shadow_service import expected_system_role_permissions


def _employment_teacher():
    return {"currentRoleCode": "EMPLOYMENT_TEACHER"}


def test_employment_teacher_can_resolve_archive_batch_context():
    user = _employment_teacher()
    assert has_permission(user, "internship.batch.view")
    assert has_permission(user, "internship.archive.view")
    assert has_permission(user, "internship.archive.package")
    assert has_permission(user, "internship.employment.view")
    assert "internship.employment.view" in set(expected_system_role_permissions("EMPLOYMENT_TEACHER"))


def test_employment_teacher_does_not_gain_archive_or_score_write_authority():
    user = _employment_teacher()
    assert not has_permission(user, "internship.archive.execute")
    assert not has_permission(user, "internship.archive.force")
    assert not has_permission(user, "internship.archive.revoke")
    assert not has_permission(user, "internship.score.manage")
    assert not has_permission(user, "internship.score.publish")
