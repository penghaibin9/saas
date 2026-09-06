from __future__ import annotations

from app.core.security import create_access_token


def _owner_headers() -> dict[str, str]:
    token = create_access_token({
        "userId": "w1-owner",
        "realName": "W1平台主管",
        "userType": "PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "tenantId": "0",
        "tid": "platform",
        "activeContextId": "ctx-w1",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _ensure_tenant(tenant_id: int, code: str) -> None:
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, int(tenant_id))
        if tenant is None:
            db.add(Tenant(
                id=int(tenant_id), tenant_code=code,
                school_name=f"W1商业授权测试学校-{code}", status="ACTIVE",
            ))
            db.commit()
    finally:
        db.close()


def _trial(tenant_id: int) -> None:
    from app.services import platform_service

    platform_service.put_config_json(tenant_id, "TENANT_META", "-", {
        "status": "trial", "packageCode": "trial", "environment": "test",
    })


def test_w1_generic_features_write_is_rejected_by_canonical_router(client, db_mode):
    response = client.put(
        "/api/v1/platform/tenants/1000000000000000001/features",
        headers=_owner_headers(),
        json={"internship": True},
    )
    body = response.json()
    assert response.status_code == 409
    assert body["bizCode"] == "COMMERCIAL_AUTHORITY_REQUIRED"


def test_w1_generic_package_or_quota_transition_requires_paid_order(client, db_mode):
    for action, payload in (
        ("change-package", {"packageCode": "professional", "expectedVersion": 1, "reason": "普通改套餐"}),
        ("quota", {"storageLimitMb": 2048, "expectedVersion": 1, "reason": "普通改额度"}),
    ):
        response = client.post(
            f"/api/v1/platform/tenants/1000000000000000001/transitions/{action}",
            headers=_owner_headers(),
            json=payload,
        )
        body = response.json()
        assert response.status_code == 409, body
        assert body["bizCode"] == "COMMERCIAL_ORDER_REQUIRED"


def test_w1_legacy_features_are_evidence_only_and_cannot_expand_trial(db_mode):
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import platform_service

    tenant_id = 1000000000000096101
    _ensure_tenant(tenant_id, "w1-legacy-evidence")
    _trial(tenant_id)
    # apiAccess is false in the trial package. The retired FEATURES row tries to
    # grant it; runtime must ignore that write and show only reconciliation drift.
    platform_service.put_config_json(tenant_id, "FEATURES", "-", {"apiAccess": True})

    projection = commercial.features_projection(tenant_id)
    assert projection["authoritySource"] == "TRIAL"
    assert projection["commercialVerified"] is True
    assert projection["features"]["apiAccess"] is False
    assert projection["legacyOverride"] == {"apiAccess": True}
    assert projection["legacyOverrideReadOnly"] is True
    assert projection["legacyDrift"]["apiAccess"] == {"commercial": False, "legacy": True}
    assert projection["repairRequired"] is True


def test_w1_formal_package_code_without_paid_order_fails_closed(db_mode):
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import platform_service

    tenant_id = 1000000000000096102
    _ensure_tenant(tenant_id, "w1-no-order")
    platform_service.put_config_json(tenant_id, "TENANT_META", "-", {
        "status": "active", "packageCode": "professional", "environment": "test",
    })
    platform_service.put_config_json(tenant_id, "FEATURES", "-", {"internship": True})

    state = commercial.commercial_state(tenant_id)
    assert state["verified"] is False
    assert state["authoritySource"] == "COMMERCIAL_ORDER_REQUIRED"
    assert state["features"]["internship"] is False
    assert commercial.feature_enabled(tenant_id, "internship") is False


def test_w1_paid_order_materializes_formal_entitlement(db_mode):
    from app.services import commercial_entitlement_authority_service as commercial
    from app.services import platform_service

    tenant_id = 1000000000000096103
    _ensure_tenant(tenant_id, "w1-paid-order")
    _trial(tenant_id)
    created = platform_service.create_order({
        "tenantId": str(tenant_id),
        "packageCode": "professional",
        "orderType": "NEW",
        "durationDays": 30,
        "amount": 1,
        "remark": "W1 paid-order authority regression",
    })
    paid = platform_service.order_action(
        created["orderNo"], "mark-paid",
        expected_version=int(created["version"]),
        reason="W1真实订单入账测试",
    )
    if paid.get("repairTaskRequired"):
        paid = platform_service.order_action(
            created["orderNo"], "repair-activation",
            expected_version=int(paid["version"]),
            reason="W1修复订单激活测试",
        )
    assert paid["tenantActivated"] is True

    state = commercial.commercial_state(tenant_id)
    assert state["verified"] is True
    assert state["authoritySource"] == "PAID_ORDER"
    assert state["commercialOrderNo"] == created["orderNo"]
    assert state["features"]["internship"] is True
    assert commercial.feature_enabled(tenant_id, "internship") is True
