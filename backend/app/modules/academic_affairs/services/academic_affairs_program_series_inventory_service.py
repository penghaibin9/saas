"""INT read-only dirty-data inventory for Program stable-series identity.

This module is intentionally internal and unrouted. It does not add ``series_key`` and
never writes historical data. Its only job is to prove whether each legacy AaProgram
row can be assigned to one linear version series from explicit ``prev_version_id``
evidence before the shared schema migration is allowed to run.

Rules:
- caller supplies an explicit positive tenant id; ambient request context is forbidden;
- one tenant-scoped AaProgram query collects all evidence; bindings are not identity;
- (major_id, grade_year, version) duplicates are reported as proof that the tuple cannot
  be used as Program identity, but are not themselves migration blockers;
- missing parent, fork, cycle, non-consecutive version, major/grade drift, invalid
  version, or a version>1 root remain fail-closed blockers;
- no inferred v1/v2 rows are fabricated for a legacy v3-only baseline.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select

_MAX_SAMPLE_LIMIT = 100
_DEFAULT_SAMPLE_LIMIT = 20


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
    """Build the single tenant-scoped read used by the inventory."""
    from app.models import AaProgram

    tid = _positive_tenant_id(tenant_id)
    return (
        select(
            AaProgram.id,
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


def _append_sample(samples: dict[str, list[str]], key: str, program_id: int, limit: int) -> None:
    bucket = samples.setdefault(key, [])
    value = str(int(program_id))
    if value not in bucket and len(bucket) < limit:
        bucket.append(value)


def _normalize_grade(value) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _build_inventory(program_rows, *, sample_limit: int = _DEFAULT_SAMPLE_LIMIT) -> dict:
    """Classify already-collected AaProgram rows without additional database I/O."""
    limit = _bounded_sample_limit(sample_limit)
    programs: dict[int, dict] = {}
    blocker_counts: Counter[str] = Counter()
    blocker_samples: dict[str, list[str]] = {}
    blocked_ids: set[int] = set()

    def block(code: str, *program_ids: int) -> None:
        unique_ids = []
        for raw in program_ids:
            pid = int(raw)
            if pid not in unique_ids:
                unique_ids.append(pid)
        if not unique_ids:
            return
        blocker_counts[code] += 1
        for pid in unique_ids:
            blocked_ids.add(pid)
            _append_sample(blocker_samples, code, pid, limit)

    for row in program_rows:
        program_id, major_id, grade_year, version, prev_version_id, status = row
        pid = int(program_id)
        if pid in programs:
            block("DUPLICATE_PROGRAM_ROW", pid)
            continue
        try:
            normalized_version = int(version)
        except (TypeError, ValueError):
            normalized_version = 0
        programs[pid] = {
            "id": pid,
            "major_id": int(major_id) if major_id is not None else None,
            "grade_year": _normalize_grade(grade_year),
            "version": normalized_version,
            "prev_version_id": int(prev_version_id) if prev_version_id is not None else None,
            "status": str(status or "").strip().upper(),
        }
        if normalized_version <= 0:
            block("INVALID_VERSION", pid)

    successors: dict[int, list[int]] = defaultdict(list)
    natural_identity_groups: dict[tuple[int | None, str | None, int], list[int]] = defaultdict(list)

    for program in programs.values():
        pid = program["id"]
        natural_identity_groups[
            (program["major_id"], program["grade_year"], program["version"])
        ].append(pid)
        parent_id = program["prev_version_id"]
        if parent_id is None:
            if program["version"] > 1:
                block("BASELINE_VERSION_WITHOUT_HISTORY", pid)
            continue
        if parent_id == pid:
            block("VERSION_CYCLE", pid)
            continue
        parent = programs.get(parent_id)
        if parent is None:
            block("PREDECESSOR_MISSING", pid)
            continue
        successors[parent_id].append(pid)
        if program["major_id"] != parent["major_id"]:
            block("MAJOR_ID_DRIFT", parent_id, pid)
        if program["grade_year"] != parent["grade_year"]:
            block("GRADE_YEAR_DRIFT", parent_id, pid)
        if program["version"] != parent["version"] + 1:
            block("VERSION_SEQUENCE_INVALID", parent_id, pid)

    for parent_id, child_ids in successors.items():
        if len(child_ids) > 1:
            block("PREDECESSOR_FORK", parent_id, *sorted(child_ids))

    # Detect arbitrary cycles in the parent graph in one pass per connected path.
    completed: set[int] = set()
    for start_id in sorted(programs):
        if start_id in completed:
            continue
        path: list[int] = []
        path_index: dict[int, int] = {}
        cursor = start_id
        while cursor in programs and cursor not in completed:
            if cursor in path_index:
                cycle_ids = path[path_index[cursor]:]
                block("VERSION_CYCLE", *cycle_ids)
                break
            path_index[cursor] = len(path)
            path.append(cursor)
            parent_id = programs[cursor]["prev_version_id"]
            if parent_id is None or parent_id not in programs:
                break
            cursor = parent_id
        completed.update(path)

    ambiguous_groups = {
        key: sorted(ids)
        for key, ids in natural_identity_groups.items()
        if len(ids) > 1
    }
    ambiguous_samples = []
    for (major_id, grade_year, version), ids in sorted(
        ambiguous_groups.items(),
        key=lambda item: (
            item[0][0] if item[0][0] is not None else -1,
            item[0][1] or "",
            item[0][2],
        ),
    )[:limit]:
        ambiguous_samples.append({
            "majorId": str(major_id) if major_id is not None else "",
            "gradeYear": grade_year or "",
            "version": int(version),
            "programIds": [str(pid) for pid in ids[:limit]],
        })

    roots = [
        pid for pid, program in programs.items()
        if program["prev_version_id"] is None
    ]
    proven_series_count = 0
    proven_program_count = 0
    visited_in_proven_series: set[int] = set()
    for root_id in sorted(roots):
        chain: list[int] = []
        cursor = root_id
        seen: set[int] = set()
        valid = True
        while True:
            if cursor in seen or cursor in blocked_ids:
                valid = False
                break
            seen.add(cursor)
            chain.append(cursor)
            child_ids = successors.get(cursor, [])
            if len(child_ids) > 1:
                valid = False
                break
            if not child_ids:
                break
            cursor = child_ids[0]
        if valid:
            proven_series_count += 1
            proven_program_count += len(chain)
            visited_in_proven_series.update(chain)

    unresolved_program_count = len(set(programs) - visited_in_proven_series)
    blocker_total = sum(blocker_counts.values())
    return {
        "totalPrograms": len(programs),
        "rootProgramCount": len(roots),
        "provenSeriesCount": proven_series_count,
        "provenProgramCount": proven_program_count,
        "unresolvedProgramCount": unresolved_program_count,
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "blockerProgramSamples": {
            key: blocker_samples[key] for key in sorted(blocker_samples)
        },
        "ambiguousNaturalIdentityGroupCount": len(ambiguous_groups),
        "ambiguousNaturalIdentitySamples": ambiguous_samples,
        "naturalIdentityPolicy": "MAJOR_GRADE_VERSION_NOT_IDENTITY",
        "bindingIdentityPolicy": "FORBIDDEN",
        "seriesKeyBackfill": "PROVABLE_PREV_VERSION_ROOT_ONLY",
        "migrationPreflightSafe": blocker_total == 0 and unresolved_program_count == 0,
    }


def inventory_legacy_program_series(
    db,
    *,
    tenant_id: int,
    sample_limit: int = _DEFAULT_SAMPLE_LIMIT,
) -> dict:
    """Return a read-only series-key migration preflight report for one tenant."""
    tid = _positive_tenant_id(tenant_id)
    limit = _bounded_sample_limit(sample_limit)
    rows = db.execute(_program_series_inventory_statement(tid)).all()
    return _build_inventory(rows, sample_limit=limit)
