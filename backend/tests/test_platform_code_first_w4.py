from __future__ import annotations

import pytest

from app.core.exceptions import AppException


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


def test_w4_brand_expected_version_prevents_lost_update(db_mode):
    from app.services import platform_control_authority_service as authority

    tenant_id = 1000000000000096402
    _ensure_tenant(tenant_id)
    initial = authority.brand_projection(tenant_id)
    version = int(initial["overrideVersion"])

    first = authority.update_brand(
        tenant_id,
        brand={"watermarkText": "W4第一版水印"},
        expected_version=version,
        reason="W4第一次品牌修改",
    )
    assert int(first["overrideVersion"]) == version + 1

    with pytest.raises(AppException) as caught:
        authority.update_brand(
            tenant_id,
            brand={"watermarkText": "W4过期写入"},
            expected_version=version,
            reason="W4过期版本品牌修改",
        )
    assert caught.value.code == "DATA_CONFLICT"


def test_w4_shared_config_writes_require_reason_and_version(db_mode):
    from app.services import platform_control_authority_service as authority

    tenant_id = 1000000000000096403
    _ensure_tenant(tenant_id)
    with pytest.raises(AppException) as missing_version:
        authority.update_rules(
            tenant_id,
            rules={"departure": {"disciplineBlocks": True}},
            expected_version=None,
            reason="W4缺少版本测试",
        )
    assert missing_version.value.code == "VALIDATION_ERROR"

    version = authority.brand_projection(tenant_id)["overrideVersion"]
    with pytest.raises(AppException) as short_reason:
        authority.update_brand(
            tenant_id,
            brand={"watermarkText": "x"},
            expected_version=version,
            reason="短",
        )
    assert short_reason.value.code == "VALIDATION_ERROR"
