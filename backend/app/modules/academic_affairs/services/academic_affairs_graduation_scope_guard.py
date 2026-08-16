"""Graduation read-side organization scope guard.

The Graduation service historically inferred scope from a small set of role names. That
is unsafe once tenant-defined roles receive ``academicAffairs.graduation.view``: data
scope is an independent authority and must come from ``build_affairs_context``.

Current Graduation read contracts support school-wide and college-wide views. Narrower
CLASS/STUDENT/SELF scopes are intentionally fail-closed until a dedicated Graduation
contract defines those projections; they must never fall back to tenant-wide access.
"""
from __future__ import annotations

from app.core.affairs_security import build_affairs_context


def graduation_college_scope_ids(db, user) -> set[int] | None:
    """Return None for tenant-wide, college ids for COLLEGE, or empty for unsupported scope."""
    ctx = build_affairs_context(user or {}, db)
    if ctx.scope_type == "TENANT_ALL":
        return None
    if ctx.scope_type == "COLLEGE":
        return {int(value) for value in (ctx.college_ids or set())}
    return set()


graduation_college_scope_ids._graduation_scope_guard = True


def graduation_list_batches(user, status=None, page=1, page_size=50):
    """Return only batches and aggregates visible to the caller's graduation data scope."""
    from sqlalchemy import and_, func, select

    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as service

    page = max(1, int(page or 1))
    page_size = max(1, int(page_size or 50))
    with service.session() as db:
        scope = graduation_college_scope_ids(db, user)
        if scope is not None and not scope:
            return [], 0

        conds = [
            AaGraduationAuditBatch.tenant_id == service._tid(),
            AaGraduationAuditBatch.is_deleted.is_(False),
        ]
        if status:
            conds.append(AaGraduationAuditBatch.status == status)

        student_join = and_(
            StudentProfile.id == AaGraduationAuditResult.student_id,
            StudentProfile.tenant_id == AaGraduationAuditResult.tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
        if scope is not None:
            visible_batch_ids = (
                select(AaGraduationAuditResult.batch_id)
                .join(StudentProfile, student_join)
                .where(
                    AaGraduationAuditResult.tenant_id == service._tid(),
                    AaGraduationAuditResult.is_deleted.is_(False),
                    StudentProfile.college_id.in_(scope),
                )
                .distinct()
            )
            conds.append(AaGraduationAuditBatch.id.in_(visible_batch_ids))

        total = db.scalar(select(func.count()).select_from(AaGraduationAuditBatch).where(*conds)) or 0
        offset = (page - 1) * page_size
        batches = db.scalars(
            select(AaGraduationAuditBatch)
            .where(*conds)
            .order_by(AaGraduationAuditBatch.id.desc())
            .offset(offset)
            .limit(page_size)
        ).all()

        out = []
        for batch in batches:
            result_query = select(AaGraduationAuditResult).where(
                AaGraduationAuditResult.tenant_id == service._tid(),
                AaGraduationAuditResult.batch_id == batch.id,
                AaGraduationAuditResult.is_deleted.is_(False),
            )
            if scope is not None:
                result_query = result_query.join(StudentProfile, student_join).where(
                    StudentProfile.college_id.in_(scope)
                )
            results = db.scalars(result_query).all()
            out.append({
                "batchId": str(batch.id),
                "batchName": batch.batch_name,
                "gradeYear": batch.grade_year,
                "majorId": str(batch.major_id) if batch.major_id else None,
                "status": batch.status,
                "total": len(results),
                "passed": sum(1 for row in results if row.overall == "SYSTEM_PASSED"),
                "abnormal": sum(1 for row in results if row.overall == "SYSTEM_ABNORMAL"),
                "concluded": sum(1 for row in results if row.conclusion),
                "archived": sum(1 for row in results if row.status == "ARCHIVED"),
            })
        return out, int(total)


graduation_list_batches._graduation_scope_guard = True


def install(service) -> None:
    """Install the shared-context projections onto the existing Graduation service owner."""
    if not getattr(getattr(service, "_college_scope_ids", None), "_graduation_scope_guard", False):
        service._college_scope_ids = graduation_college_scope_ids
    if not getattr(getattr(service, "list_batches", None), "_graduation_scope_guard", False):
        service.list_batches = graduation_list_batches
