from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.core.permissions import ROLE_PERMISSION_DENY, has_permission
from app.modules.internship.services.internship_consent_service import _assert_guardian_token, _hash


@pytest.mark.parametrize("code", [
    "internship.score.publish",
    "internship.agreement.schoolConfirm",
    "internship.archive.force",
    "internship.archive.revoke",
    "internship.compliance.exempt.approve",
    "internship.incident.close",
    "internship.evidence.export",
])
def test_mentor_and_college_cannot_execute_school_final_actions(code):
    assert not has_permission({"currentRoleCode": "INTERN_MENTOR"}, code)
    assert not has_permission({"currentRoleCode": "COLLEGE_ADMIN"}, code)
    assert has_permission({"currentRoleCode": "SCHOOL_ADMIN"}, code)


def test_college_keeps_normal_scoped_archive_and_review_work():
    user = {"currentRoleCode": "COLLEGE_ADMIN"}
    assert has_permission(user, "internship.archive.execute")
    assert has_permission(user, "internship.safety.manage")
    assert has_permission(user, "internship.incident.handle")
    assert ROLE_PERMISSION_DENY == {}


def _token_row(token, **changes):
    values = {
        "guardian_token_hash": _hash(token),
        "guardian_token_expires_at": datetime.utcnow() + timedelta(minutes=5),
        "guardian_token_used_at": None,
        "guardian_token_revoked_at": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_guardian_token_is_short_lived_single_use_and_revocable():
    token = "one-time-secret"
    _assert_guardian_token(_token_row(token), token)
    for row in (
        _token_row(token, guardian_token_used_at=datetime.utcnow()),
        _token_row(token, guardian_token_revoked_at=datetime.utcnow()),
        _token_row(token, guardian_token_expires_at=datetime.utcnow() - timedelta(seconds=1)),
    ):
        with pytest.raises(AppException):
            _assert_guardian_token(row, token)
    with pytest.raises(AppException):
        _assert_guardian_token(_token_row(token), "wrong-token")
