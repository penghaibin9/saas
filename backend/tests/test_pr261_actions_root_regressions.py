"""PR261: real-MySQL first-write, ownership and transaction regressions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest

from test_aa_grade_identity_head_concurrency import identity, _student, _session
from test_aa_effective_grade_policy_contract import (
    TID, _activate, _new_term, _policies, policy_service,
)
from test_internship_v93_batch2_remaining_first_create import _seed, _admin_ctx, ADMIN_USER


def _platform_owner_headers() -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "pr261-review-owner",
        "realName": "PR261合并审计",
        "userType": "PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "tenantId": "0",
        "tid": "platform",
        "activeContextId": "ctx-pr261-review",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _commercial_trial_tenant(tenant_id: int, code: str) -> None:
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import platform_service

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant is None:
            tenant = Tenant(
                id=int(tenant_id), tenant_code=code,
                school_name=f"PR261商业授权回归-{code}", status="ACTIVE",
            )
            db.add(tenant)
        else:
            tenant.status = "ACTIVE"
            tenant.is_deleted = False
        db.commit()
    finally:
        db.close()
    platform_service.put_config_json(tenant_id, "TENANT_META", "-", {
        "status": "trial", "packageCode": "trial", "environment": "test",
    })


@pytest.mark.parametrize("broken_link", ["foreign", "deleted", "missing"])
def test_record_scope_rejects_invalid_student_owner(db_mode, broken_link):
    from app.core.exceptions import AppException
    from app.models import InternshipRecord, StudentProfile, Tenant
    from app.modules.internship.services.internship_scope import assert_internship_record_scope

    with _session() as db:
        ids = _seed(db)
        rec = db.get(InternshipRecord, ids["internship"])
        student = db.get(StudentProfile, rec.student_id)
        if broken_link == "foreign":
            db.add(Tenant(id=TID + 99, tenant_code="pr261-foreign-student", school_name="隔离测试学校"))
            db.flush()
            student.tenant_id = TID + 99
        elif broken_link == "deleted":
            student.is_deleted = True
        else:
            rec.student_id = 8999999999999999999
        db.commit()
    _admin_ctx()
    with _session() as db, pytest.raises(AppException) as caught:
        assert_internship_record_scope(db, ids["internship"], ADMIN_USER, "测试操作", lock=True)
    assert caught.value.http_status == 404


def test_reentrant_allocation_preserves_pending_counter(identity, db_mode):
    """The upsert/read must not overwrite an uncommitted ORM counter on re-entry."""
    from app.models import AaGradeIdentityHead
    with _session() as db:
        acad = _student(db, "GI_REENTRY")
        db.commit()
        acad_id = acad.id
        assert identity.next_study_attempt_no(db, acad_id, "GI_REENTRY") == 1
        assert identity.next_study_attempt_no(db, acad_id, "GI_REENTRY") == 2
        db.commit()
    with _session() as db:
        row = db.query(AaGradeIdentityHead).filter(
            AaGradeIdentityHead.tenant_id == TID,
            AaGradeIdentityHead.acad_student_id == acad_id,
            AaGradeIdentityHead.course_code == "GI_REENTRY",
        ).one()
        assert row.current_attempt_no == 2


def test_first_identity_creation_rolls_back_with_caller(identity, db_mode):
    """No hidden commit in the allocator: an outer failure leaves no head."""
    from app.models import AaGradeIdentityHead
    with _session() as db:
        acad = _student(db, "GI_ROLLBACK")
        db.commit()
        acad_id = acad.id
        assert identity.next_study_attempt_no(db, acad_id, "GI_ROLLBACK") == 1
        db.rollback()
    with _session() as db:
        assert db.query(AaGradeIdentityHead).filter(
            AaGradeIdentityHead.tenant_id == TID,
            AaGradeIdentityHead.acad_student_id == acad_id,
            AaGradeIdentityHead.course_code == "GI_ROLLBACK",
        ).count() == 0
        assert identity.next_study_attempt_no(db, acad_id, "GI_ROLLBACK") == 1
        db.commit()


def test_soft_deleted_identity_is_not_recreated_or_reset(identity, db_mode):
    from app.core.exceptions import AppException
    from app.models import AaGradeIdentityHead
    with _session() as db:
        acad = _student(db, "GI_DELETED")
        db.add(AaGradeIdentityHead(tenant_id=TID, acad_student_id=acad.id,
            course_code="GI_DELETED", current_attempt_no=8, is_deleted=True))
        db.commit()
        with pytest.raises(AppException) as caught:
            identity.next_study_attempt_no(db, acad.id, "GI_DELETED")
        assert caught.value.code == "DATA_CONFLICT"
        db.rollback()
        row = db.query(AaGradeIdentityHead).filter(
            AaGradeIdentityHead.tenant_id == TID,
            AaGradeIdentityHead.acad_student_id == acad.id,
            AaGradeIdentityHead.course_code == "GI_DELETED",
        ).one()
        assert row.is_deleted is True and row.current_attempt_no == 8


@pytest.mark.usefixtures("db_mode")
@pytest.mark.parametrize("repeat", range(3))
def test_concurrent_publications_share_version_chain_across_scopes(repeat):
    """One policy code can span terms; each successful publication gets a new version."""
    _activate()
    term_id = _new_term()
    barrier = Barrier(2)

    def publish(scope):
        _activate()
        barrier.wait(timeout=10)
        return policy_service.activate_grade_policy(None, {
            "attemptStrategy": "LATEST_ATTEMPT", "policyCode": "CROSS_SCOPE_RACE",
            "effectiveFromTermId": scope,
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(publish, scope) for scope in [None, term_id]]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(row["policyVersion"] for row in results) == [1, 2]
    active = [row for row in _policies() if row.status == "ACTIVE"]
    assert len(active) == 2
    assert {row.active_scope_key for row in active} == {"BASE", str(term_id)}


def test_paid_order_marker_does_not_grant_before_service_start(db_mode):
    """A materialized paid marker cannot bypass the order's future service window."""
    from app.db.session import get_sessionmaker
    from app.models import PlatformOrder
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import platform_service

    tenant_id = 1000000000000096261
    _commercial_trial_tenant(tenant_id, "pr261-future-paid-window")
    created = platform_service.create_order({
        "tenantId": str(tenant_id), "packageCode": "professional",
        "orderType": "NEW", "durationDays": 30, "amount": 1,
        "remark": "PR261 paid service-window regression",
    })
    paid = platform_service.order_action(
        created["orderNo"], "mark-paid",
        expected_version=int(created["version"]), reason="PR261订单入账回归测试",
    )
    if paid.get("repairTaskRequired"):
        paid = platform_service.order_action(
            created["orderNo"], "repair-activation",
            expected_version=int(paid["version"]), reason="PR261订单激活修复回归",
        )
    assert paid["tenantActivated"] is True

    db = get_sessionmaker()()
    try:
        order = db.query(PlatformOrder).filter(
            PlatformOrder.tenant_id == tenant_id,
            PlatformOrder.order_no == created["orderNo"],
        ).one()
        order.start_at = datetime.utcnow() + timedelta(days=1)
        db.commit()
    finally:
        db.close()

    state = commercial.commercial_state(tenant_id)
    assert state["verified"] is False
    assert state["authoritySource"] == "PAID_ORDER_SERVICE_NOT_STARTED"
    assert state["features"]["internship"] is False
    assert commercial.feature_enabled(tenant_id, "internship") is False


def test_future_same_package_renewal_keeps_current_paid_coverage(db_mode):
    """Prepaying the next term must not turn off the package before renewal starts."""
    from app.db.session import get_sessionmaker
    from app.models import PlatformOrder
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import platform_service

    tenant_id = 1000000000000096264
    _commercial_trial_tenant(tenant_id, "pr261-renewal-continuity")

    first = platform_service.create_order({
        "tenantId": str(tenant_id), "packageCode": "professional",
        "orderType": "NEW", "durationDays": 30, "amount": 1,
        "remark": "PR261 current paid coverage",
    })
    first_paid = platform_service.order_action(
        first["orderNo"], "mark-paid",
        expected_version=int(first["version"]), reason="PR261首期订单入账",
    )
    if first_paid.get("repairTaskRequired"):
        first_paid = platform_service.order_action(
            first["orderNo"], "repair-activation",
            expected_version=int(first_paid["version"]), reason="PR261首期激活修复",
        )
    assert first_paid["tenantActivated"] is True
    assert commercial.commercial_state(tenant_id)["verified"] is True

    renewal = platform_service.create_order({
        "tenantId": str(tenant_id), "packageCode": "professional",
        "orderType": "RENEW", "durationDays": 30, "amount": 1,
        "remark": "PR261 prepaid renewal continuity",
    })
    renewal_paid = platform_service.order_action(
        renewal["orderNo"], "mark-paid",
        expected_version=int(renewal["version"]), reason="PR261续费订单提前入账",
    )
    if renewal_paid.get("repairTaskRequired"):
        renewal_paid = platform_service.order_action(
            renewal["orderNo"], "repair-activation",
            expected_version=int(renewal_paid["version"]), reason="PR261续费激活修复",
        )
    assert renewal_paid["tenantActivated"] is True

    db = get_sessionmaker()()
    try:
        renewal_row = db.query(PlatformOrder).filter(
            PlatformOrder.tenant_id == tenant_id,
            PlatformOrder.order_no == renewal["orderNo"],
        ).one()
        assert renewal_row.start_at is not None and renewal_row.start_at > datetime.now()
    finally:
        db.close()

    state = commercial.commercial_state(tenant_id)
    assert state["verified"] is True
    assert state["authoritySource"] == "PAID_ORDER"
    assert state["commercialOrderNo"] == renewal["orderNo"]
    assert state["features"]["internship"] is True


def test_controlled_exception_stops_granting_after_tenant_disable(db_mode):
    """Approval evidence cannot revive features after the hard tenant state is inactive."""
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import tenant_effective_state_service as lifecycle

    tenant_id = 1000000000000096262
    _commercial_trial_tenant(tenant_id, "pr261-disabled-exception")
    current = lifecycle.get_effective_state(tenant_id, strict=True)
    converted = lifecycle.apply_transition(
        tenant_id, "convert-to-paid",
        reason="PR261受控例外授权建立",
        expected_version=int(current["version"]),
        payload={
            "packageCode": "professional", "durationDays": 30,
            "exceptionGrantType": "SPECIAL_APPROVAL",
            "approvalRef": "APPROVAL-PR261-INACTIVE",
        },
    )
    active_state = commercial.commercial_state(tenant_id)
    assert active_state["verified"] is True
    assert active_state["authoritySource"] == "CONTROLLED_EXCEPTION"

    lifecycle.apply_transition(
        tenant_id, "disable",
        reason="PR261停用受控例外租户",
        expected_version=int(converted["version"]), payload={},
    )
    inactive_state = commercial.commercial_state(tenant_id)
    assert inactive_state["verified"] is False
    assert inactive_state["authoritySource"] == "CONTROLLED_EXCEPTION_TENANT_INACTIVE"
    assert inactive_state["features"]["internship"] is False


@pytest.mark.parametrize("action,payload", [
    ("change-package", {"packageCode": "professional"}),
    ("quota", {"storageLimitMb": 4096}),
])
def test_generic_package_and_quota_transition_rejects_even_exception_evidence(client, db_mode, action, payload):
    """The generic transition surface must not advertise an exception path its authority rejects."""
    tenant_id = 1000000000000096263
    _commercial_trial_tenant(tenant_id, "pr261-generic-commercial-write")
    response = client.post(
        f"/api/v1/platform/tenants/{tenant_id}/transitions/{action}",
        headers=_platform_owner_headers(),
        json={
            **payload,
            "expectedVersion": 1,
            "reason": "PR261通用商业写入口拒绝",
            "exceptionGrantType": "SPECIAL_APPROVAL",
            "approvalRef": "APPROVAL-PR261-GENERIC",
        },
    )
    body = response.json()
    assert response.status_code == 409, body
    assert body["bizCode"] == "COMMERCIAL_ORDER_REQUIRED"
    assert body["details"]["genericTransitionDisabled"] is True
