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

from . import academic_affairs_effective_grade_policy_service as effective_policy
from . import academic_affairs_warning_service as warning


def _fail_counts(db) -> dict[int, int]:
    from app.models import AcademicGrade

    statement = (
        select(AcademicGrade)
        .where(
            AcademicGrade.tenant_id == warning._tid(),
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        )
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


def scan_warnings(user) -> dict:
    """Mature EXAM_FAIL rule over canonical EffectiveGrade, without tenant-wide materialization."""
    threshold = warning._fail_threshold()
    now = datetime.utcnow()
    with warning.session() as db:
        counts = _fail_counts(db)
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
        db.commit()
        return {
            "threshold": threshold,
            "created": created,
            "updated": updated,
            "notified": created,
            "sourcePolicy": "LATEST_FORMAL_SOURCE_V1",
        }


scan_warnings._effective_grade_stream_guard = True


def install() -> None:
    if not hasattr(warning, "_effective_grade_stream_original_scan_warnings"):
        warning._effective_grade_stream_original_scan_warnings = warning.scan_warnings
    warning.scan_warnings = scan_warnings
