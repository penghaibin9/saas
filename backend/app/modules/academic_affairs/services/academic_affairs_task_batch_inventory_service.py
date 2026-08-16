"""A-W3/INT read-only inventory for editable TeachingTaskBatch scope conflicts.

This module deliberately owns no schema and performs no repair. It gives the
future INT migration an executable preflight before adding a database unique
constraint for the invariant:

    tenant + term + management scope -> at most one editable batch

Both DRAFT and RETURNED are editable states. Historical duplicates are
reported fail-closed and must be reconciled explicitly; this service never
chooses a winner or mutates a batch.

MySQL unique indexes allow multiple NULL values. Therefore the future unique
constraint must not rely on nullable ``college_id`` to distinguish school
scope. Editable rows use a canonical non-null ``editable_scope_key`` and
non-editable rows keep that key NULL, allowing historical terminal batches
while still making the editable school scope genuinely unique.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

_EDITABLE_BATCH_STATUSES = ("DRAFT", "RETURNED")
_NON_EDITABLE_BATCH_STATUSES = ("COLLEGE_CONFIRMED", "APPROVED", "ARCHIVED")
_BATCH_STATUSES = frozenset((*_EDITABLE_BATCH_STATUSES, *_NON_EDITABLE_BATCH_STATUSES))
_DEFAULT_SAMPLE_LIMIT = 20
_MAX_SAMPLE_LIMIT = 100
_EDITABLE_SCOPE_KEY_VERSION = "V1"


def _positive_tenant_id(value) -> int:
    tenant_id = int(value or 0)
    if tenant_id <= 0:
        raise ValueError("tenant_id must be a positive integer")
    return tenant_id


def _positive_scope_id(value, *, name: str) -> int:
    identifier = int(value or 0)
    if identifier <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return identifier


def _validated_scope_ids(term_id: int, college_id: int | None) -> tuple[int, int | None]:
    term_id = _positive_scope_id(term_id, name="term_id")
    if college_id is None:
        return term_id, None
    return term_id, _positive_scope_id(college_id, name="college_id")


def canonical_editable_scope_key(term_id: int, college_id: int | None) -> str:
    """Return the exact non-null key reserved for an editable management scope.

    ``tenant_id`` intentionally stays outside the string because the future DB
    constraint is ``UNIQUE(tenant_id, editable_scope_key)``. School scope uses
    an explicit token instead of SQL NULL so MySQL cannot admit duplicates.
    """
    term_id, college_id = _validated_scope_ids(term_id, college_id)
    if college_id is None:
        return f"{_EDITABLE_SCOPE_KEY_VERSION}:TERM:{term_id}:SCHOOL"
    return f"{_EDITABLE_SCOPE_KEY_VERSION}:TERM:{term_id}:COLLEGE:{college_id}"


def editable_scope_key_for_status(term_id: int, college_id: int | None, status: str) -> str | None:
    """Return the DB key a canonical batch writer must persist for ``status``.

    Only DRAFT/RETURNED reserve the management scope. Non-editable states use
    SQL NULL so multiple historical/terminal batches remain legal. Unknown
    states or malformed scope identifiers fail closed instead of silently
    escaping the uniqueness invariant.
    """
    normalized = str(status or "").strip().upper()
    if normalized not in _BATCH_STATUSES:
        raise ValueError(f"unsupported teaching task batch status: {normalized or '<empty>'}")
    term_id, college_id = _validated_scope_ids(term_id, college_id)
    if normalized in _EDITABLE_BATCH_STATUSES:
        return canonical_editable_scope_key(term_id, college_id)
    return None


def _sample_limit(value) -> int:
    limit = int(value or _DEFAULT_SAMPLE_LIMIT)
    return max(1, min(limit, _MAX_SAMPLE_LIMIT))


def editable_batch_inventory_statement(tenant_id: int):
    """Return the single bounded-surface read statement used by the inventory."""
    from app.models import AaTeachingTaskBatch

    tenant_id = _positive_tenant_id(tenant_id)
    return (
        select(
            AaTeachingTaskBatch.id,
            AaTeachingTaskBatch.term_id,
            AaTeachingTaskBatch.college_id,
            AaTeachingTaskBatch.status,
        )
        .where(
            AaTeachingTaskBatch.tenant_id == tenant_id,
            AaTeachingTaskBatch.status.in_(_EDITABLE_BATCH_STATUSES),
            AaTeachingTaskBatch.is_deleted.is_(False),
        )
        .order_by(
            AaTeachingTaskBatch.term_id.asc(),
            AaTeachingTaskBatch.college_id.asc(),
            AaTeachingTaskBatch.id.asc(),
        )
    )


def _row_value(row, name: str, index: int):
    mapping = getattr(row, "_mapping", None)
    if mapping is not None and name in mapping:
        return mapping[name]
    if hasattr(row, name):
        return getattr(row, name)
    return row[index]


def inventory_editable_batch_scope_conflicts(db, tenant_id: int, *, sample_limit: int = 20) -> dict:
    """Inventory duplicate editable scopes with one tenant-scoped read query.

    The result is intentionally migration-oriented: it returns counts plus
    bounded batch-id/status samples, but never returns student/teacher data and
    never calls ``add``/``flush``/``commit``.
    """
    tenant_id = _positive_tenant_id(tenant_id)
    limit = _sample_limit(sample_limit)
    rows = db.execute(editable_batch_inventory_statement(tenant_id)).all()

    grouped: dict[tuple[int, int | None], list[tuple[int, str]]] = defaultdict(list)
    for row in rows:
        batch_id = int(_row_value(row, "id", 0))
        term_id = int(_row_value(row, "term_id", 1))
        college_raw = _row_value(row, "college_id", 2)
        college_id = int(college_raw) if college_raw is not None else None
        status = str(_row_value(row, "status", 3) or "").strip().upper()
        grouped[(term_id, college_id)].append((batch_id, status))

    conflicts = []
    conflict_batch_count = 0
    for (term_id, college_id), batches in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], -1 if item[0][1] is None else item[0][1]),
    ):
        if len(batches) <= 1:
            continue
        conflict_batch_count += len(batches)
        sample = batches[:limit]
        conflicts.append({
            "termId": str(term_id),
            "collegeId": str(college_id) if college_id is not None else "",
            "scope": f"COLLEGE:{college_id}" if college_id is not None else "SCHOOL",
            "editableScopeKey": canonical_editable_scope_key(term_id, college_id),
            "editableBatchCount": len(batches),
            "batchIds": [str(batch_id) for batch_id, _status in sample],
            "batchStatuses": [status for _batch_id, status in sample],
            "sampleTruncated": len(batches) > len(sample),
        })

    return {
        "tenantId": str(tenant_id),
        "scopeKeyVersion": _EDITABLE_SCOPE_KEY_VERSION,
        "editableBatchCount": len(rows),
        "conflictScopeCount": len(conflicts),
        "conflictBatchCount": conflict_batch_count,
        "migrationPreflightSafe": not conflicts,
        "conflicts": conflicts,
    }
