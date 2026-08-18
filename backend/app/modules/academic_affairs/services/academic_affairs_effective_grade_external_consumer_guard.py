"""C-C3 EffectiveGrade guard for cross-domain read consumers.

The grade domain already owns ACTIVE-only attempt identity and the frozen
``resolve_effective_grade`` policy.  Some older cross-domain readers still consume
raw ``AcademicGrade`` rows directly.  This adapter closes those read-side bypasses
without moving ownership of grading, funding, guardian, or mobile-student workflows.

Covered consumers:
- student mobile academic summary: only effective grades are exposed/countable;
- guardian overview: ``courseCount`` is the effective course/attempt projection;
- scholarship eligibility: a superseded/ineffective failed attempt cannot block an
  otherwise effective passed result.

No AcademicGrade row is written here.  GPA remains the canonical aggregate stored on
AcademicStudent, whose grade publication/correction refresh already uses the same
EffectiveGrade policy and frozen GPA point rule.
"""
from __future__ import annotations

from sqlalchemy import select

from . import academic_affairs_effective_grade_policy_service as effective_policy


def _effective_rows(db, tenant_id: int, acad_student_id: int):
    from app.models import AcademicGrade

    candidates = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == int(tenant_id),
        AcademicGrade.acad_student_id == int(acad_student_id),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    )).all()
    rows = list(effective_policy.resolve_effective_grade(candidates))
    rows.sort(key=lambda row: int(row.id), reverse=True)
    return rows


def mobile_academic_my(user: dict) -> dict:
    """Student mobile academic card from EffectiveGrade, preserving legacy shape."""
    from app.services import mobile_student_service as mobile
    from app.models import AcademicStudent, AcademicWarning

    u = mobile._require_student(user)
    if not mobile.db_enabled():
        return mobile._empty("演示模式")
    with mobile._session() as db:
        stu = mobile.resolve_student(db, u)
        if not stu:
            return mobile._empty()
        academic = mobile._resolve_domain_student(db, AcademicStudent, stu)
        if not academic:
            return mobile._empty("你暂无学业记录")
        grades = _effective_rows(db, mobile._tid(), int(academic.id))
        warnings = db.scalars(select(AcademicWarning).where(
            AcademicWarning.tenant_id == mobile._tid(),
            AcademicWarning.acad_student_id == academic.id,
            AcademicWarning.is_deleted.is_(False),
            AcademicWarning.record_status == "ACTIVE",
        ).order_by(AcademicWarning.id.desc())).all()

        scored = [row for row in grades if row.score is not None]
        failed_count = sum(
            1 for row in grades
            if str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
        )
        obtained_credits = sum(
            float(row.credit_value or 0)
            for row in grades
            if str(row.pass_status or "").upper() == "PASSED"
        )
        avg_score = (
            round(sum(float(row.score) for row in scored) / len(scored))
            if scored else 0
        )
        return {
            "hasData": True,
            "summary": {
                "gpa": float(academic.gpa or 0),
                "avgScore": avg_score,
                "obtainedCredits": round(obtained_credits, 2),
                "requiredCredits": float(academic.required_credits or 0),
                "failedCount": failed_count,
                "academicStatus": academic.academic_status,
                "warningLevel": academic.warning_level,
            },
            "grades": [
                {
                    "course": row.course_name,
                    "term": row.term or "",
                    "score": row.score,
                    "passStatus": row.pass_status,
                }
                for row in grades
            ],
            "warnings": [
                {
                    "type": row.warn_type,
                    "level": row.level,
                    "reason": row.reason or "",
                    "status": row.status,
                }
                for row in warnings
            ],
            "effectiveGradePolicy": "LATEST_FORMAL_SOURCE_V1",
            "effectiveGradeCount": len(grades),
        }


mobile_academic_my._effective_grade_external_consumer_guard = True


def guardian_student_overview(user: dict) -> dict:
    """Preserve guardian payload but correct academic courseCount to EffectiveGrade."""
    from app.student_portal.services import guardian_service as guardian
    from app.models import AcademicStudent

    result = guardian._effective_grade_guard_original_student_overview(user)
    student_id = str((user or {}).get("studentId") or "")
    if not student_id.isdigit():
        return result
    with guardian.session() as db:
        academic = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == guardian._tid(),
            AcademicStudent.student_id == int(student_id),
            AcademicStudent.is_deleted.is_(False),
        )).first()
        effective = _effective_rows(db, guardian._tid(), int(academic.id)) if academic else []
    academic_payload = result.get("academic")
    if isinstance(academic_payload, dict):
        academic_payload["courseCount"] = len(effective)
        academic_payload["effectiveGradePolicy"] = "LATEST_FORMAL_SOURCE_V1"
    return result


guardian_student_overview._effective_grade_external_consumer_guard = True


def scholarship_eligible(db, student_id: int) -> bool:
    """Scholarship academic gate uses the same effective-attempt policy as transcript."""
    from app.services import affairs_funding_service as funding
    from app.models import AcademicStudent, AffairsDisciplineCase

    academic = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == funding._tid(),
        AcademicStudent.student_id == int(student_id),
        AcademicStudent.is_deleted.is_(False),
    )).first()
    if academic:
        grades = _effective_rows(db, funding._tid(), int(academic.id))
        if any(
            str(row.pass_status or "").upper() in {"FAIL", "FAILED"}
            for row in grades
        ):
            return False

    bad = db.scalars(select(AffairsDisciplineCase).where(
        AffairsDisciplineCase.tenant_id == funding._tid(),
        AffairsDisciplineCase.student_id == int(student_id),
        AffairsDisciplineCase.status.in_(["EFFECTIVE", "ARCHIVED"]),
        AffairsDisciplineCase.is_deleted.is_(False),
    )).first()
    if bad:
        return False
    return True


scholarship_eligible._effective_grade_external_consumer_guard = True


def install() -> None:
    from app.services import mobile_student_service as mobile
    from app.student_portal.services import guardian_service as guardian
    from app.services import affairs_funding_service as funding

    current_mobile = getattr(mobile, "academic_my", None)
    if not getattr(current_mobile, "_effective_grade_external_consumer_guard", False):
        if not hasattr(mobile, "_effective_grade_guard_original_academic_my"):
            mobile._effective_grade_guard_original_academic_my = current_mobile
        mobile.academic_my = mobile_academic_my

    current_guardian = getattr(guardian, "student_overview", None)
    if not getattr(current_guardian, "_effective_grade_external_consumer_guard", False):
        if not hasattr(guardian, "_effective_grade_guard_original_student_overview"):
            guardian._effective_grade_guard_original_student_overview = current_guardian
        guardian.student_overview = guardian_student_overview

    current_funding = getattr(funding, "_check_scholarship", None)
    if not getattr(current_funding, "_effective_grade_external_consumer_guard", False):
        if not hasattr(funding, "_effective_grade_guard_original_check_scholarship"):
            funding._effective_grade_guard_original_check_scholarship = current_funding
        funding._check_scholarship = scholarship_eligible
