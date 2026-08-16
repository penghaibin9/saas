"""A-W4 Course confirm DB error classification contracts."""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError, OperationalError


def _service():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_confirm_service as service
    return service


class _DbError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(code, message)
        self.args = (code, message)


def test_only_aa_course_stable_unique_is_classified_as_course_conflict():
    service = _service()
    stable = IntegrityError(
        "INSERT",
        {},
        _DbError(1062, "Duplicate entry '1001-CS101-1' for key 't_aa_course.uk_aa_course'"),
    )
    primary = IntegrityError(
        "INSERT",
        {},
        _DbError(1062, "Duplicate entry '42' for key 't_aa_course.PRIMARY'"),
    )
    other_unique = IntegrityError(
        "INSERT",
        {},
        _DbError(1062, "Duplicate entry 'x' for key 'uk_other_business_key'"),
    )

    assert service._is_course_unique_conflict(stable) is True
    assert service._is_course_unique_conflict(primary) is False
    assert service._is_course_unique_conflict(other_unique) is False


def test_only_mysql_deadlock_and_lock_wait_are_retryable_business_conflicts():
    service = _service()
    deadlock = OperationalError("SELECT", {}, _DbError(1213, "Deadlock found"))
    lock_wait = OperationalError("SELECT", {}, _DbError(1205, "Lock wait timeout"))
    disconnect = OperationalError("SELECT", {}, _DbError(2006, "MySQL server has gone away"))

    assert service._is_mysql_lock_conflict(deadlock) is True
    assert service._is_mysql_lock_conflict(lock_wait) is True
    assert service._is_mysql_lock_conflict(disconnect) is False
