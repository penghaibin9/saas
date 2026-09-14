"""C-C3 scale-safe EffectiveGrade consumer for fail-course warning scans.

The mature warning service owns warning rules, idempotent upsert, counselor todo,
message delivery and audit.  Its EXAM_FAIL scan historically materialized every
ACTIVE AcademicGrade in the tenant before resolving retake/makeup effectiveness.
That is correct on small data but makes one grade publish proportional to the whole
multi-year grade ledger.

This guard changes only the read side:
- rows are ordered by academic student and streamed from MySQL;
- at most one student's candidate grades are held while the canonical
  ``resolve_effective_grade`` policy selects formal effective attempts;
- only the final fail count per affected student is retained;
- writes start after the streaming cursor is exhausted, avoiding MySQL server-side
  cursor / mutation conflicts.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException

from . import academic_affairs_effective_grade_policy_service as effective_policy
from . import academic_affairs_warning_service as warning


def _fail_counts(db, *, academic_student_ids: set[int] | None = None) -> dict[int, int]:
    """Return effective failing-course counts for the requested students.

    A normal publication can change many people and still needs the tenant-wide
    stream.  A correction changes exactly one student's grade, so its durable
    effect must not reread every active grade in the school before returning the
    final-approval receipt.
    """
    from app.models import AcademicGrade

    conditions = [
        AcademicGrade.tenant_id == warning._tid(),
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ]
    if academic_student_ids is not None:
        scoped_ids = sorted({int(value) for value in academic_student_ids if int(value) > 0})
        if not scoped_ids:
            return {}
        conditions.append(AcademicGrade.acad_student_id.in_(scoped_ids))

    statement = (
        select(AcademicGrade)
        .where(*conditions)
        .order_by(AcademicGrade.acad_student_id.asc(), AcademicGrade.id.asc())
        .execution_options(yield_per=500)
    )
    counts: dict[int, int] = {}
    current_student_id = None
    bucket = []

    def consume(rows) -> None:
        if not rows:
            return
        student_id = int(rows[0].acad_student_id)
        failed = sum(
            1
            for grade in effective_policy.resolve_effective_grade(rows)
            if str(grade.pass_status or "").upper() in {"FAILED", "FAIL"}
        )
        if failed:
            counts[student_id] = failed

    for grade in db.scalars(statement):
        student_id = int(grade.acad_student_id or 0)
        if current_student_id is None:
            current_student_id = student_id
        if student_id != current_student_id:
            consume(bucket)
            bucket = []
            current_student_id = student_id
        bucket.append(grade)
    consume(bucket)
    return counts


def _effect_scope_students(db, job) -> set[int] | None:
    """Limit correction effects to the only student whose effective grade changed."""
    if job is None or str(job.source_kind or "").upper() != "CORRECTION":
        return None

    from app.models import AcademicStudent
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    request = db.scalar(select(AaGradeChangeRequest).where(
        AaGradeChangeRequest.id == int(job.source_id or 0),
        AaGradeChangeRequest.tenant_id == warning._tid(),
        AaGradeChangeRequest.is_deleted.is_(False),
    ))
    student_id = int(getattr(request, "student_id", 0) or 0)
    academic_student_id = db.scalar(select(AcademicStudent.id).where(
        AcademicStudent.tenant_id == warning._tid(),
        AcademicStudent.student_id == student_id,
        AcademicStudent.is_deleted.is_(False),
    ))
    if int(academic_student_id or 0) <= 0:
        raise AppException(
            "DATA_CONFLICT",
            "成绩更正后置预警缺少来源学生，无法安全执行局部扫描",
            http_status=409,
        )
    return {int(academic_student_id)}


def _scan_warnings(user, effect_job=None) -> dict:
    """Mature EXAM_FAIL rule over canonical EffectiveGrade, without tenant-wide materialization."""
    threshold = warning._fail_threshold()
    now = datetime.utcnow()
    with warning.session() as db:
        job = None
        if effect_job is not None:
            from .academic_grade_effect_service import lock_effect_for_scan
            job = lock_effect_for_scan(db, *effect_job)
        scope_students = _effect_scope_students(db, job)
        counts = _fail_counts(db, academic_student_ids=scope_students)
        created = updated = 0
        rule_code = f"EXAM_FAIL_GE_{threshold}"
        for academic_student_id, fail_count in counts.items():
            if fail_count < threshold:
                continue
            was_created, was_updated = warning._upsert_warning(
                db,
                academic_student_id,
                warning._SOURCE,
                "MULTI_FAIL",
                warning._level_for(fail_count),
                f"挂科 {fail_count} 门",
                rule_code,
                now,
            )
            created += int(was_created)
            updated += int(was_updated)
        warning._audit(
            db,
            "ACAD_WARNING_SCAN",
            0,
            "SCAN_FAIL_COURSE",
            f"created={created} updated={updated} source=EFFECTIVE_GRADE_STREAM",
        )
        result = {
            "threshold": threshold,
            "created": created,
            "updated": updated,
            "notified": None,
            "notificationState": "NOT_VERIFIED",
            "sourcePolicy": "LATEST_FORMAL_SOURCE_V1",
            "scanScope": "CORRECTION_STUDENT" if scope_students is not None else "TENANT",
        }
        if job is not None:
            from .academic_grade_effect_service import finish_effect_in_scan
            finish_effect_in_scan(job, result)
        db.commit()
        return result


def scan_warnings(user, *, effect_job=None) -> dict:
    from .academic_grade_effect_service import warning_scan_lock
    with warning_scan_lock():
        return _scan_warnings(user, effect_job)


scan_warnings._effective_grade_stream_guard = True


def install() -> None:
    if not hasattr(warning, "_effective_grade_stream_original_scan_warnings"):
        warning._effective_grade_stream_original_scan_warnings = warning.scan_warnings
    warning.scan_warnings = scan_warnings
