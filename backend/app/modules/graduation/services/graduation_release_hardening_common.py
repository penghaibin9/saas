"""Graduation release hardening shared identity/scope primitives."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, cast, func, or_, select, String

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (
    GraduationArchiveRecord, GraduationAuditTrail, GraduationBatch, GraduationGrade,
    GraduationGradeAppeal, GraduationGuidance, GraduationGuidancePlan, GraduationMentor,
    GraduationMentorAssignment, GraduationStudent, GraduationTaskBook, GraduationTopic,
)
from app.services.db_service import _iso, _tid, session


def _ctx() -> tuple[dict, str]:
    user = get_current_user_ctx() or {}
    role = str(user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    return user, role


def _claim_ids(user: dict, singular: str, plural: str) -> set[str]:
    values: set[str] = set()
    raw = user.get(plural)
    if isinstance(raw, (list, tuple, set)):
        values.update(str(v).strip() for v in raw if str(v).strip())
    one = str(user.get(singular) or "").strip()
    if one:
        values.add(one)
    return values


def _strict_dt(value, field_name: str):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"{field_name} 不是合法日期时间") from exc


def _full_scope(role: str) -> bool:
    from app.modules.graduation.services import graduation_scope_service as scope
    return role in scope.FULL_SCOPE_ROLES


def _student_scope_select(db, tenant_id: int, *, batch_id=None):
    """SQL-native student scope for high-frequency graduation reads.

    Stable IDs only.  Missing organization / mentor identity fails closed.
    """
    from app.modules.graduation.services import graduation_scope_service as scope
    from app.modules.graduation.services import graduation_identity as identity
    from app.models import GraduationReview

    user, role = _ctx()
    q = select(GraduationStudent.id).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    )
    if batch_id not in (None, ""):
        q = q.where(GraduationStudent.batch_id == int(batch_id))
    if role in scope.FULL_SCOPE_ROLES:
        return q
    if role in scope.COLLEGE_SCOPE_ROLES:
        ids = _claim_ids(user, "collegeId", "collegeIds")
        return q.where(GraduationStudent.college_id.in_(ids or {"__NONE__"}))
    if role in scope.MAJOR_SCOPE_ROLES:
        ids = _claim_ids(user, "majorId", "majorIds")
        return q.where(GraduationStudent.major_id.in_(ids or {"__NONE__"}))
    if role in {"GD_MENTOR", "COUNSELOR"}:
        mentor = identity.current_user_mentor(db)
        return q.where(GraduationStudent.mentor_id == (int(mentor.id) if mentor else -1))
    if role == "GD_REVIEWER":
        mentor = identity.current_user_mentor(db)
        if not mentor:
            return q.where(GraduationStudent.id == -1)
        reviewer_students = select(GraduationReview.gd_student_id).where(
            GraduationReview.tenant_id == tenant_id,
            GraduationReview.reviewer_mentor_id == int(mentor.id),
            GraduationReview.is_deleted.is_(False),
        )
        return q.where(GraduationStudent.id.in_(reviewer_students))
    if role == "STUDENT":
        student_no = str(user.get("studentNo") or "").strip()
        student_id = user.get("studentId") or user.get("studentProfileId")
        if student_no:
            return q.where(GraduationStudent.student_no == student_no)
        try:
            return q.where(GraduationStudent.student_id == int(student_id))
        except (TypeError, ValueError):
            return q.where(GraduationStudent.id == -1)
    return q.where(GraduationStudent.id == -1)
