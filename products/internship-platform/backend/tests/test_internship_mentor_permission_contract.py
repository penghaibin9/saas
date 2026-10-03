"""Permission contract required by the internship mentor approval workspace."""

from app.core.permissions import ROLE_PERMISSIONS, has_permission


def _mentor_user() -> dict:
    return {
        "userId": "900000000000000001",
        "tenantId": "1000000000000000007",
        "userType": "STAFF",
        "currentRoleCode": "INTERN_MENTOR",
    }


def test_internship_mentor_can_read_batch_context_for_leave_review():
    user = _mentor_user()
    assert has_permission(user, "internship.batch.view")
    assert has_permission(user, "internship.leave.view")
    assert has_permission(user, "internship.leave.review")


def test_internship_mentor_cannot_manage_or_export_batches():
    granted = ROLE_PERMISSIONS["INTERN_MENTOR"]
    assert "internship.batch.manage" not in granted
    assert "internship.batch.export" not in granted
    assert not has_permission(_mentor_user(), "internship.batch.manage")
    assert not has_permission(_mentor_user(), "internship.batch.export")
