"""Scope-first, keyset lifecycle fact read projection for all four clients."""
from __future__ import annotations

import base64
import json
from datetime import datetime

from sqlalchemy import and_, or_, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission
from app.models import StudentAccountLink, StudentProfile
from app.modules.platform.document_lifecycle.models import StudentLifecycleFact
from app.services.message_identity import resolve_message_user_id
from app.services.teacher_student_visibility_service import compile_teacher_student_visibility

_KNOWN_SENSITIVITY = {"PUBLIC", "INTERNAL", "PERSONAL", "SENSITIVE", "HIGHLY_SENSITIVE"}


def _normalized_sensitivity(value: object) -> str:
    normalized = str(value or "").strip().upper()
    return normalized if normalized in _KNOWN_SENSITIVITY else "HIGHLY_SENSITIVE"


def _tid() -> int:
    value = int(current_tenant_id() or 0)
    if value <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return value


def _assert_student_scope(db, student_id: int, user: dict) -> StudentProfile:
    user_type = str((user or {}).get("userType") or "").upper()
    conditions = [
        StudentProfile.tenant_id == _tid(), StudentProfile.id == int(student_id),
        StudentProfile.is_deleted.is_(False),
    ]
    if user_type == "STUDENT":
        actor_id = resolve_message_user_id(user or {})
        if actor_id is None:
            raise not_found("学生不存在或不在当前数据范围内")
        conditions.append(StudentProfile.id == select(StudentAccountLink.student_id).where(
            StudentAccountLink.tenant_id == _tid(),
            StudentAccountLink.user_id == int(actor_id),
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
        ).scalar_subquery())
    else:
        conditions.append(compile_teacher_student_visibility(user or {}, StudentProfile.id))
    row = db.scalars(select(StudentProfile).where(*conditions).limit(1)).first()
    if row is None:
        raise not_found("学生不存在或不在当前数据范围内")
    return row


def _decode_cursor(value: str | None) -> tuple[datetime, int] | None:
    if not value:
        return None
    try:
        raw = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        return datetime.fromisoformat(str(raw[0])), int(raw[1])
    except Exception as exc:
        raise AppException("VALIDATION_ERROR", "cursor 格式不正确") from exc


def _encode_cursor(row: StudentLifecycleFact) -> str:
    raw = json.dumps([row.event_time.isoformat(), int(row.id)], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def lifecycle_timeline(db, *, student_id: int, user: dict, source_module: str | None = None,
                       cursor: str | None = None, page_size: int = 20) -> dict:
    student = _assert_student_scope(db, student_id, user)
    size = min(100, max(1, int(page_size or 20)))
    stmt = select(StudentLifecycleFact).where(
        StudentLifecycleFact.tenant_id == _tid(),
        StudentLifecycleFact.student_id == int(student.id),
    )
    user_type = str((user or {}).get("userType") or "").upper()
    can_view_sensitive = False
    if user_type == "STUDENT":
        stmt = stmt.where(StudentLifecycleFact.visibility_code.in_((
            "STUDENT_SELF_ONLY", "STUDENT_SELF_AND_SCOPED_STAFF",
        )))
    else:
        staff_codes = ["STUDENT_SELF_AND_SCOPED_STAFF", "SCOPED_STAFF_ONLY"]
        can_view_sensitive = has_permission(user or {}, "systemAdmin.audit.sensitive.view") \
            or has_permission(user or {}, "*")
        if can_view_sensitive:
            staff_codes.append("RESTRICTED_STAFF_ONLY")
        stmt = stmt.where(StudentLifecycleFact.visibility_code.in_(staff_codes))
    if source_module:
        stmt = stmt.where(StudentLifecycleFact.source_module == str(source_module))
    boundary = _decode_cursor(cursor)
    if boundary:
        event_time, row_id = boundary
        stmt = stmt.where(or_(
            StudentLifecycleFact.event_time < event_time,
            and_(StudentLifecycleFact.event_time == event_time, StudentLifecycleFact.id < row_id),
        ))
    rows = list(db.scalars(stmt.order_by(
        StudentLifecycleFact.event_time.desc(), StudentLifecycleFact.id.desc(),
    ).limit(size + 1)).all())
    has_more = len(rows) > size
    page = rows[:size]
    def project(row: StudentLifecycleFact) -> dict:
        sensitivity = _normalized_sensitivity(row.sensitivity_level)
        summary_allowed = sensitivity in {"PUBLIC", "INTERNAL", "PERSONAL"} \
            or (user_type != "STUDENT" and can_view_sensitive)
        return {
            "id": str(row.id), "sourceModule": row.source_module,
            "factType": row.fact_type, "eventTime": row.event_time.isoformat(),
            "title": row.title,
            "summary": row.summary if summary_allowed else None,
            "importance": row.importance, "visibilityCode": row.visibility_code,
            "sensitivityLevel": sensitivity,
            "targetRef": row.target_ref_json, "canOpen": False,
        }
    return {
        "studentId": str(student.id),
        "studentName": student.real_name or "",
        "items": [project(row) for row in page],
        "nextCursor": _encode_cursor(page[-1]) if has_more and page else None,
        "pageSize": size,
    }
