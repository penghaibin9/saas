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


def test_w1_generic_features_write_is_rejected_by_canonical_router(client, db_mode):
    response = client.put(
        "/api/v1/platform/tenants/1000000000000000001/features",
        headers=_owner_headers(),
        json={"internship": True},
    )
    body = response.json()
    assert response.status_code == 409
    assert body["bizCode"] == "COMMERCIAL_AUTHORITY_REQUIRED"


def test_w1_generic_package_or_quota_transition_requires_controlled_exception(client, db_mode):
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


def test_w1_features_projection_exposes_legacy_override_as_read_only(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant
    from app.services import platform_control_authority_service as authority
    from app.services import platform_service

    tenant_id = 1000000000000096101
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            db.add(Tenant(id=tenant_id, tenant_code="w1-authority", school_name="W1授权学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()
    platform_service.put_config_json(tenant_id, "TENANT_META", "-", {
        "status": "active", "packageCode": "trial"
    })
    platform_service.put_config_json(tenant_id, "FEATURES", "-", {"internship": True})

    projection = authority.features_projection(tenant_id)
    assert projection["legacyOverride"] == {"internship": True}
    assert projection["legacyOverrideReadOnly"] is True
    assert projection["authoritySource"] == "LEGACY_OVERRIDE_READ_ONLY"
    assert projection["repairRequired"] is True
