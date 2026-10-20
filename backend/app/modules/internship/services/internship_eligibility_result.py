"""资格认定的只读投影；学生只收到明确标记为公开的本次意见。"""
from __future__ import annotations

from sqlalchemy import select

from app.models import InternshipAuditTrail
from app.services.db_service import _iso


def eligibility_result(db, record, *, include_internal=False):
    review = db.scalar(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == record.tenant_id,
        InternshipAuditTrail.target_type == "INTERN_STUDENT",
        InternshipAuditTrail.target_id == record.id,
        InternshipAuditTrail.action == "ELIGIBILITY",
    ).order_by(InternshipAuditTrail.occurred_at.desc(), InternshipAuditTrail.id.desc()).limit(1))
    detail = (review.detail_json or {}) if review else {}
    # A legacy/stale audit entry cannot describe a different current result.
    matches = detail.get("status") == record.eligibility_status
    published = matches and detail.get("studentVisible") is True
    return {
        "status": record.eligibility_status or "PENDING",
        "label": {"PENDING": "待认定", "QUALIFIED": "资格合格",
                  "UNQUALIFIED": "资格不合格"}.get(record.eligibility_status, "待认定"),
        "reason": str(detail.get("reason") or "") if matches and (include_internal or published) else "",
        "reviewedAt": _iso(review.occurred_at) if review and matches else "",
        "studentVisible": bool(published),
    }
