from app.core.permissions import has_permission, ROLE_PERMISSIONS


def _employment_teacher():
    return {"currentRoleCode": "INTERN_MENTOR"}


def test_standalone_normal_mentor_can_resolve_batch_and_review_employment():
    user = _employment_teacher()
    assert has_permission(user, "internship.batch.view")
    assert has_permission(user, "internship.archive.view")
    assert has_permission(user, "internship.employment.view")
    assert has_permission(user, "internship.employment.review")
    assert has_permission(user, "internship.employment.sensitive.view")
    assert "internship.employment.view" in ROLE_PERMISSIONS["INTERN_MENTOR"]


def test_employment_permission_does_not_grant_archive_publish_or_full_employment_domain():
    user = _employment_teacher()
    assert not has_permission(user, "internship.archive.execute")
    assert not has_permission(user, "internship.archive.force")
    assert not has_permission(user, "internship.archive.revoke")
    assert not has_permission(user, "internship.score.publish")
    assert not has_permission(user, "employment.*")
    assert not has_permission({"currentRoleCode":"EMPLOYMENT_TEACHER"},"internship.employment.view")

def test_counselor_employment_is_view_only():
    user={"currentRoleCode":"COUNSELOR"}
    assert has_permission(user,"internship.employment.view")
    assert not has_permission(user,"internship.employment.review")
    assert not has_permission(user,"internship.employment.sensitive.view")
