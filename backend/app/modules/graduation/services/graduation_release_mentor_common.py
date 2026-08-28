"""Graduation mentor P0/P1/P2 scope, qualification, concurrency and export hardening."""
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

from app.modules.graduation.services.graduation_release_hardening_common import (
    _claim_ids, _ctx, _full_scope, _strict_dt, _student_scope_select,
)


def _mentor_scope_select(db):
    from app.modules.graduation.services import graduation_scope_service as scope
    user, role = _ctx()
    q = select(GraduationMentor.id).where(GraduationMentor.tenant_id == _tid(), GraduationMentor.is_deleted.is_(False))
    if role in scope.FULL_SCOPE_ROLES:
        return q
    if role in scope.COLLEGE_SCOPE_ROLES:
        ids = _claim_ids(user, "collegeId", "collegeIds")
        return q.where(GraduationMentor.college_id.in_(ids or {"__NONE__"}))
    return q.where(GraduationMentor.id == -1)


def _mentor_get_manage(db, mentor_id, *, lock=False):
    q = select(GraduationMentor).where(
        GraduationMentor.id == int(mentor_id), GraduationMentor.tenant_id == _tid(), GraduationMentor.is_deleted.is_(False),
        GraduationMentor.id.in_(_mentor_scope_select(db)),
    )
    if lock: q = q.with_for_update()
    m = db.scalars(q).first()
    if not m:
        raise no_permission("导师不存在或不在当前管理数据范围内")
    return m
