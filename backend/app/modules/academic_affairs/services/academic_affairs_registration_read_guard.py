"""PR #101 registration read-side production hardening.

Keep the existing registration facts and write services untouched while making the
high-frequency eligibility/exception/deferral/unregistered ledgers SQL-paged and
fail-closed at the original data-scope granularity.
"""
from __future__ import annotations

import importlib
from datetime import datetime

from sqlalchemy import and_, exists, func, literal, or_, select, union_all

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


def _unregistered_union(db, user, batch_id=None):
    """One SQL ledger for explicit UNREGISTERED + expired candidates awaiting scan."""
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    from app.models import (
        AaRegistration,
        AaRegistrationBatch,
        AaRegistrationDeferral,
        StudentProfile,
    )

    ctx = build_affairs_context(user, db)
    scope_condition = _scope_condition(ctx, db, StudentProfile)
    explicit_conditions = [
        AaRegistration.tenant_id == legacy._tid(),
        AaRegistration.is_deleted.is_(False),
        AaRegistration.status == "UNREGISTERED",
        AaRegistrationBatch.tenant_id == legacy._tid(),
        AaRegistrationBatch.is_deleted.is_(False),
    ]
    if batch_id:
        explicit_conditions.append(AaRegistration.batch_id == int(batch_id))
    if scope_condition is not None:
        explicit_conditions.append(scope_condition)

    explicit = (
        select(
            StudentProfile.id.label("student_id"),
            StudentProfile.student_no.label("student_no"),
            StudentProfile.real_name.label("real_name"),
            StudentProfile.class_id.label("class_id"),
            AaRegistrationBatch.id.label("batch_id"),
            AaRegistrationBatch.batch_name.label("batch_name"),
            AaRegistrationBatch.register_type.label("register_type"),
            AaRegistrationBatch.window_end.label("window_end"),
            literal("UNREGISTERED").label("kind"),
            literal(0).label("kind_rank"),
            AaRegistration.id.label("sort_id"),
        )
        .select_from(AaRegistration)
        .join(
            StudentProfile,
            and_(
                StudentProfile.id == AaRegistration.student_id,
                StudentProfile.tenant_id == AaRegistration.tenant_id,
                StudentProfile.is_deleted.is_(False),
            ),
        )
        .join(
            AaRegistrationBatch,
            and_(
                AaRegistrationBatch.id == AaRegistration.batch_id,
                AaRegistrationBatch.tenant_id == AaRegistration.tenant_id,
            ),
        )
        .where(*explicit_conditions)
    )

    now = datetime.utcnow()
    candidate_status = or_(
        and_(
            AaRegistrationBatch.register_type == "ENROLL",
            StudentProfile.student_status == "PENDING_REGISTER",
        ),
        and_(
            AaRegistrationBatch.register_type != "ENROLL",
            StudentProfile.student_status.in_(("REGISTERED", "RETAINED")),
        ),
    )
    registration_join = and_(
        AaRegistration.tenant_id == legacy._tid(),
        AaRegistration.batch_id == AaRegistrationBatch.id,
        AaRegistration.student_id == StudentProfile.id,
        AaRegistration.is_deleted.is_(False),
    )
    active_deferral = exists(
        select(AaRegistrationDeferral.id).where(
            AaRegistrationDeferral.tenant_id == legacy._tid(),
            AaRegistrationDeferral.batch_id == AaRegistrationBatch.id,
            AaRegistrationDeferral.student_id == StudentProfile.id,
            AaRegistrationDeferral.status == "APPROVED",
            AaRegistrationDeferral.is_deleted.is_(False),
            or_(
                AaRegistrationDeferral.requested_until.is_(None),
                AaRegistrationDeferral.requested_until >= now,
            ),
        )
    )
    overdue_conditions = [
        AaRegistrationBatch.tenant_id == legacy._tid(),
        AaRegistrationBatch.is_deleted.is_(False),
        AaRegistrationBatch.status == "OPEN",
        AaRegistrationBatch.window_end.isnot(None),
        AaRegistrationBatch.window_end < now,
        StudentProfile.tenant_id == legacy._tid(),
        StudentProfile.is_deleted.is_(False),
        candidate_status,
        or_(
            AaRegistration.id.is_(None),
            AaRegistration.status.is_(None),
            AaRegistration.status.notin_(("REGISTERED", "UNREGISTERED")),
        ),
        ~active_deferral,
    ]
    if batch_id:
        overdue_conditions.append(AaRegistrationBatch.id == int(batch_id))
    if scope_condition is not None:
        overdue_conditions.append(scope_condition)

    overdue = (
        select(
            StudentProfile.id.label("student_id"),
            StudentProfile.student_no.label("student_no"),
            StudentProfile.real_name.label("real_name"),
            StudentProfile.class_id.label("class_id"),
            AaRegistrationBatch.id.label("batch_id"),
            AaRegistrationBatch.batch_name.label("batch_name"),
            AaRegistrationBatch.register_type.label("register_type"),
            AaRegistrationBatch.window_end.label("window_end"),
            literal("OVERDUE_PENDING_SCAN").label("kind"),
            literal(1).label("kind_rank"),
            StudentProfile.id.label("sort_id"),
        )
        .select_from(AaRegistrationBatch)
        .join(
            StudentProfile,
            and_(
                StudentProfile.tenant_id == AaRegistrationBatch.tenant_id,
                candidate_status,
            ),
        )
        .outerjoin(AaRegistration, registration_join)
        .where(*overdue_conditions)
    )
    return union_all(explicit, overdue).subquery("aa_unregistered_ledger")


def _unregistered_dto(row, legacy) -> dict:
    return {
        "studentId": str(row.student_id),
        "studentNo": row.student_no or "",
        "realName": row.real_name or "",
        "classId": str(row.class_id or ""),
        "batchId": str(row.batch_id),
        "batchName": row.batch_name or "",
        "registerType": row.register_type or "",
        "windowEnd": legacy._iso(row.window_end),
        "kind": row.kind,
    }


def list_unregistered_students(user, batch_id=None, page=1, page_size=20):
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    page_no, size = _page_values(page, page_size)
    with legacy.session() as db:
        ledger = _unregistered_union(db, user, batch_id)
        total = int(db.scalar(select(func.count()).select_from(ledger)) or 0)
        rows = db.execute(
            select(ledger)
            .order_by(ledger.c.kind_rank.asc(), ledger.c.sort_id.desc())
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        return [_unregistered_dto(row, legacy) for row in rows], total


def export_unregistered_xlsx(user, batch_id=None, purpose="") -> bytes:
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    from app.services.xlsx_util import build_ledger_xlsx

    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    with legacy.session() as db:
        ledger = _unregistered_union(db, user, batch_id)
        rows = db.execute(
            select(ledger).order_by(ledger.c.kind_rank.asc(), ledger.c.sort_id.desc())
        ).all()
        rows_data = [_unregistered_dto(row, legacy) for row in rows]

    operator_name, _role, _uid = legacy._op()
    watermark = (
        f"导出人：{operator_name or '-'}  时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  "
        f"用途：{purpose}"
    )
    headers = ["学号", "姓名", "批次", "类型", "截止时间", "状态"]
    export_rows = [
        [
            row["studentNo"],
            row["realName"],
            row["batchName"],
            legacy._REG_TYPE_LABEL.get(row["registerType"], ""),
            row["windowEnd"] or "",
            "未注册" if row["kind"] == "UNREGISTERED" else "逾期待处理",
        ]
        for row in rows_data
    ]
    content = build_ledger_xlsx("未注册学生名单", headers, export_rows, watermark=watermark)
    with legacy.session() as db:
        legacy._audit(db, "AA_REGISTRATION", batch_id, "EXPORT_UNREGISTERED", f"用途={purpose[:100]}")
        db.commit()
    return content


def install() -> None:
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    public = importlib.import_module(".academic_affairs_dashboard_scope_facade", package=__package__)
    bindings = {
        "list_registration_eligibility": list_registration_eligibility,
        "list_registration_exceptions": list_registration_exceptions,
        "list_registration_deferrals": list_registration_deferrals,
        "list_unregistered_students": list_unregistered_students,
        "export_unregistered_xlsx": export_unregistered_xlsx,
    }
    for name, func in bindings.items():
        setattr(legacy, name, func)
        setattr(public, name, func)
