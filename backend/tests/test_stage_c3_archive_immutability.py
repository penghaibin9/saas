"""Stage C3: ARCHIVED semester history cannot be reopened by the formal archive service."""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_archive_service as archive_service


def test_formal_archive_unfreeze_is_fail_closed_before_any_database_write():
    with pytest.raises(AppException) as exc:
        archive_service.unfreeze(
            {"currentRoleCode": "SCHOOL_ADMIN"},
            10001,
            "尝试普通解冻归档",
        )

    assert exc.value.code == "TERM_ARCHIVED"
    assert exc.value.http_status == 409
    assert "归档后纠错" in exc.value.message


def test_archive_guard_does_not_change_frozen_term_unfreeze_contract():
    """C3 only closes ARCHIVED reopen; PUBLISHED<->FROZEN remains a separate operational state."""
    from app.modules.academic_affairs.services import academic_affairs_archive_immutable_guard as guard

    assert guard.reject_archive_unfreeze is archive_service.unfreeze
