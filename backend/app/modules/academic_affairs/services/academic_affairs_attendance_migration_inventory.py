"""Read-only INT inventory for legacy Attendance source governance.

This module never mutates/backfills. It reports which same-tenant legacy rows have an
AA_ATTENDANCE/CREATE audit proving the historical ADMIN_MANUAL source and which remain
unresolved. A later contract migration may tighten only after this inventory is reconciled.
"""
from __future__ import annotations

from sqlalchemy import func, select


def inventory_legacy_attendance_sources(db, tenant_id: int, *, sample_limit: int = 50) -> dict:
    from app.models import AaAttendanceSession, AffairsAuditTrail

    tid = int(tenant_id)
    limit = max(1, min(int(sample_limit or 50), 200))
    legacy = [
        AaAttendanceSession.tenant_id == tid,
        AaAttendanceSession.source_type.is_(None),
    ]
    manual_audit = [
        AffairsAuditTrail.tenant_id == tid,
        AffairsAuditTrail.biz_type == "AA_ATTENDANCE",
        AffairsAuditTrail.action == "CREATE",
        AffairsAuditTrail.biz_id.is_not(None),
        AffairsAuditTrail.detail.contains("source=ADMIN_MANUAL"),
    ]

    manual_ids = select(AffairsAuditTrail.biz_id).where(*manual_audit).distinct()
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
            .filter(*manual_audit, ~AffairsAuditTrail.biz_id.in_(tenant_session_ids))
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
    }
