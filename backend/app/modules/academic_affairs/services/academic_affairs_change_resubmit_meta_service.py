"""Student-owned read model for returned AA-003 status-change resubmission.

The normal student status summary remains compact.  RETURNED rows additionally need the
exact optimistic-lock version and editable application reason so the real Student Mini
button can send the version that was actually rendered.  This module installs a narrow
read-side projection guard on the canonical mobile public service; it never owns the
status-change write chain.
"""
from __future__ import annotations

from functools import wraps

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.services.db_service import _tid, session
from app.services.mobile_student_service import _require_student, resolve_student

from . import mobile_academic_affairs_public_service as public


_ORIGINAL_STATUS_MY = getattr(public, "_aa003_original_status_my", public.status_my)


def get_my(user, change_id) -> dict:
    try:
        cid = int(change_id)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "changeId 非法") from exc

    from app.models import AaStatusChange

    with session() as db:
        student = resolve_student(db, _require_student(user))
        if not student:
            raise no_permission("尚未建立你的学生档案")
        row = db.scalars(select(AaStatusChange).where(
            AaStatusChange.id == cid,
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("异动单不存在")
        if int(row.student_id) != int(student.id):
            raise no_permission("该异动不属于当前学生本人")
        if str(row.status or "").upper() != "RETURNED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已退回的异动可修改重交", http_status=409)
        return {
            "changeId": str(row.id),
            "changeType": row.change_type,
            "reason": row.reason or "",
            "status": row.status,
            "currentNode": row.current_node or "",
            "version": int(row.version or 0),
            "decisionVersion": int(row.decision_version or 0),
            "toMajorId": str(row.to_major_id or ""),
            "toClassId": str(row.to_class_id or ""),
        }


@wraps(_ORIGINAL_STATUS_MY)
def status_my_with_resubmit_meta(user) -> dict:
    """Add edit metadata only to the owning student's RETURNED summary rows."""
    result = _ORIGINAL_STATUS_MY(user)
    changes = list((result or {}).get("changes") or [])
    returned_ids = []
    for item in changes:
        if str(item.get("status") or "").upper() == "RETURNED":
            try:
                returned_ids.append(int(item.get("changeId")))
            except (TypeError, ValueError):
                continue
    if not returned_ids:
        return result

    from app.models import AaStatusChange

    with session() as db:
        rows = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(),
            AaStatusChange.id.in_(returned_ids),
            AaStatusChange.status == "RETURNED",
            AaStatusChange.is_deleted.is_(False),
        )).all()
        by_id = {int(row.id): row for row in rows}

    for item in changes:
        try:
            row = by_id.get(int(item.get("changeId")))
        except (TypeError, ValueError):
            row = None
        if row is None:
            continue
        item["reason"] = row.reason or ""
        item["version"] = int(row.version or 0)
        item["decisionVersion"] = int(row.decision_version or 0)
        item["currentNode"] = row.current_node or ""
    result["changes"] = changes
    return result


status_my_with_resubmit_meta._aa003_resubmit_projection = True


def install() -> None:
    """Idempotently install the returned-card projection on the canonical mobile owner."""
    if not hasattr(public, "_aa003_original_status_my"):
        public._aa003_original_status_my = _ORIGINAL_STATUS_MY
    if not getattr(public.status_my, "_aa003_resubmit_projection", False):
        public.status_my = status_my_with_resubmit_meta


install()
