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


def assert_college_review_authority(db, user, result):
    """学院初审由学生所属学院的当前责任账号办理，校级不能冒充。"""
    from sqlalchemy import select
    from app.core.affairs_security import no_data_scope
    from app.core.permissions import _match
    from app.models import StudentProfile
    from app.services.db_service import _tid
    from .academic_affairs_grade_correction_command import _current_user_id
    from .academic_affairs_responsibility_service import resolve_organization

    ctx = build_affairs_context(user or {}, db)
    if (ctx.scope_type != "COLLEGE" or not ctx.college_ids
            or not _match("academicAffairs.graduation.collegeReview", ctx.permission_codes)):
        raise no_data_scope("学院初审须由本学院责任账号办理，校教务处负责终审")
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == result.student_id, StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    if not student or int(student.college_id or 0) not in ctx.college_ids:
        raise no_data_scope("该学生不在您的学院责任范围内")
    responsibility = resolve_organization(
        db, "COLLEGE", student.college_id,
        permission_code="academicAffairs.graduation.collegeReview",
    )
    actor_id = str(_current_user_id(db, user))
    if not responsibility["resolved"] or actor_id not in responsibility["assigneeUserIds"]:
        raise no_data_scope("您不是该学院当前有效的初审责任人，请核对组织与任职")
    return responsibility


def graduation_college_scope_ids(db, user) -> set[int] | None:
    """Return None for tenant-wide, college ids for COLLEGE, or empty for unsupported scope."""
    ctx = build_affairs_context(user or {}, db)
    if ctx.scope_type == "TENANT_ALL":
        return None
    if ctx.scope_type == "COLLEGE":
        return {int(value) for value in (ctx.college_ids or set())}
    return set()


def assert_school_review_authority(db, user):
    from app.core.affairs_security import no_data_scope
    from app.core.permissions import _match
    from .academic_affairs_grade_correction_command import _current_user_id
    from .academic_affairs_responsibility_service import resolve_school
    context = build_affairs_context(user or {}, db)
    if context.scope_type != "TENANT_ALL" or not _match("academicAffairs.graduation.final", context.permission_codes):
        raise no_data_scope("毕业终审须由当前有终审权限的校教务责任岗位办理")
    owner = resolve_school(db, permission_code="academicAffairs.graduation.final")
    if not owner["resolved"] or str(_current_user_id(db, user)) not in owner["assigneeUserIds"]:
        raise no_data_scope("您不是当前有效的校教务毕业终审责任人")
    return owner


def result_responsibilities(db, user, rows):
    """列表和详情共用当前责任投影，每页预载学生并按学院复用任职解析。"""
    from sqlalchemy import select
    from app.core.exceptions import AppException
    from app.models import StudentProfile
    from app.services.db_service import _tid
    from .academic_affairs_grade_correction_command import _current_user_id
    from .academic_affairs_responsibility_service import resolve_organization, resolve_school
    if not rows:
        return {}
    context = build_affairs_context(user, db)
    try:
        actor_id = str(_current_user_id(db, user))
    except AppException as error:
        if error.code != "NO_PERMISSION":
            raise
        actor_id = ""
    students = {row.id: row for row in db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        StudentProfile.id.in_([row.student_id for row in rows]),
    )).all()}
    owners = {}
    from app.core.permissions import _match
    cache = {}
    school = resolve_school(db, permission_code="academicAffairs.graduation.final", cache=cache)
    result = {}
    for row in rows:
        student = students.get(row.student_id)
        college_id = student.college_id if student else None
        if college_id not in owners:
            owners[college_id] = resolve_organization(db, "COLLEGE", college_id,
                permission_code="academicAffairs.graduation.collegeReview", cache=cache)
        owner = owners[college_id]
        initial = row.status in {"SYSTEM_PASSED", "SYSTEM_ABNORMAL", "COLLEGE_REVIEW"}
        result[row.id] = {
            "responsibility": owner if initial else school if row.status == "ACADEMIC_REVIEW" else None,
            "canCollegeReview": bool(initial and context.scope_type == "COLLEGE"
                and _match("academicAffairs.graduation.collegeReview", context.permission_codes)
                and college_id in context.college_ids and owner["resolved"] and actor_id in owner["assigneeUserIds"]),
            "canAcademicFinal": bool(row.status == "ACADEMIC_REVIEW" and context.scope_type == "TENANT_ALL"
                and _match("academicAffairs.graduation.final", context.permission_codes)
                and school["resolved"] and actor_id in school["assigneeUserIds"]),
            "collegeReviewHint": "学院责任账号完成初审后，交由校教务处终审",
            "nextStep": {"code": "ACADEMIC_REVIEW", "label": "校教务终审", "responsibility": school} if initial else None,
        }
    return result


graduation_college_scope_ids._graduation_scope_guard = True


def graduation_list_batches(user, status=None, page=1, page_size=50, *, batch_id=None):
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
    page_size = min(200, max(1, int(page_size or 50)))
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
        if batch_id is not None:
            batch_conds.append(AaGraduationAuditBatch.id == int(batch_id))

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
