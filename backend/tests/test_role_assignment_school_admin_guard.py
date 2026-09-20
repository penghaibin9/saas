from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.services.role_assignment_p1_guard_service import _assert_not_last_school_admin


def _db_with_holders(*, links, accounts):
    db = Mock()
    db.scalars.side_effect = [Mock(all=lambda: links), Mock(all=lambda: accounts)]
    return db


def test_last_active_school_admin_cannot_be_revoked():
    db = _db_with_holders(
        links=[NS(user_id=51)],
        accounts=[NS(id=51, status="ACTIVE")],
    )

    with pytest.raises(AppException, match="最后一名"):
        _assert_not_last_school_admin(db, 1007, 51, NS(id=71, role_code="SCHOOL_ADMIN"))

    assert db.scalars.call_count == 2


def test_one_of_two_active_school_admins_can_be_revoked():
    db = _db_with_holders(
        links=[NS(user_id=51), NS(user_id=52)],
        accounts=[NS(id=51, status="ACTIVE"), NS(id=52, status="ACTIVE")],
    )

    _assert_not_last_school_admin(db, 1007, 51, NS(id=71, role_code="SCHOOL_ADMIN"))

    assert db.scalars.call_count == 2


def test_disabled_holder_does_not_count_as_a_replacement_admin():
    db = _db_with_holders(
        links=[NS(user_id=51), NS(user_id=52)],
        accounts=[NS(id=51, status="ACTIVE"), NS(id=52, status="DISABLED")],
    )

    with pytest.raises(AppException, match="最后一名"):
        _assert_not_last_school_admin(db, 1007, 51, NS(id=71, role_code="SCHOOL_ADMIN"))


def test_other_roles_do_not_run_the_school_admin_holder_query():
    db = Mock()

    _assert_not_last_school_admin(db, 1007, 51, NS(id=72, role_code="STAFF"))

    db.scalars.assert_not_called()
