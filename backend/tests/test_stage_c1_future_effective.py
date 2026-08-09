"""Stage C1 approval != application contracts for future-effective status changes."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import academic_affairs_change_service as change_service
from app.modules.academic_affairs.services import academic_affairs_change_temporal_guard as temporal_guard
from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
    resolve_student_academic_fact,
)
from tests.support_status_change_identity import TID
from tests.test_aa_status_change_concurrency import _ctx, _seed_change_at_final


def _activate():
    user = _ctx("school_admin01", "SCHOOL_ADMIN")
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    set_current_user(user)
    return user


@pytest.mark.usefixtures("db_mode")
def test_future_final_approval_does_not_change_profile_until_due_then_applies_once():
    from app.models import AaStatusChange, StudentProfile

    change_id, student_id, base_version = _seed_change_at_final()
    future_at = datetime.utcnow() + timedelta(days=1)
    db = get_sessionmaker()()
    try:
        change = db.get(AaStatusChange, change_id)
        change.effective_date = future_at
        db.commit()
    finally:
        db.close()

    user = _activate()
    result = change_service.review(change_id, user, "APPROVE")
    assert result["status"] == "APPROVED_PENDING_EFFECTIVE"
    assert result["effectiveDate"]

    db = get_sessionmaker()()
    try:
        student = db.get(StudentProfile, student_id)
        change = db.get(AaStatusChange, change_id)
        assert student.student_status == "REGISTERED"
        assert int(student.version or 0) == base_version
        assert change.status == "APPROVED_PENDING_EFFECTIVE"
        assert resolve_student_academic_fact(db, student_id).version_no == 1

        # Move the planned time to now to deterministically exercise the worker without sleep.
        due_at = datetime.utcnow()
        change.effective_date = due_at
        db.commit()
    finally:
        db.close()

    _activate()
    applied = temporal_guard.apply_one_due_change(change_id)
    assert applied["status"] == "EFFECTIVE"

    db = get_sessionmaker()()
    try:
        student = db.get(StudentProfile, student_id)
        change = db.get(AaStatusChange, change_id)
        assert student.student_status == "SUSPENDED"
        assert int(student.version or 0) == base_version + 1
        assert change.status == "EFFECTIVE"
        facts = db.query(type(resolve_student_academic_fact(db, student_id))).filter_by(
            tenant_id=TID, student_id=student_id
        ).order_by("version_no").all()
        assert len(facts) == 2
        assert facts[0].valid_to == due_at
        assert facts[1].valid_from == due_at
    finally:
        db.close()

    _activate()
    replay = temporal_guard.apply_one_due_change(change_id)
    assert replay["status"] == "SKIPPED"

    db = get_sessionmaker()()
    try:
        from app.models.academic_affairs_student_fact import StudentAcademicFact
        assert db.query(StudentAcademicFact).filter(
            StudentAcademicFact.tenant_id == TID,
            StudentAcademicFact.student_id == student_id,
        ).count() == 2
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_scheduled_router_is_registered_as_formal_extension():
    from app.modules.academic_affairs.routers.academic_affairs_bundle import build_router

    paths = {route.path for route in build_router().routes}
    assert "/academic-affairs/status-changes/scheduled" in paths


def test_future_effective_parser_rejects_past_or_invalid_values():
    with pytest.raises(Exception):
        temporal_guard._parse_future_effective("not-a-date")
    with pytest.raises(Exception):
        temporal_guard._parse_future_effective((datetime.utcnow() - timedelta(seconds=1)).isoformat())
    future = datetime.utcnow() + timedelta(days=2)
    parsed = temporal_guard._parse_future_effective(future.isoformat())
    assert parsed > datetime.utcnow()
