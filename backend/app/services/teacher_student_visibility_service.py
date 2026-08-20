"""Teacher Miniapp V3 T3 student visibility SQL compiler.

The teacher mobile surface already has one canonical scope authority in
``mobile_teacher_service.resolve_teacher_scope``.  This module does not interpret roles or
re-read scope rows.  It only compiles the resolved CLASS / STUDENT / COLLEGE / ADVISOR scope
into a correlated SQL predicate over ``StudentProfile``.

Important scale invariant: authorization sets stay small (class names, student numbers,
college names, advisor identities).  We never materialize every visible student and never turn
``studentIds .all()`` into a large Python ``IN`` list.
"""
from __future__ import annotations

from sqlalchemy import and_, exists, false, or_, select, true

from app.services import mobile_teacher_service as teacher_scope_authority
from app.services.db_service import _tid


def _clean_strings(values) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in (values or ()) if str(value).strip()}))


def _class_name_variants(values) -> tuple[str, ...]:
    variants: set[str] = set()
    for raw in _clean_strings(values):
        base = raw.rstrip("班")
        if base:
            variants.add(base)
            variants.add(base + "班")
        variants.add(raw)
    return tuple(sorted(variants))


def _positive_ints(values) -> tuple[int, ...]:
    result: set[int] = set()
    for raw in values or ():
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            result.add(value)
    return tuple(sorted(result))


def compile_teacher_student_visibility(user: dict, student_id_column):
    """Compile canonical teacher scope into one correlated student visibility predicate.

    ``ADMIN_TENANT`` is explicitly tenant-wide.  ``SCOPED`` is a union of the small
    authorization dimensions returned by the existing authority.  Unknown modes fail closed.
    """
    from app.models import (College, GraduationStudent, InternshipRecord, Major,
                            SchoolClass, StudentProfile)

    scope = teacher_scope_authority.resolve_teacher_scope(user or {})
    mode = str(scope.get("mode") or "").upper()
    if mode == "ADMIN_TENANT":
        return true()
    if mode != "SCOPED":
        return false()

    tenant_id = _tid()
    student_scope = []

    student_nos = _clean_strings(scope.get("studentNos"))
    if student_nos:
        student_scope.append(StudentProfile.student_no.in_(student_nos))

    class_names = _class_name_variants(scope.get("classNames"))
    if class_names:
        student_scope.append(exists(
            select(1).select_from(SchoolClass).where(
                SchoolClass.tenant_id == tenant_id,
                SchoolClass.is_deleted.is_(False),
                SchoolClass.id == StudentProfile.class_id,
                SchoolClass.class_name.in_(class_names),
            )
        ))

    college_names = _clean_strings(scope.get("collegeNames"))
    if college_names:
        # StudentProfile has denormalized college_id/major_id/class_id combinations across
        # historical data.  Mirror the canonical mobile visibility fallback order in SQL:
        # direct college → major.college → class.major.college.
        direct_college = exists(
            select(1).select_from(College).where(
                College.tenant_id == tenant_id,
                College.is_deleted.is_(False),
                College.id == StudentProfile.college_id,
                College.college_name.in_(college_names),
            )
        )
        major_college = exists(
            select(1).select_from(Major).join(
                College,
                and_(College.id == Major.college_id, College.tenant_id == tenant_id),
            ).where(
                Major.tenant_id == tenant_id,
                Major.is_deleted.is_(False),
                Major.id == StudentProfile.major_id,
                College.is_deleted.is_(False),
                College.college_name.in_(college_names),
            )
        )
        class_college = exists(
            select(1).select_from(SchoolClass).join(
                Major,
                and_(Major.id == SchoolClass.major_id, Major.tenant_id == tenant_id),
            ).join(
                College,
                and_(College.id == Major.college_id, College.tenant_id == tenant_id),
            ).where(
                SchoolClass.tenant_id == tenant_id,
                SchoolClass.is_deleted.is_(False),
                SchoolClass.id == StudentProfile.class_id,
                Major.is_deleted.is_(False),
                College.is_deleted.is_(False),
                College.college_name.in_(college_names),
            )
        )
        student_scope.append(or_(direct_college, major_college, class_college))

    advisor_user_ids = _positive_ints(scope.get("advisorUserIds"))
    advisor_names = _clean_strings(scope.get("advisorNames"))
    internship_advisor = []
    if advisor_user_ids:
        internship_advisor.append(InternshipRecord.advisor_user_id.in_(advisor_user_ids))
    if advisor_names:
        # Stable advisor_user_id wins when present.  Name is historical compatibility only.
        internship_advisor.append(and_(
            InternshipRecord.advisor_user_id.is_(None),
            InternshipRecord.advisor_name.in_(advisor_names),
        ))
    if internship_advisor:
        student_scope.append(exists(
            select(1).select_from(InternshipRecord).where(
                InternshipRecord.tenant_id == tenant_id,
                InternshipRecord.is_deleted.is_(False),
                InternshipRecord.student_id == StudentProfile.id,
                or_(*internship_advisor),
            )
        ))

    if advisor_names:
        # Graduation's current canonical mobile visibility still uses advisor_name as the
        # historical relation.  Do not invent a second mentor identity mapping here.
        student_scope.append(exists(
            select(1).select_from(GraduationStudent).where(
                GraduationStudent.tenant_id == tenant_id,
                GraduationStudent.is_deleted.is_(False),
                or_(
                    GraduationStudent.student_id == StudentProfile.id,
                    and_(
                        GraduationStudent.student_id.is_(None),
                        GraduationStudent.student_no == StudentProfile.student_no,
                    ),
                ),
                GraduationStudent.advisor_name.in_(advisor_names),
            )
        ))

    if not student_scope:
        return false()

    return exists(
        select(1).select_from(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
            StudentProfile.id == student_id_column,
            or_(*student_scope),
        )
    )
