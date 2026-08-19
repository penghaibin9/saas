"""INT ProgramCourse formation provenance inventory for shared-schema backfill.

TeachingTask runtime formation is not ProgramCourse plan provenance. Current
legacy ProgramCourse rows store no formation_mode and no source link to the task
that may later have been generated from them. This inventory therefore accepts
only explicit migration evidence keyed by ProgramCourse id; absent evidence
remains a blocker instead of inferring from course labels, task majority, or an
ADMIN_FIXED default.

The database side is intentionally one explicit-tenant read and zero writes.
Evidence loading/parsing belongs to the future privileged migration owner.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from sqlalchemy import select

from .academic_affairs_task_formation_policy import (
    FORMATION_MODES,
    normalize_formation_mode,
)

_MAX_SAMPLE_LIMIT = 100
_DEFAULT_SAMPLE_LIMIT = 20


def _positive_tenant_id(value: object) -> int:
    try:
        tenant_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("tenant_id must be a positive integer") from exc
    if tenant_id <= 0:
        raise ValueError("tenant_id must be a positive integer")
    return tenant_id


def _bounded_sample_limit(value: object) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("sample_limit must be an integer") from exc
    if limit < 1 or limit > _MAX_SAMPLE_LIMIT:
        raise ValueError(f"sample_limit must be between 1 and {_MAX_SAMPLE_LIMIT}")
    return limit


def _program_course_inventory_statement(tenant_id: int):
    from app.models import AaProgramCourse

    tid = _positive_tenant_id(tenant_id)
    return (
        select(
            AaProgramCourse.id,
            AaProgramCourse.program_id,
            AaProgramCourse.course_id,
            AaProgramCourse.open_term_no,
            AaProgramCourse.module,
        )
        .where(
            AaProgramCourse.tenant_id == tid,
            AaProgramCourse.is_deleted.is_(False),
        )
        .order_by(AaProgramCourse.id.asc())
    )


def _required_text(value: object) -> str:
    return str(value or "").strip()


def _append_sample(samples: dict[str, list[str]], code: str, row_id: int, limit: int) -> None:
    values = samples.setdefault(code, [])
    text = str(int(row_id))
    if text not in values and len(values) < limit:
        values.append(text)


def _build_inventory(
    program_course_rows,
    *,
    provenance_by_program_course_id: Mapping[int | str, Mapping[str, object]] | None = None,
    sample_limit: int = _DEFAULT_SAMPLE_LIMIT,
) -> dict:
    """Classify explicit ProgramCourse provenance with no additional DB reads."""
    limit = _bounded_sample_limit(sample_limit)
    provenance_source = provenance_by_program_course_id or {}
    if not isinstance(provenance_source, Mapping):
        raise ValueError("provenance_by_program_course_id must be a mapping")

    evidence_by_id: dict[int, Mapping[str, object]] = {}
    for raw_id, raw_evidence in provenance_source.items():
        try:
            row_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("ProgramCourse provenance key must be a positive integer id") from exc
        if row_id <= 0:
            raise ValueError("ProgramCourse provenance key must be a positive integer id")
        if not isinstance(raw_evidence, Mapping):
            raise ValueError(f"ProgramCourse provenance {row_id} must be an object")
        if row_id in evidence_by_id:
            raise ValueError(f"duplicate ProgramCourse provenance id: {row_id}")
        evidence_by_id[row_id] = raw_evidence

    rows: dict[int, dict] = {}
    blocker_counts: Counter[str] = Counter()
    blocker_samples: dict[str, list[str]] = {}
    mode_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    resolved_ids: set[int] = set()

    def block(code: str, row_id: int) -> None:
        blocker_counts[code] += 1
        _append_sample(blocker_samples, code, row_id, limit)

    for program_course_id, program_id, course_id, open_term_no, module in program_course_rows:
        row_id = int(program_course_id)
        if row_id in rows:
            block("DUPLICATE_PROGRAM_COURSE_ROW", row_id)
            continue
        rows[row_id] = {
            "programCourseId": row_id,
            "programId": int(program_id),
            "courseId": int(course_id) if course_id else None,
            "openTermNo": int(open_term_no) if open_term_no is not None else None,
            "module": _required_text(module),
        }

    for row_id in sorted(rows):
        evidence = evidence_by_id.get(row_id)
        if evidence is None:
            block("FORMATION_PROVENANCE_MISSING", row_id)
            continue
        try:
            formation_mode = normalize_formation_mode(
                evidence.get("formationMode"), required=True
            )
        except ValueError:
            block("FORMATION_PROVENANCE_MODE_INVALID", row_id)
            continue

        source_system = _required_text(evidence.get("sourceSystem"))
        source_record_id = _required_text(evidence.get("sourceRecordId"))
        evidence_ref = _required_text(evidence.get("evidenceRef"))
        if not source_system or not source_record_id or not evidence_ref:
            block("FORMATION_PROVENANCE_INCOMPLETE", row_id)
            continue

        resolved_ids.add(row_id)
        mode_counts[str(formation_mode)] += 1
        source_counts[source_system] += 1

    orphan_evidence_ids = sorted(set(evidence_by_id) - set(rows))
    for row_id in orphan_evidence_ids:
        block("ORPHAN_FORMATION_PROVENANCE", row_id)

    unresolved_count = len(set(rows) - resolved_ids)
    blocker_total = sum(blocker_counts.values())
    safe = blocker_total == 0 and unresolved_count == 0
    return {
        "totalProgramCourses": len(rows),
        "explicitProvenanceCount": len(resolved_ids),
        "unresolvedProgramCourseCount": unresolved_count,
        "formationModeCounts": {
            mode: int(mode_counts[mode]) for mode in sorted(FORMATION_MODES)
        },
        "provenanceSourceCounts": dict(sorted(source_counts.items())),
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "blockerProgramCourseSamples": {
            code: blocker_samples[code] for code in sorted(blocker_samples)
        },
        "inferencePolicy": {
            "courseNameOrNature": "FORBIDDEN",
            "teachingTaskMajority": "FORBIDDEN",
            "adminFixedDefault": "FORBIDDEN",
        },
        "programCourseFormationBackfill": (
            "EXPLICIT_PROVENANCE_PROVEN"
            if safe
            else "REQUIRES_EXPLICIT_PROVENANCE"
        ),
        "migrationPreflightSafe": safe,
    }


def inventory_program_course_formation_provenance(
    db,
    *,
    tenant_id: int,
    provenance_by_program_course_id: Mapping[int | str, Mapping[str, object]] | None = None,
    sample_limit: int = _DEFAULT_SAMPLE_LIMIT,
) -> dict:
    """Return one-tenant ProgramCourse formation backfill evidence report."""
    tid = _positive_tenant_id(tenant_id)
    limit = _bounded_sample_limit(sample_limit)
    rows = db.execute(_program_course_inventory_statement(tid)).all()
    return _build_inventory(
        rows,
        provenance_by_program_course_id=provenance_by_program_course_id,
        sample_limit=limit,
    )
