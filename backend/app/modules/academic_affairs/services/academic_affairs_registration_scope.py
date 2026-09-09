"""P1-02 / AA-002 registration writer and main-ledger object scope.

This module owns only the formal register_student/list_registrations entrypoints.  The
existing eligibility/exception/deferral/unregistered read guard remains the source of
truth for scope SQL semantics; registration status transitions stay in the canonical
status service.
"""
from __future__ import annotations

import importlib
import json
from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.affairs_security import build_affairs_context
from app.modules.academic_affairs.services.academic_affairs_status_service import (
    audit_status_change,
    change_student_status,
)


def _legacy():
    return importlib.import_module(".academic_affairs_service", package=__package__)


def _scope_condition(ctx, db, StudentProfile):
    from .academic_affairs_registration_read_guard import _scope_condition as read_scope_condition

    return read_scope_condition(ctx, db, StudentProfile)


def assert_registration_student_scope(db, user, student_id):
    """Resolve one student through the same fail-closed scope contract as read ledgers."""
    ctx = build_affairs_context(user, db)
    return ctx.require_student(db, int(student_id))


def register_student(batch_id, user, student_id) -> dict:
    """Scoped formal registration writer; scope is proven inside the write transaction."""
    legacy = _legacy()
    _n, _r, uid = legacy._op()
    with legacy.session() as db:
        from app.models import AaRegistration, AaRegistrationBatch
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != legacy._tid():
            raise legacy.not_found("注册批次不存在")
        guard_term_writable(db, batch.term_id)
        if batch.status != "OPEN":
            raise legacy.AppException("DATA_CONFLICT", "注册批次未开放或已关闭")

        student = assert_registration_student_scope(db, user, student_id)
        existing = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == legacy._tid(),
            AaRegistration.batch_id == batch.id,
            AaRegistration.student_id == student.id,
            AaRegistration.is_deleted.is_(False),
        )).first()
        if existing and existing.status == "REGISTERED":
            raise legacy.AppException("DATA_CONFLICT", "该生已在本批次完成注册")

        snap = legacy._precheck(db, student.id)
        change_type = legacy._REG_CHANGE_TYPE.get(batch.register_type, "ANNUAL_REGISTER")
        rec = existing or AaRegistration(
            tenant_id=legacy._tid(), batch_id=batch.id, student_id=student.id
        )
        rec.precheck_json = json.dumps(snap, ensure_ascii=False)
        rec.register_at = datetime.utcnow()
        rec.operator_id = int(uid) if uid.isdigit() else None
        rec.status = "REGISTERED"
        if not existing:
            db.add(rec)
            db.flush()

        result = change_student_status(
            db,
            student.id,
            "REGISTERED",
            change_type=change_type,
            reason=f"{batch.register_type}注册",
            operator=uid,
            source_biz_id=rec.id,
        )
        legacy._audit(db, "AA_REGISTRATION", rec.id, "REGISTER", change_type)
        db.commit()
        db.refresh(rec)

    audit_status_change(
        student.id,
        result["fromStatus"],
        result["toStatus"],
        change_type,
        uid,
    )
    return {
        "registrationId": str(rec.id),
        "studentId": str(student.id),
        "status": "REGISTERED",
        "studentStatus": "REGISTERED",
        "changeType": change_type,
        "precheck": snap,
    }


def list_registrations(batch_id, user, page=1, page_size=50):
    """Main registration ledger with SQL scope and scope-identical COUNT."""
    legacy = _legacy()
    from app.models import AaRegistration, StudentProfile

    with legacy.session() as db:
        ctx = build_affairs_context(user, db)
        join = and_(
            StudentProfile.id == AaRegistration.student_id,
            StudentProfile.tenant_id == AaRegistration.tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
        conditions = [
            AaRegistration.tenant_id == legacy._tid(),
            AaRegistration.batch_id == int(batch_id),
            AaRegistration.is_deleted.is_(False),
            StudentProfile.tenant_id == legacy._tid(),
        ]
        scope = _scope_condition(ctx, db, StudentProfile)
        if scope is not None:
            conditions.append(scope)

        total = int(db.scalar(
            select(func.count(AaRegistration.id))
            .select_from(AaRegistration)
            .join(StudentProfile, join)
            .where(*conditions)
        ) or 0)
        offset = (max(1, int(page or 1)) - 1) * int(page_size)
        rows = db.execute(
            select(AaRegistration, StudentProfile)
            .join(StudentProfile, join)
            .where(*conditions)
            .order_by(AaRegistration.id.desc())
            .offset(offset)
            .limit(int(page_size))
        ).all()
        return [
            {
                "registrationId": str(reg.id),
                "studentId": str(reg.student_id),
                "studentNo": student.student_no,
                "realName": student.real_name,
                "status": reg.status,
                "registerAt": legacy._iso(reg.register_at),
            }
            for reg, student in rows
        ], total
