"""Finite whole-transaction retry helper for MySQL 1205/1213 only."""
from __future__ import annotations

from collections.abc import Callable
from sqlalchemy.exc import OperationalError

from app.core.exceptions import AppException

_RETRYABLE_MYSQL_CODES = frozenset({1205, 1213})
_MAX_TRANSACTION_ATTEMPTS = 3


def _mysql_error_code(exc: OperationalError) -> int | None:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    try:
        return int(args[0]) if args else None
    except (TypeError, ValueError):
        return None


def run_with_bounded_mysql_retry(db, operation: Callable[[], object], *, max_attempts: int = _MAX_TRANSACTION_ATTEMPTS):
    """Retry the caller's entire transaction body; never retry one SQL statement in isolation."""
    attempts = max(1, min(int(max_attempts), _MAX_TRANSACTION_ATTEMPTS))
    for attempt in range(1, attempts + 1):
        try:
            result = operation()
            db.commit()
            return result
        except OperationalError as exc:
            db.rollback()
            code = _mysql_error_code(exc)
            if code not in _RETRYABLE_MYSQL_CODES or attempt >= attempts:
                raise
        except Exception:
            db.rollback()
            raise
    raise AppException("DATA_CONFLICT", "志愿事务重试次数已耗尽", http_status=409)
