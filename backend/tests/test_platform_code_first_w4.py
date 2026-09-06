from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.core.security import create_access_token


def _ensure_tenant(tenant_id: int) -> None:
    from app.db.session import get_sessionmaker
    from app.models import Tenant

    db = get_sessionmaker()()
    try:
        row = db.get(Tenant, tenant_id)
        if row is None:
            db.add(Tenant(id=tenant_id, tenant_code=f"w4-{tenant_id}", school_name="W4并发学校", status="ACTIVE"))
            db.commit()
    finally:
        db.close()


def _owner_headers() -> dict[str, str]:
    token = create_access_token({
        "userId": "w4-owner",
        "realName": "W4平台主管",
        "userType": "PLATFORM_SUPER_ADMIN",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "tenantId": "0",
        "tid": "platform",
        "activeContextId": "ctx-w4",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def test_w4_rules_expected_version_prevents_lost_update(db_mode):
    from app.services import platform_control_authority_service as authority

    tenant_id = 1000000000000096401
    _ensure_tenant(tenant_id)
    initial = authority.rules_projection(tenant_id)
    version = int(initial["overrideVersion"])

    first = authority.update_rules(
        tenant_id,
        rules={"departure": {"disciplineBlocks": True}},
        expected_version=version,
        reason="W4第一次规则修改",
    )
    assert int(first["overrideVersion"]) == version + 1

    with pytest.raises(AppException) as caught:
        authority.update_rules(
            tenant_id,
            rules={"departure": {"disciplineBlocks": False}},
            expected_version=version,
            reason="W4过期版本规则修改",
        )
    assert caught.value.code == "DATA_CONFLICT"


def test_w4_tenant_brand_expected_version_prevents_lost_update(db_mode):
    from app.services import tenant_brand_authority_service as brand_authority

    tenant_id = 1000000000000096402
    _ensure_tenant(tenant_id)
    initial = brand_authority.brand_projection(tenant_id)
    version = int(initial["version"])

    first = brand_authority.update_school_brand(
        tenant_id,
        brand={"watermarkText": "W4第一版水印"},
        expected_version=version,
        reason="W4第一次品牌修改",
        user={"userId": "db-1", "realName": "学校管理员"},
    )
    assert int(first["version"]) == version + 1

    with pytest.raises(AppException) as caught:
        brand_authority.update_school_brand(
            tenant_id,
            brand={"watermarkText": "W4过期写入"},
            expected_version=version,
            reason="W4过期版本品牌修改",
            user={"userId": "db-1", "realName": "学校管理员"},
        )
    assert caught.value.code == "DATA_CONFLICT"


def test_w4_platform_brand_writer_is_retired_and_legacy_brand_is_read_only(client, db_mode):
    from app.services import platform_service
    from app.services import tenant_brand_authority_service as brand_authority

    tenant_id = 1000000000000096403
    _ensure_tenant(tenant_id)
    current = brand_authority.brand_projection(tenant_id)
    brand_authority.update_school_brand(
        tenant_id,
        brand={"watermarkText": "学校唯一真值"},
        expected_version=current["version"],
        reason="学校写入唯一品牌真值",
        user={"userId": "db-1", "realName": "学校管理员"},
    )
    # Historical PlatformConfig(BRAND) may still exist for reconciliation, but
    # it cannot replace TenantBrandConfig at runtime.
    platform_service.put_config_json(
        tenant_id, "BRAND", "-", {"watermarkText": "历史平台主管旧值"}
    )
    projection = brand_authority.brand_projection(tenant_id)
    assert projection["authority"] == "TENANT_BRAND_CONFIG"
    assert projection["brand"]["watermarkText"] == "学校唯一真值"
    assert projection["legacyOverride"]["watermarkText"] == "历史平台主管旧值"
    assert projection["legacyOverrideReadOnly"] is True
    assert projection["repairRequired"] is True

    response = client.put(
        f"/api/v1/platform/tenants/{tenant_id}/brand",
        headers=_owner_headers(),
        json={"brand": {"watermarkText": "平台主管再次覆盖"}, "expectedVersion": 0, "reason": "尝试旧平台写入口"},
    )
    assert response.status_code == 409
    assert response.json()["bizCode"] == "BRAND_AUTHORITY_MOVED"
    assert brand_authority.brand_projection(tenant_id)["brand"]["watermarkText"] == "学校唯一真值"


def test_w4_shared_config_writes_require_reason_and_version(db_mode):
    from app.services import platform_control_authority_service as authority
    from app.services import tenant_brand_authority_service as brand_authority

    tenant_id = 1000000000000096404
    _ensure_tenant(tenant_id)
    with pytest.raises(AppException) as missing_version:
        authority.update_rules(
            tenant_id,
            rules={"departure": {"disciplineBlocks": True}},
            expected_version=None,
            reason="W4缺少版本测试",
        )
    assert missing_version.value.code == "VALIDATION_ERROR"

    with pytest.raises(AppException) as brand_missing_version:
        brand_authority.update_school_brand(
            tenant_id,
            brand={"watermarkText": "x"},
            expected_version=None,
            reason="W4品牌缺少版本",
        )
    assert brand_missing_version.value.code == "VALIDATION_ERROR"

    with pytest.raises(AppException) as reset_missing_version:
        brand_authority.reset_school_brand(
            tenant_id,
            expected_version=None,
            reason="W4恢复品牌缺少版本",
        )
    assert reset_missing_version.value.code == "VALIDATION_ERROR"
