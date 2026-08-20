"""D-W0 college-review action contract.

Invalid review actions must fail closed before a DB transaction is opened. Otherwise a
free-form API action can accidentally fall through to the REJECT branch and mutate the
student's graduation workflow state.
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as service


@pytest.mark.parametrize("action", ["", "FOO", "APPROVE_NOW", "DELETE"])
def test_invalid_college_review_action_fails_before_db(monkeypatch, action):
    def _unexpected_session():
        raise AssertionError("invalid review action must be rejected before opening a DB session")

    monkeypatch.setattr(service.graduation_service, "session", _unexpected_session)

    with pytest.raises(AppException) as exc_info:
        service.college_review(
            1,
            {"currentRoleCode": "", "userType": "PLATFORM_SUPER_ADMIN"},
            action,
            "这是合法长度的退回原因",
        )

    assert exc_info.value.code == "BAD_REQUEST"
    assert exc_info.value.http_status == 400
    assert "APPROVE/REJECT" in exc_info.value.message
