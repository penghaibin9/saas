"""PR #101 roster-correction read-side production hardening.

The correction workflow, encrypted sensitive values, materials and approval command remain
owned by ``academic_affairs_service``.  This guard only replaces the high-frequency ledger
read so 20k-student tenants do not materialize every scoped student/correction before paging,
and STUDENT/SELF scope can never widen to an entire class.
"""
from __future__ import annotations

import importlib

from sqlalchemy import exists, func, select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException

_MAX_PAGE_SIZE = 200


def _page_values(page, page_size) -> tuple[int, int]:
    try:
        page_no = max(1, int(page or 1))
        size = int(page_size if page_size is not None else 20)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page/pageSize 必须为整数") from None
    if size < 1 or size > _MAX_PAGE_SIZE:
        raise AppException("VALIDATION_ERROR", f"pageSize 必须在 1-{_MAX_PAGE_SIZE} 之间")
    return page_no, size


def _scope_condition(ctx, db, AaStudentCorrection, StudentProfile, tenant_id):
    scope_type = str(getattr(ctx, "scope_type", "") or "").upper()
    if scope_type == "TENANT_ALL":
        return None
    if scope_type == "STUDENT":
        student_ids = {
            int(value)
            for value in (
                (getattr(ctx, "student_ids", set()) or set())
                | (getattr(ctx, "psychology_student_ids", set()) or set())
            )
            if value is not None
        }
        return (
            AaStudentCorrection.student_id.in_(sorted(student_ids))
            if student_ids else AaStudentCorrection.id == -1
        )
    if scope_type == "SELF":
        student_id = getattr(ctx, "self_student_id", None)
        return (
            AaStudentCorrection.student_id == int(student_id)
            if student_id else AaStudentCorrection.id == -1
        )

    allowed = ctx.allowed_class_ids(db)
    if allowed is None or not allowed:
        return AaStudentCorrection.id == -1
    return exists(
        select(StudentProfile.id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.id == AaStudentCorrection.student_id,
            StudentProfile.class_id.in_(sorted(allowed)),
        )
    )


def list_roster_corrections(
    user,
    status=None,
    student_id=None,
    field_key=None,
    page=1,
    page_size=20,
):
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    from app.core.permissions import has_permission
    from app.models import AaStudentCorrection, StudentProfile

    page_no, size = _page_values(page, page_size)
    with legacy.session() as db:
        ctx = build_affairs_context(user, db)
        conditions = [
            AaStudentCorrection.tenant_id == legacy._tid(),
            AaStudentCorrection.is_deleted.is_(False),
        ]
        if status:
            conditions.append(AaStudentCorrection.status == str(status).strip().upper())
        if field_key:
            conditions.append(AaStudentCorrection.field_key == str(field_key).strip().upper())
        if student_id:
            try:
                target_student_id = int(student_id)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "studentId 必须为有效学生 ID") from None
            conditions.append(AaStudentCorrection.student_id == target_student_id)

        scope_condition = _scope_condition(
            ctx,
            db,
            AaStudentCorrection,
            StudentProfile,
            legacy._tid(),
        )
        if scope_condition is not None:
            conditions.append(scope_condition)

        total = int(
            db.scalar(
                select(func.count(AaStudentCorrection.id)).where(*conditions)
            )
            or 0
        )
        rows = db.scalars(
            select(AaStudentCorrection)
            .where(*conditions)
            .order_by(AaStudentCorrection.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()

        profile_ids = {int(row.student_id) for row in rows if row.student_id is not None}
        profiles = {
            int(profile.id): profile
            for profile in db.scalars(
                select(StudentProfile).where(
                    StudentProfile.tenant_id == legacy._tid(),
                    StudentProfile.id.in_(sorted(profile_ids))
                    if profile_ids else StudentProfile.id == -1,
                )
            ).all()
        }
        reveal = has_permission(user, "academicAffairs.roster.viewSensitive")
        extras = legacy._correction_extras(db, rows, profiles)
        return [
            legacy._correction_row(row, profiles.get(int(row.student_id)), reveal, extras)
            for row in rows
        ], total


def install() -> None:
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    public = importlib.import_module(".academic_affairs_dashboard_scope_facade", package=__package__)
    legacy.list_roster_corrections = list_roster_corrections
    public.list_roster_corrections = list_roster_corrections
