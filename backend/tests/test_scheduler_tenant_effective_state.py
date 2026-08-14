"""Issue 12: business schedulers obey canonical tenant effective state."""
from __future__ import annotations

from datetime import datetime, timedelta
import inspect

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.services import tenant_effective_state_service as tenant_state


@pytest.mark.parametrize(
    "row_status,meta,business,maintenance,auth",
    [
        ("ACTIVE", {"status": "active"}, True, True, True),
        ("ACTIVE", {"status": "trial", "expireAt": (datetime.utcnow() + timedelta(days=1)).isoformat()}, True, True, True),
        ("ACTIVE", {"status": "expired"}, False, True, True),
        ("ACTIVE", {"status": "readonly"}, False, True, True),
        ("SUSPENDED", {"status": "disabled"}, False, True, False),
        ("ARCHIVED", {"status": "archived"}, False, True, False),
        ("PROVISIONING", {"status": "provisioning"}, False, True, False),
    ],
)
def test_background_policy_matrix(row_status, meta, business, maintenance, auth):
    state = tenant_state.effective_state_from_records(row_status=row_status, meta=meta, strict=True)
    policy = tenant_state._background_policy_from_state(state)
    assert policy["businessWriteAllowed"] is business
    assert policy["maintenanceAllowed"] is maintenance
    assert policy["authSecurityAllowed"] is auth


@pytest.mark.parametrize(
    "row_status,meta",
    [
        ("MYSTERY", {"status": "active"}),
        ("ACTIVE", {"status": "mystery"}),
        ("ACTIVE", {"status": "active", "expireAt": "not-a-date"}),
    ],
)
def test_invalid_effective_state_is_fail_closed(row_status, meta):
    with pytest.raises(AppException) as exc:
        tenant_state.effective_state_from_records(row_status=row_status, meta=meta, strict=True)
    assert exc.value.code == "TENANT_STATE_UNRESOLVED"


def test_candidate_enumeration_does_not_prefilter_relation_status():
    from scripts import run_scheduled_jobs as scheduler
    source = inspect.getsource(scheduler._candidate_tenant_ids)
    assert "Tenant.is_deleted.is_(False)" in source
    assert "Tenant.status" not in source


def test_unresolved_scheduler_policy_never_allows_business(monkeypatch):
    from scripts import run_scheduled_jobs as scheduler
    monkeypatch.setattr(scheduler, "_candidate_tenant_ids", lambda: [9001])
    monkeypatch.setattr(
        tenant_state, "background_execution_policy",
        lambda _tenant_id: (_ for _ in ()).throw(
            AppException("TENANT_STATE_UNRESOLVED", "bad tenant state", http_status=409)
        ),
    )
    called = []
    before = scheduler._metric("unresolved-test").tenant_skip_count
    scheduler._run_for_tenants(
        "unresolved-test", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda tid: called.append(tid),
    )
    assert called == []
    assert scheduler._metric("unresolved-test").tenant_skip_count == before + 1


def test_expired_policy_runs_maintenance_but_not_business(monkeypatch):
    from scripts import run_scheduled_jobs as scheduler
    monkeypatch.setattr(scheduler, "_candidate_tenant_ids", lambda: [9002])
    monkeypatch.setattr(
        tenant_state, "background_execution_policy",
        lambda _tenant_id: {
            "effectiveStatus": "expired",
            "businessWriteAllowed": False,
            "maintenanceAllowed": True,
            "authSecurityAllowed": True,
            "reason": "TENANT_EXPIRED_READONLY",
        },
    )
    business, maintenance = [], []
    scheduler._run_for_tenants(
        "business-expired-test", tenant_state.BACKGROUND_BUSINESS_WRITE,
        lambda tid: business.append(tid),
    )
    scheduler._run_for_tenants(
        "maintenance-expired-test", tenant_state.BACKGROUND_MAINTENANCE,
        lambda tid: maintenance.append(tid),
    )
    assert business == []
    assert maintenance == [9002]


def _set_tenant_meta(tenant_id: int, status: str, *, expire_at: str | None = None) -> None:
    from sqlalchemy import select
    from app.models import PlatformConfig, Tenant

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, tenant_id)
        assert tenant is not None
        tenant.status = "ACTIVE"
        row = db.scalar(select(PlatformConfig).where(
            PlatformConfig.tenant_id == tenant_id,
            PlatformConfig.config_type == "TENANT_META",
            PlatformConfig.config_key == "-",
            PlatformConfig.is_deleted.is_(False),
        ))
        payload = {"status": status}
        if expire_at:
            payload["expireAt"] = expire_at
        if row is None:
            row = PlatformConfig(
                tenant_id=tenant_id, config_type="TENANT_META", config_key="-",
                config_json=payload, enabled=True,
            )
            db.add(row)
        else:
            row.config_json = payload
            row.enabled = True
        db.commit()
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_expired_active_relation_does_not_apply_due_academic_change_then_active_does():
    from app.models import AaStatusChange, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_change_service as change_service
    from scripts import run_scheduled_jobs as scheduler
    from tests.support_status_change_identity import TID
    from tests.test_aa_status_change_concurrency import _ctx, _seed_change_at_final

    change_id, student_id, base_version = _seed_change_at_final()
    db = get_sessionmaker()()
    try:
        db.get(AaStatusChange, change_id).effective_date = datetime.utcnow() + timedelta(days=1)
        db.commit()
    finally:
        db.close()

    actor = _ctx("school_admin01", "SCHOOL_ADMIN")
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    set_current_user(actor)
    reviewed = change_service.review(change_id, actor, "APPROVE")
    assert reviewed["status"] == "APPROVED_PENDING_EFFECTIVE"

    db = get_sessionmaker()()
    try:
        db.get(AaStatusChange, change_id).effective_date = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    _set_tenant_meta(TID, "expired", expire_at=(datetime.utcnow() - timedelta(seconds=5)).isoformat())
    set_current_user(None)
    set_tenant(None)
    scheduler.job_academic_future_effective()

    db = get_sessionmaker()()
    try:
        change = db.get(AaStatusChange, change_id)
        student = db.get(StudentProfile, student_id)
        assert change.status == "APPROVED_PENDING_EFFECTIVE"
        assert student.student_status == "REGISTERED"
        assert int(student.version or 0) == base_version
    finally:
        db.close()

    _set_tenant_meta(TID, "active", expire_at=(datetime.utcnow() + timedelta(days=30)).isoformat())
    scheduler.job_academic_future_effective()

    db = get_sessionmaker()()
    try:
        change = db.get(AaStatusChange, change_id)
        student = db.get(StudentProfile, student_id)
        assert change.status == "EFFECTIVE"
        assert student.student_status == "SUSPENDED"
        assert int(student.version or 0) == base_version + 1
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_expired_pending_message_outbox_is_not_consumed():
    from app.models import MessageEventOutbox, Tenant
    from scripts import run_scheduled_jobs as scheduler

    tid = 1000000000000012012
    db = get_sessionmaker()()
    try:
        if db.get(Tenant, tid) is None:
            db.add(Tenant(
                id=tid, tenant_code="scheduler-expired-outbox",
                school_name="到期调度学校", short_name="到期调度",
                deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
            ))
            db.flush()
        row = MessageEventOutbox(
            tenant_id=tid, event_code="LEAVE.APPROVED",
            source_module="student-affairs", source_biz_type="TEST",
            source_biz_id=1, payload_json={"title": "x", "content": "x"},
            recipient_refs_json=[{"userId": 999999}],
            dedup_key="scheduler-expired-outbox-1", status="PENDING",
            attempt_count=0, occurred_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        row_id = int(row.id)
    finally:
        db.close()

    _set_tenant_meta(tid, "expired", expire_at=(datetime.utcnow() - timedelta(seconds=5)).isoformat())
    scheduler.job_delivery_and_outbox()

    db = get_sessionmaker()()
    try:
        row = db.get(MessageEventOutbox, row_id)
        assert row.status == "PENDING"
        assert int(row.attempt_count or 0) == 0
    finally:
        db.close()
