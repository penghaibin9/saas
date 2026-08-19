"""C-C3 Effective Grade read-contract consumer guard.

The canonical grade service already owns effective-grade identity, ACTIVE-only
selection and frozen attempt-strategy semantics. A few older academic-process
readers predate that contract and still expose/count raw ``AcademicGrade`` rows.
This module closes only those read-side bypasses; it never writes grade facts and
never re-implements the ranking policy.

Scale discipline:
- student detail resolves one student's ACTIVE rows;
- legacy grade ledger streams rows grouped by student and keeps only a bounded
  top-ID window needed for the requested page, never all effective grade IDs;
- overview fail-rate streams one student's rows at a time, so a large tenant does
  not materialize the whole grade table merely to compute one indicator.
"""
from __future__ import annotations

import heapq
from collections.abc import Iterable, Iterator

from sqlalchemy import or_, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_service as policy
from app.modules.academic_affairs.services import academic_affairs_stats_scale_guard as stats_scale
from app.modules.academic_affairs.services import academic_affairs_stats_service as stats
from app.services import academic_service as legacy_academic
from app.services.db_service import _tid, session

_MAX_PAGE_SIZE = 200
_MAX_LEDGER_WINDOW = 20_000


def _effective_groups(db, conditions: Iterable) -> Iterator:
    """Yield effective rows while bounding memory to one student's candidate rows."""
    from app.models import AcademicGrade

    statement = (
        select(AcademicGrade)
        .where(*list(conditions))
        .order_by(AcademicGrade.acad_student_id.asc(), AcademicGrade.id.asc())
        .execution_options(yield_per=500)
    )
    current_student_id = None
    bucket = []
    for row in db.scalars(statement):
        student_id = int(row.acad_student_id or 0)
        if current_student_id is None:
            current_student_id = student_id
        if student_id != current_student_id:
            for selected in policy.resolve_effective_grade(bucket):
                yield selected
            bucket = []
            current_student_id = student_id
        bucket.append(row)
    if bucket:
        for selected in policy.resolve_effective_grade(bucket):
            yield selected


def _active_conditions():
    from app.models import AcademicGrade

    return [
        AcademicGrade.tenant_id == _tid(),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ]


def get_student_detail(sid) -> dict:
    """Legacy academic-process detail, with grades/credits sourced from EffectiveGrade."""
    from app.models import AcademicGrade

    result = legacy_academic._effective_grade_guard_original_get_student_detail(sid)
    with session() as db:
        student = legacy_academic._get_stu(db, sid)
        rows = db.scalars(
            select(AcademicGrade).where(
                AcademicGrade.tenant_id == _tid(),
                AcademicGrade.acad_student_id == student.id,
                AcademicGrade.record_status == "ACTIVE",
                AcademicGrade.is_deleted.is_(False),
            )
        ).all()
        effective = policy.resolve_effective_grade(rows)
        effective.sort(
            key=lambda row: (
                str(row.term or ""),
                str(row.course_code or row.course_name or ""),
                int(row.id),
            ),
            reverse=True,
        )
        result["grades"] = [legacy_academic._grade_row(row, student) for row in effective]
        earned = sum(
            float(row.credit_value or 0)
            for row in effective
            if str(row.pass_status or "").upper() == "PASSED"
        )
        required = float(student.required_credits or 0)
        result["credit"] = {
            "obtained": round(earned, 1),
            "required": required,
            "gap": max(0.0, round(required - earned, 1)),
        }
        result["effectiveGradePolicy"] = "LATEST_FORMAL_SOURCE_V1"
        result["effectiveGradeCount"] = len(effective)
    return result


get_student_detail._effective_grade_consumer_guard = True


def list_grades(page, ps, keyword=None, term=None, pass_status=None, exam_type=None):
    """Legacy grade ledger lists only effective grades with a bounded exact top-ID window."""
    from app.models import AcademicGrade, AcademicStudent

    page_no = max(1, int(page or 1))
    page_size = max(1, min(int(ps or 20), _MAX_PAGE_SIZE))
    window = page_no * page_size
    if window > _MAX_LEDGER_WINDOW:
        raise AppException(
            "VALIDATION_ERROR",
            "成绩台账翻页范围过深，请增加学期、关键字或状态筛选后再查询",
            details={"maxWindow": _MAX_LEDGER_WINDOW, "page": page_no, "pageSize": page_size},
        )

    conditions = _active_conditions()
    if term:
        conditions.append(AcademicGrade.term == term)
    value = str(keyword or "").strip()
    if value:
        student_ids = select(AcademicStudent.id).where(
            AcademicStudent.tenant_id == _tid(),
            AcademicStudent.is_deleted.is_(False),
            AcademicStudent.name.contains(value, autoescape=True),
        )
        conditions.append(
            or_(
                AcademicGrade.acad_student_id.in_(student_ids),
                AcademicGrade.course_name.contains(value, autoescape=True),
            )
        )

    expected_pass = str(pass_status or "").upper()
    expected_exam = str(exam_type or "").upper()
    with session() as db:
        # Exact pagination by descending grade ID without retaining every selected ID.
        # A min-heap of the largest ``page * pageSize`` IDs is sufficient to reconstruct
        # all rows through the requested page after the EffectiveGrade stream completes.
        top_ids: list[int] = []
        total = 0
        for row in _effective_groups(db, conditions):
            if expected_pass and str(row.pass_status or "").upper() != expected_pass:
                continue
            if expected_exam and str(row.exam_type or "").upper() != expected_exam:
                continue
            total += 1
            row_id = int(row.id)
            if len(top_ids) < window:
                heapq.heappush(top_ids, row_id)
            elif row_id > top_ids[0]:
                heapq.heapreplace(top_ids, row_id)

        ordered_ids = sorted(top_ids, reverse=True)
        start = (page_no - 1) * page_size
        page_ids = ordered_ids[start:start + page_size]
        if not page_ids:
            return [], total
        rows = db.execute(
            select(AcademicGrade, AcademicStudent)
            .outerjoin(AcademicStudent, legacy_academic._grade_join())
            .where(AcademicGrade.id.in_(page_ids))
            .order_by(AcademicGrade.id.desc())
        ).all()
        return [legacy_academic._grade_row(grade, student) for grade, student in rows], total


list_grades._effective_grade_consumer_guard = True
list_grades._effective_grade_bounded_window = _MAX_LEDGER_WINDOW


def _effective_fail_rate(db, scope, acad_ids, term_id) -> dict:
    """Overview fail-rate over EffectiveGrade, streamed per student."""
    from app.models import AcademicGrade

    conditions = _active_conditions()
    if acad_ids is not None:
        if not acad_ids:
            return stats._ind(
                "failRate", "挂科率", numerator=0, denominator=0,
                rate=None, unit="%", drill="grade",
            )
        conditions.append(AcademicGrade.acad_student_id.in_(acad_ids))
    codes = stats._term_codes(db, term_id)
    if codes is not None:
        if not codes:
            return stats._ind(
                "failRate", "挂科率", numerator=0, denominator=0,
                rate=None, unit="%", drill="grade",
            )
        conditions.append(AcademicGrade.term.in_(codes))

    denominator = 0
    failed = 0
    for row in _effective_groups(db, conditions):
        status = str(row.pass_status or "").upper()
        if status not in {"PASSED", "FAIL", "FAILED"}:
            continue
        denominator += 1
        if status in {"FAIL", "FAILED"}:
            failed += 1
    return stats._ind(
        "failRate", "挂科率", numerator=failed, denominator=denominator,
        rate=stats._rate(failed, denominator), unit="%", drill="grade",
    )


_effective_fail_rate._effective_grade_consumer_guard = True


def install() -> None:
    """Idempotently close legacy readers without touching shared route registration."""
    if not hasattr(legacy_academic, "_effective_grade_guard_original_get_student_detail"):
        legacy_academic._effective_grade_guard_original_get_student_detail = legacy_academic.get_student_detail
    if not hasattr(legacy_academic, "_effective_grade_guard_original_list_grades"):
        legacy_academic._effective_grade_guard_original_list_grades = legacy_academic.list_grades
    legacy_academic.get_student_detail = get_student_detail
    legacy_academic.list_grades = list_grades

    # services package installs the scale guard before routers are imported. Patch both
    # its exported replacement and the live stats module so a later explicit reinstall
    # cannot silently restore the raw ACTIVE-row counter.
    stats_scale._i_fail_rate = _effective_fail_rate
    stats._i_fail_rate = _effective_fail_rate
