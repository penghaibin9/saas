"""A-W1 compatibility proof for historical SYS-12 data without a Tenant parent row.

Production schools normally have ``t_tenant``.  Existing SYS-12 MySQL regression fixtures and
some migration-era datasets can still contain valid ``AaTerm`` rows under a tenant id whose
Tenant parent is absent.  A-C1 must keep those transitions serialized instead of weakening or
breaking the mature calendar state machine.
"""
from datetime import datetime


def test_governance_activation_falls_back_to_term_anchor_when_tenant_parent_is_absent(db_mode):
    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models import AaTerm, Tenant
    from app.services import academic_calendar_service as calendar

    orphan_tenant = 1000000000000000777
    db = get_sessionmaker()()
    try:
        assert db.get(Tenant, orphan_tenant) is None
        term = AaTerm(
            tenant_id=orphan_tenant,
            year_code="2097-2098",
            term_no=1,
            term_name="A-W1 历史孤立租户学期",
            start_date=datetime(2097, 9, 1),
            end_date=datetime(2098, 1, 20),
            teaching_weeks=20,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.commit()
        db.refresh(term)
        term_id = int(term.id)
    finally:
        db.close()

    enrolled = calendar.enroll_term(term_id, tenant_id=orphan_tenant)
    validated = calendar.transition(
        term_id,
        "VALIDATED",
        reason="A-W1 历史兼容验收",
        expected_version=int(enrolled["version"]),
        tenant_id=orphan_tenant,
    )
    activated = calendar.transition(
        term_id,
        "ACTIVE",
        reason="A-W1 历史兼容验收",
        expected_version=int(validated["version"]),
        tenant_id=orphan_tenant,
    )

    assert activated["governanceStatus"] == "ACTIVE"
    assert calendar.resolve_current(tenant_id=orphan_tenant)["termId"] == str(term_id)

    db = get_sessionmaker()()
    try:
        current_count = db.scalar(
            select(func.count(AaTerm.id)).where(
                AaTerm.tenant_id == orphan_tenant,
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            )
        )
        assert int(current_count or 0) == 1
    finally:
        db.close()
