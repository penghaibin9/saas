"""INT tenant-scoped adapter for canonical Program series inventory.

The Program version-graph algorithm lives only in
``academic_affairs_program_series_inventory.inventory_program_series``.  This
module owns the database boundary: one explicit-tenant AaProgram query, lossless
row mapping, and bounded presentation metadata.  It must never reimplement
parent/fork/cycle/version-chain classification or compute a second backfill map.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select

from .academic_affairs_program_series_inventory import inventory_program_series

_MAX_SAMPLE_LIMIT = 100
_DEFAULT_SAMPLE_LIMIT = 20
SERIES_BACKFILL_POLICY = "CANONICAL_PROPOSED_BACKFILL"


def _positive_tenant_id(value) -> int:
    try:
        tenant_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("tenant_id must be a positive integer") from exc
    if tenant_id <= 0:
        raise ValueError("tenant_id must be a positive integer")
    return tenant_id


def _bounded_sample_limit(value) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("sample_limit must be an integer") from exc
    if limit < 1 or limit > _MAX_SAMPLE_LIMIT:
        raise ValueError(f"sample_limit must be between 1 and {_MAX_SAMPLE_LIMIT}")
    return limit


def _program_series_inventory_statement(tenant_id: int):
    """Build the single tenant-scoped read used by the inventory adapter."""
    from app.models import AaProgram

    tid = _positive_tenant_id(tenant_id)
    return (
        select(
            AaProgram.id,
            AaProgram.tenant_id,
            AaProgram.major_id,
            AaProgram.grade_year,
            AaProgram.version,
            AaProgram.prev_version_id,
            AaProgram.status,
        )
        .where(
            AaProgram.tenant_id == tid,
            AaProgram.is_deleted.is_(False),
        )
        .order_by(AaProgram.id.asc())
    )


def _canonical_rows(program_rows) -> list[dict]:
    rows: list[dict] = []
    for raw in program_rows:
        program_id, tenant_id, major_id, grade_year, version, prev_version_id, status = raw
        rows.append({
            "programId": program_id,
            "tenantId": tenant_id,
            "majorId": major_id,
            "gradeYear": grade_year,
            "version": version,
            "prevVersionId": prev_version_id,
            # Status is not series identity, but retaining it as an ignored extra
            # proves the canonical classifier does not accidentally depend on it.
            "status": status,
        })
    return rows


def _append_sample(samples: dict[str, list[str]], key: str, program_id: object, limit: int) -> None:
    try:
        value = str(int(program_id))
    except (TypeError, ValueError):
        return
    bucket = samples.setdefault(key, [])
    if value not in bucket and len(bucket) < limit:
        bucket.append(value)


def _natural_identity_summary(rows: list[dict], *, sample_limit: int) -> tuple[int, list[dict]]:
    groups: dict[tuple[object, str, object], list[object]] = defaultdict(list)
    for row in rows:
        groups[(
            row.get("majorId"),
            str(row.get("gradeYear") or "").strip(),
            row.get("version"),
        )].append(row.get("programId"))
    ambiguous = {
        key: values for key, values in groups.items()
        if len(values) > 1
    }
    samples = []
    for (major_id, grade_year, version), program_ids in sorted(
        ambiguous.items(),
        key=lambda item: (
            int(item[0][0]) if item[0][0] is not None else -1,
            item[0][1],
            int(item[0][2]) if item[0][2] is not None else -1,
        ),
    )[:sample_limit]:
        samples.append({
            "majorId": str(major_id) if major_id is not None else "",
            "gradeYear": grade_year,
            "version": int(version),
            "programIds": [str(int(value)) for value in program_ids[:sample_limit]],
        })
    return len(ambiguous), samples


def _build_inventory(program_rows, *, sample_limit: int = _DEFAULT_SAMPLE_LIMIT) -> dict:
    """Delegate graph truth to the canonical pure classifier and add summaries."""
    limit = _bounded_sample_limit(sample_limit)
    rows = _canonical_rows(program_rows)
    canonical = inventory_program_series(rows)

    blocker_counts = Counter(
        str(item.get("code") or "") for item in canonical.get("blockers") or ()
        if str(item.get("code") or "")
    )
    blocker_samples: dict[str, list[str]] = {}
    for issue in canonical.get("blockers") or ():
        code = str(issue.get("code") or "")
        for program_id in issue.get("programIds") or ():
            _append_sample(blocker_samples, code, program_id, limit)

    ambiguous_count, ambiguous_samples = _natural_identity_summary(rows, sample_limit=limit)
    proposed = [dict(item) for item in canonical.get("proposedBackfill") or ()]
    total_programs = int(canonical.get("totalRows") or 0)
    root_program_count = sum(1 for row in rows if row.get("prevVersionId") in (None, "", 0, "0"))
    safe = bool(canonical.get("migrationPreflightSafe"))

    # Preserve bounded operator-facing summary fields for existing diagnostics,
    # but never derive migration truth from them. ``proposedBackfill`` below is
    # the only Program->series mapping a migration may consume.
    return {
        **canonical,
        "totalPrograms": total_programs,
        "rootProgramCount": root_program_count,
        "provenSeriesCount": int(canonical.get("rootCount") or 0) if safe else 0,
        "provenProgramCount": len(proposed),
        "unresolvedProgramCount": max(total_programs - len(proposed), 0),
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "blockerProgramSamples": {
            key: blocker_samples[key] for key in sorted(blocker_samples)
        },
        "ambiguousNaturalIdentityGroupCount": ambiguous_count,
        "ambiguousNaturalIdentitySamples": ambiguous_samples,
        "naturalIdentityPolicy": "MAJOR_GRADE_VERSION_NOT_IDENTITY",
        "bindingIdentityPolicy": "FORBIDDEN",
        "seriesKeyBackfill": SERIES_BACKFILL_POLICY,
        "canonicalClassifier": "inventory_program_series",
    }


def inventory_legacy_program_series(
    db,
    *,
    tenant_id: int,
    sample_limit: int = _DEFAULT_SAMPLE_LIMIT,
) -> dict:
    """Return one-query canonical series-key migration evidence for one tenant."""
    tid = _positive_tenant_id(tenant_id)
    limit = _bounded_sample_limit(sample_limit)
    rows = db.execute(_program_series_inventory_statement(tid)).all()
    return _build_inventory(rows, sample_limit=limit)
