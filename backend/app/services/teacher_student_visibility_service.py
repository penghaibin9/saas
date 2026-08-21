"""Teacher Miniapp V3 T3 student visibility SQL compiler.

The teacher mobile surface already has one canonical scope authority in
``mobile_teacher_service.resolve_teacher_scope``. This module does not re-read scope rows and
does not maintain a second role table. It compiles the resolved CLASS / STUDENT / COLLEGE /
ADVISOR scope into correlated SQL while reusing the canonical advisor-role set from the
existing teacher-mobile implementation.

Important scale invariant: authorization sets stay small (class names, student numbers,
college names, advisor identities). We never materialize the full visible-student population
into a large Python id collection.
"""
from __future__ import annotations

from sqlalchemy import and_, exists, false, or_, select, true

from app.services import _mobile_teacher_service_impl as teacher_scope_impl
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


def is_advisor_scope(scope: dict | None) -> bool:
    """Reuse the canonical advisor-role authority; do not duplicate the role-code set here."""
    role = str((scope or {}).get("roleCode") or "").strip().upper()
    return role in teacher_scope_impl._ADVISOR_ROLES


def _scope_dimensions(scope: dict) -> dict:
    """Normalize only the small authorization dimensions before any tenant DB context is needed."""
    advisor_role = is_advisor_scope(scope)
    return {
        "advisorRole": advisor_role,
        "advisorUserIds": _positive_ints(scope.get("advisorUserIds")) if advisor_role else (),
        "advisorNames": _clean_strings(scope.get("advisorNames")),
        "studentNos": _clean_strings(scope.get("studentNos")),
        "classNames": _class_name_variants(scope.get("classNames")),
        "collegeNames": _clean_strings(scope.get("collegeNames")),
    }


def _has_effective_scope(dimensions: dict) -> bool:
    if dimensions["advisorRole"]:
        return bool(dimensions["advisorUserIds"] or dimensions["advisorNames"])
    return bool(
        dimensions["studentNos"]
        or dimensions["classNames"]
        or dimensions["collegeNames"]
        or dimensions["advisorNames"]
    )


def _advisor_student_scope(dimensions: dict, tenant_id: int,
                           StudentProfile, InternshipRecord, GraduationStudent) -> list:
    """Compile advisor business relations with canonical stable-id-first semantics."""
    advisor_role = bool(dimensions["advisorRole"])
    advisor_user_ids = dimensions["advisorUserIds"]
    advisor_names = dimensions["advisorNames"]
    predicates = []

    internship_advisor = []
    if advisor_user_ids:
        internship_advisor.append(InternshipRecord.advisor_user_id.in_(advisor_user_ids))
    if advisor_names:
        # Stable advisor_user_id is authoritative for advisor roles. Name is only a historical
        # fallback when the stable relation has not been backfilled. Non-advisor roles can only
        # consume an explicitly resolved ADVISOR-name scope and never borrow their own user id.
        if advisor_role:
            internship_advisor.append(and_(
                InternshipRecord.advisor_user_id.is_(None),
                InternshipRecord.advisor_name.in_(advisor_names),
            ))
        else:
            internship_advisor.append(InternshipRecord.advisor_name.in_(advisor_names))
    if internship_advisor:
        predicates.append(exists(
            select(1).select_from(InternshipRecord).where(
                InternshipRecord.tenant_id == tenant_id,
                InternshipRecord.is_deleted.is_(False),
                InternshipRecord.student_id == StudentProfile.id,
                or_(*internship_advisor),
            )
        ))

    if advisor_names:
        # Graduation's current canonical relation is still advisor_name. Keep that historical
        # authority; do not invent a second mentor identity mapping in V3.
        predicates.append(exists(
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
    return predicates


def compile_teacher_student_visibility(user: dict, student_id_column, *, scope: dict | None = None):
    """Compile canonical teacher scope into one correlated student visibility predicate.

    ``ADMIN_TENANT`` is explicitly tenant-wide. Advisor roles are *exclusive* business-
    relation scopes exactly like ``scope_match_row``: class/student/college dimensions cannot
    widen the current advisor role. Other ``SCOPED`` roles use the union of their small resolved
    dimensions. Unknown or empty scopes fail closed before opening tenant DB context.
    """
    from app.models import (College, GraduationStudent, InternshipRecord, Major,
                            SchoolClass, StudentProfile)

    resolved_scope = scope or teacher_scope_authority.resolve_teacher_scope(user or {})
    mode = str(resolved_scope.get("mode") or "").upper()
    if mode == "ADMIN_TENANT":
        return true()
    if mode != "SCOPED":
        return false()

    dimensions = _scope_dimensions(resolved_scope)
    if not _has_effective_scope(dimensions):
        return false()

    tenant_id = _tid()
    advisor_scope = _advisor_student_scope(
        dimensions, tenant_id, StudentProfile, InternshipRecord, GraduationStudent
    )

    # Canonical hard boundary: when the current role is a mentor/advisor, only the business
    # assignment relation is valid. The same account's class/college/student scopes belong to
    # other roles and must not widen this request.
    if dimensions["advisorRole"]:
        student_scope = advisor_scope
    else:
        student_scope = []
        student_nos = dimensions["studentNos"]
        if student_nos:
            student_scope.append(StudentProfile.student_no.in_(student_nos))

        class_names = dimensions["classNames"]
        if class_names:
            student_scope.append(exists(
                select(1).select_from(SchoolClass).where(
                    SchoolClass.tenant_id == tenant_id,
                    SchoolClass.is_deleted.is_(False),
                    SchoolClass.id == StudentProfile.class_id,
                    SchoolClass.class_name.in_(class_names),
                )
            ))

        college_names = dimensions["collegeNames"]
        if college_names:
            # StudentProfile has denormalized college_id/major_id/class_id combinations across
            # historical data. Mirror the canonical fallback order entirely in SQL.
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

        # Explicit ADVISOR-name scope remains valid for non-advisor roles because the canonical
        # scope matcher permits it; stable advisor_user_id never widens a non-advisor role.
        student_scope.extend(advisor_scope)

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
