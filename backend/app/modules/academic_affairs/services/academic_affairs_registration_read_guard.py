"""PR #101 registration read-side production hardening.

Keep the existing registration facts and write services untouched while making the
high-frequency eligibility/exception/deferral ledgers SQL-paged and fail-closed at the
original data-scope granularity.
"""
from __future__ import annotations

import importlib

from sqlalchemy import and_, func, or_, select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException

_MAX_PAGE_SIZE = 200


def _page_values(page, page_size, *, default=20) -> tuple[int, int]:
    try:
        page_no = max(1, int(page or 1))
        size = int(page_size if page_size is not None else default)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page/pageSize 必须为整数") from None
    if size < 1 or size > _MAX_PAGE_SIZE:
        raise AppException("VALIDATION_ERROR", f"pageSize 必须在 1-{_MAX_PAGE_SIZE} 之间")
    return page_no, size


def _scope_condition(ctx, db, StudentProfile):
    """Preserve exact STUDENT/SELF scope; never widen a named student to their whole class."""
    scope_type = str(getattr(ctx, "scope_type", "") or "").upper()
    if scope_type == "TENANT_ALL":
        return None
    if scope_type == "STUDENT":
        ids = {
            int(value)
            for value in (getattr(ctx, "student_ids", set()) | getattr(ctx, "psychology_student_ids", set()))
            if value is not None
        }
        return StudentProfile.id.in_(sorted(ids)) if ids else StudentProfile.id == -1
    if scope_type == "SELF":
        sid = getattr(ctx, "self_student_id", None)
        return StudentProfile.id == int(sid) if sid else StudentProfile.id == -1
    allowed = ctx.allowed_class_ids(db)
    if allowed is None:
        return StudentProfile.id == -1
    return StudentProfile.class_id.in_(sorted(allowed)) if allowed else StudentProfile.id == -1


def list_registration_eligibility(batch_id, user, status=None, keyword=None, page=1, page_size=20):
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    from app.models import AaRegistration, AaRegistrationBatch, StudentProfile

    page_no, size = _page_values(page, page_size)
    with legacy.session() as db:
        ctx = build_affairs_context(user, db)
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != legacy._tid():
            raise legacy.not_found("注册批次不存在")

        join = and_(
            AaRegistration.tenant_id == legacy._tid(),
            AaRegistration.batch_id == batch.id,
            AaRegistration.student_id == StudentProfile.id,
            AaRegistration.is_deleted.is_(False),
        )
        conditions = [
            StudentProfile.tenant_id == legacy._tid(),
            StudentProfile.is_deleted.is_(False),
            StudentProfile.student_status.in_(legacy._batch_target_statuses(batch)),
            or_(AaRegistration.id.is_(None), AaRegistration.status != "REGISTERED"),
        ]
        scope_condition = _scope_condition(ctx, db, StudentProfile)
        if scope_condition is not None:
            conditions.append(scope_condition)
        term = str(keyword or "").strip()
        if term:
            conditions.append(or_(
                StudentProfile.real_name.contains(term, autoescape=True),
                StudentProfile.student_no.contains(term, autoescape=True),
            ))
        if status:
            if status == "PENDING":
                conditions.append(or_(
                    AaRegistration.id.is_(None),
                    AaRegistration.eligibility_status == "PENDING",
                ))
            else:
                conditions.append(AaRegistration.eligibility_status == status)

        base = select(StudentProfile, AaRegistration).outerjoin(AaRegistration, join).where(*conditions)
        total = int(db.scalar(
            select(func.count(StudentProfile.id))
            .select_from(StudentProfile)
            .outerjoin(AaRegistration, join)
            .where(*conditions)
        ) or 0)
        rows = db.execute(
            base.order_by(StudentProfile.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [
            {
                "studentId": str(student.id),
                "studentNo": student.student_no,
                "realName": student.real_name,
                "classId": str(student.class_id or ""),
                "registrationStatus": registration.status if registration else "PENDING_REGISTER",
                "eligibilityStatus": registration.eligibility_status if registration else "PENDING",
                "eligibilityNote": (registration.eligibility_note if registration else "") or "",
                "eligibilityCheckedAt": legacy._iso(registration.eligibility_checked_at) if registration else None,
            }
            for student, registration in rows
        ], total


def list_registration_exceptions(user, batch_id=None, status=None, page=1, page_size=20):
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    from app.models import AaRegistrationException, StudentProfile

    page_no, size = _page_values(page, page_size)
    with legacy.session() as db:
        ctx = build_affairs_context(user, db)
        join = and_(
            StudentProfile.id == AaRegistrationException.student_id,
            StudentProfile.tenant_id == AaRegistrationException.tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
        conditions = [
            AaRegistrationException.tenant_id == legacy._tid(),
            AaRegistrationException.is_deleted.is_(False),
        ]
        if batch_id:
            conditions.append(AaRegistrationException.batch_id == int(batch_id))
        if status:
            conditions.append(AaRegistrationException.status == status)
        scope_condition = _scope_condition(ctx, db, StudentProfile)
        if scope_condition is not None:
            conditions.append(scope_condition)

        total = int(db.scalar(
            select(func.count(AaRegistrationException.id))
            .select_from(AaRegistrationException)
            .join(StudentProfile, join)
            .where(*conditions)
        ) or 0)
        rows = db.execute(
            select(AaRegistrationException, StudentProfile)
            .join(StudentProfile, join)
            .where(*conditions)
            .order_by(AaRegistrationException.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        out = []
        for item, student in rows:
            row = legacy._exception_row(item)
            row["realName"] = student.real_name or ""
            row["studentNo"] = student.student_no or ""
            out.append(row)
        return out, total


def list_registration_deferrals(user, batch_id=None, status=None, page=1, page_size=20):
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    from app.models import AaRegistrationDeferral, StudentProfile

    page_no, size = _page_values(page, page_size)
    with legacy.session() as db:
        ctx = build_affairs_context(user, db)
        join = and_(
            StudentProfile.id == AaRegistrationDeferral.student_id,
            StudentProfile.tenant_id == AaRegistrationDeferral.tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
        conditions = [
            AaRegistrationDeferral.tenant_id == legacy._tid(),
            AaRegistrationDeferral.is_deleted.is_(False),
        ]
        if batch_id:
            conditions.append(AaRegistrationDeferral.batch_id == int(batch_id))
        if status:
            conditions.append(AaRegistrationDeferral.status == status)
        scope_condition = _scope_condition(ctx, db, StudentProfile)
        if scope_condition is not None:
            conditions.append(scope_condition)

        total = int(db.scalar(
            select(func.count(AaRegistrationDeferral.id))
            .select_from(AaRegistrationDeferral)
            .join(StudentProfile, join)
            .where(*conditions)
        ) or 0)
        rows = db.execute(
            select(AaRegistrationDeferral, StudentProfile)
            .join(StudentProfile, join)
            .where(*conditions)
            .order_by(AaRegistrationDeferral.id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        out = []
        for item, student in rows:
            row = legacy._deferral_row(item)
            row["realName"] = student.real_name or ""
            row["studentNo"] = student.student_no or ""
            out.append(row)
        return out, total


def install() -> None:
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    public = importlib.import_module(".academic_affairs_dashboard_scope_facade", package=__package__)
    bindings = {
        "list_registration_eligibility": list_registration_eligibility,
        "list_registration_exceptions": list_registration_exceptions,
        "list_registration_deferrals": list_registration_deferrals,
    }
    for name, func in bindings.items():
        setattr(legacy, name, func)
        setattr(public, name, func)
