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
    """Return scope-safe batch counters with one grouped aggregate query per page.

    The legacy implementation loaded every result row once per batch. Graduation season
    can put thousands of students behind each row, so a 100-batch page became an N+1 query
    plus full ORM materialization. This projection keeps the same DTO while doing only:
    count visible batches -> fetch one batch page -> aggregate that page in SQL.
    """
    from sqlalchemy import and_, case, func, select

    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as service

    page = max(1, int(page or 1))
    page_size = max(1, int(page_size or 50))
    with service.session() as db:
        scope = graduation_college_scope_ids(db, user)
        if scope is not None and not scope:
            return [], 0

        tenant_id = service._tid()
        batch_conds = [
            AaGraduationAuditBatch.tenant_id == tenant_id,
            AaGraduationAuditBatch.is_deleted.is_(False),
        ]
        if status:
            batch_conds.append(AaGraduationAuditBatch.status == status)

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
                    AaGraduationAuditResult.tenant_id == tenant_id,
                    AaGraduationAuditResult.is_deleted.is_(False),
                    StudentProfile.college_id.in_(scope),
                )
                .distinct()
            )
            batch_conds.append(AaGraduationAuditBatch.id.in_(visible_batch_ids))

        total = db.scalar(
            select(func.count()).select_from(AaGraduationAuditBatch).where(*batch_conds)
        ) or 0
        offset = (page - 1) * page_size
        batches = db.scalars(
            select(AaGraduationAuditBatch)
            .where(*batch_conds)
            .order_by(AaGraduationAuditBatch.id.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        if not batches:
            return [], int(total)

        batch_ids = [int(batch.id) for batch in batches]
        result_conds = [
            AaGraduationAuditResult.tenant_id == tenant_id,
            AaGraduationAuditResult.batch_id.in_(batch_ids),
            AaGraduationAuditResult.is_deleted.is_(False),
        ]
        aggregate_query = select(
            AaGraduationAuditResult.batch_id.label("batch_id"),
            func.count(AaGraduationAuditResult.id).label("total"),
            func.sum(case((AaGraduationAuditResult.overall == "SYSTEM_PASSED", 1), else_=0)).label("passed"),
            func.sum(case((AaGraduationAuditResult.overall == "SYSTEM_ABNORMAL", 1), else_=0)).label("abnormal"),
            func.sum(case((AaGraduationAuditResult.conclusion.is_not(None), 1), else_=0)).label("concluded"),
            func.sum(case((AaGraduationAuditResult.status == "ARCHIVED", 1), else_=0)).label("archived"),
        )
        if scope is not None:
            aggregate_query = aggregate_query.join(StudentProfile, student_join)
            result_conds.append(StudentProfile.college_id.in_(scope))
        aggregate_query = aggregate_query.where(*result_conds).group_by(AaGraduationAuditResult.batch_id)
        aggregates = {
            int(row.batch_id): row
            for row in db.execute(aggregate_query).all()
        }

        out = []
        for batch in batches:
            stats = aggregates.get(int(batch.id))
            out.append({
                "batchId": str(batch.id),
                "batchName": batch.batch_name,
                "gradeYear": batch.grade_year,
                "majorId": str(batch.major_id) if batch.major_id else None,
                "status": batch.status,
                "total": int(stats.total or 0) if stats else 0,
                "passed": int(stats.passed or 0) if stats else 0,
                "abnormal": int(stats.abnormal or 0) if stats else 0,
                "concluded": int(stats.concluded or 0) if stats else 0,
                "archived": int(stats.archived or 0) if stats else 0,
            })
        return out, int(total)


graduation_list_batches._graduation_scope_guard = True


def install(service) -> None:
    """Install the shared-context projections onto the existing Graduation service owner."""
    if not getattr(getattr(service, "_college_scope_ids", None), "_graduation_scope_guard", False):
        service._college_scope_ids = graduation_college_scope_ids
    if not getattr(getattr(service, "list_batches", None), "_graduation_scope_guard", False):
        service.list_batches = graduation_list_batches
