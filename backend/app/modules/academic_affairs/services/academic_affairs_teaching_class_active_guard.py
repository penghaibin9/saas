"""C15 teaching-class write boundary: archived classes are immutable.

Roster/version and formal teacher-relation commands already resolve a TeachingClass
through ``academic_affairs_teaching_class_change_service._get_class`` in their own
transaction.  This guard tightens that shared resolver in-place so an ARCHIVED class
cannot receive new roster versions or teacher topology changes. Reads remain
unchanged and no schema/registry ownership moves here.
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_affairs_teaching_class_change_service as change_service

_ORIGINAL_GET_CLASS = change_service._get_class


def _get_class(db, user, teaching_class_id: int, *, lock=False):
    row = _ORIGINAL_GET_CLASS(db, user, teaching_class_id, lock=lock)
    if str(row.status or "").upper() != "ACTIVE":
        raise AppException(
            "DATA_CONFLICT",
            "教学班已归档/失效，不允许继续修改名单或正式教师关系",
            details={"teachingClassId": str(row.id), "status": row.status},
            http_status=409,
        )
    return row


_get_class._teaching_class_active_write_guard = True


def install() -> None:
    current = getattr(change_service, "_get_class", None)
    if getattr(current, "_teaching_class_active_write_guard", False):
        return
    if not hasattr(change_service, "_active_write_guard_original_get_class"):
        change_service._active_write_guard_original_get_class = current
    change_service._get_class = _get_class
