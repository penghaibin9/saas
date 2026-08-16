"""INT governance helpers for legacy Attendance source migration.

The inventory is read-only and repeatable. The backfill is deliberately narrow:
only a same-tenant historical AA_ATTENDANCE/CREATE audit with the exact semicolon token
``source=ADMIN_MANUAL`` can prove ``source_type=ADMIN_SPECIAL``. It never invents
source_reason/source_evidence, and it never commits the caller's transaction.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

_ADMIN_SPECIAL = "ADMIN_SPECIAL"
_MANUAL_AUDIT_TOKEN = "source=ADMIN_MANUAL"


def _manual_source_audit_condition(model):
    """Match the historical source token exactly, not ADMIN_MANUAL_* lookalikes."""
    marker = _MANUAL_AUDIT_TOKEN
    return or_(
        model.detail == marker,
        model.detail.like(f"{marker};%"),
        model.detail.like(f"%;{marker}"),
        model.detail.like(f"%;{marker};%"),
    )


def _manual_audit_filters(tenant_id: int):
    from app.models import AffairsAuditTrail

    return [
        AffairsAuditTrail.tenant_id == int(tenant_id),
        AffairsAuditTrail.biz_type == "AA_ATTENDANCE",
        AffairsAuditTrail.action == "CREATE",
        AffairsAuditTrail.biz_id.is_not(None),
        _manual_source_audit_condition(AffairsAuditTrail),
    ]


def _manual_audit_ids(tenant_id: int):
    from app.models import AffairsAuditTrail

    return select(AffairsAuditTrail.biz_id).where(*_manual_audit_filters(tenant_id)).distinct()


def inventory_legacy_attendance_sources(db, tenant_id: int, *, sample_limit: int = 50) -> dict:
    """Report unresolved legacy source rows without mutating or committing anything."""
    from app.models import AaAttendanceSession, AffairsAuditTrail

    tid = int(tenant_id)
    limit = max(1, min(int(sample_limit or 50), 200))
    legacy = [
        AaAttendanceSession.tenant_id == tid,
        AaAttendanceSession.source_type.is_(None),
    ]
    manual_ids = _manual_audit_ids(tid)
    tenant_session_ids = select(AaAttendanceSession.id).where(AaAttendanceSession.tenant_id == tid)

    total = int(db.query(func.count(AaAttendanceSession.id)).filter(*legacy).scalar() or 0)
    active = int(
        db.query(func.count(AaAttendanceSession.id))
        .filter(*legacy, AaAttendanceSession.is_deleted.is_(False))
        .scalar()
        or 0
    )
    matched = int(
        db.query(func.count(AaAttendanceSession.id))
        .filter(*legacy, AaAttendanceSession.id.in_(manual_ids))
        .scalar()
        or 0
    )

    term_totals = dict(
        db.query(AaAttendanceSession.term_code, func.count(AaAttendanceSession.id))
        .filter(*legacy)
        .group_by(AaAttendanceSession.term_code)
        .all()
    )
    term_matched = dict(
        db.query(AaAttendanceSession.term_code, func.count(AaAttendanceSession.id))
        .filter(*legacy, AaAttendanceSession.id.in_(manual_ids))
        .group_by(AaAttendanceSession.term_code)
        .all()
    )
    terms = []
    for term_code in sorted(term_totals, key=lambda value: str(value or "")):
        count = int(term_totals[term_code] or 0)
        proven = int(term_matched.get(term_code, 0) or 0)
        terms.append(
            {
                "termCode": term_code,
                "legacyRows": count,
                "manualAuditMatchedRows": proven,
                "unresolvedRows": count - proven,
            }
        )

    unresolved_ids = [
        int(row[0])
        for row in (
            db.query(AaAttendanceSession.id)
            .filter(*legacy, ~AaAttendanceSession.id.in_(manual_ids))
            .order_by(AaAttendanceSession.id.asc())
            .limit(limit)
            .all()
        )
    ]
    orphan_audit_ids = [
        int(row[0])
        for row in (
            db.query(AffairsAuditTrail.biz_id)
            .filter(
                *_manual_audit_filters(tid),
                ~AffairsAuditTrail.biz_id.in_(tenant_session_ids),
            )
            .distinct()
            .order_by(AffairsAuditTrail.biz_id.asc())
            .limit(limit)
            .all()
        )
    ]

    return {
        "tenantId": str(tid),
        "legacyRows": total,
        "activeLegacyRows": active,
        "deletedLegacyRows": total - active,
        "manualAuditMatchedRows": matched,
        "unresolvedRows": total - matched,
        "orphanManualAuditRows": len(orphan_audit_ids),
        "unresolvedSampleSessionIds": unresolved_ids,
        "orphanManualAuditSampleBizIds": orphan_audit_ids,
        "terms": terms,
        "mutationPerformed": False,
        "commitPerformed": False,
    }


def backfill_proven_legacy_admin_sources(
    db,
    tenant_id: int,
    *,
    apply: bool = False,
    sample_limit: int = 50,
    operator: str = "ACADEMIC_INT_C1",
) -> dict:
    """Backfill only the source type that historical audit evidence actually proves.

    ``apply=False`` is the default dry-run. With ``apply=True`` rows are locked and only
    ``source_type`` changes to ADMIN_SPECIAL; reason/evidence are left untouched because the
    old audit cannot prove them. The function flushes but never commits, so the caller owns
    atomic commit/rollback and can perform external reconciliation first.
    """
    from app.models import AaAttendanceSession, AffairsAuditTrail

    tid = int(tenant_id)
    limit = max(1, min(int(sample_limit or 50), 200))
    before = inventory_legacy_attendance_sources(db, tid, sample_limit=limit)
    manual_ids = _manual_audit_ids(tid)

    statement = (
        select(AaAttendanceSession)
        .where(
            AaAttendanceSession.tenant_id == tid,
            AaAttendanceSession.source_type.is_(None),
            AaAttendanceSession.id.in_(manual_ids),
        )
        .order_by(AaAttendanceSession.id.asc())
    )
    if apply:
        statement = statement.with_for_update()
    rows = list(db.scalars(statement).all())
    candidate_ids = [int(row.id) for row in rows]

    result = {
        "tenantId": str(tid),
        "mode": "APPLY" if apply else "DRY_RUN",
        "provenCandidateRows": len(rows),
        "candidateSampleSessionIds": candidate_ids[:limit],
        "sourceTypeTarget": _ADMIN_SPECIAL,
        "sourceReasonEvidenceMutated": False,
        "mutationPerformed": False,
        "commitPerformed": False,
        "before": before,
    }
    if not apply:
        result["after"] = before
        return result

    for row in rows:
        row.source_type = _ADMIN_SPECIAL
    if rows:
        db.flush()
        db.add(
            AffairsAuditTrail(
                tenant_id=tid,
                biz_type="AA_ATTENDANCE_MIGRATION",
                biz_id=None,
                action="BACKFILL_SOURCE_TYPE",
                operator=str(operator or "ACADEMIC_INT_C1")[:100],
                detail=(
                    f"proof=AA_ATTENDANCE_CREATE_ADMIN_MANUAL;"
                    f"updated={len(rows)};target=ADMIN_SPECIAL;"
                    "source_reason=UNCHANGED;source_evidence=UNCHANGED"
                )[:990],
                occurred_at=datetime.utcnow(),
            )
        )
        db.flush()

    result["mutationPerformed"] = bool(rows)
    result["after"] = inventory_legacy_attendance_sources(db, tid, sample_limit=limit)
    result["appliedRows"] = len(rows)
    return result
