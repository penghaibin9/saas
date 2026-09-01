"""V8 control-plane delivery evidence and authority boundaries."""
from __future__ import annotations

from datetime import datetime, timedelta


TENANT_ID = 2608311200000000001


def _owner_headers() -> dict:
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": "u-platform-delivery-owner",
        "realName": "平台交付负责人",
        "userType": "PLATFORM_SUPER_ADMIN",
        "tid": "platform",
        "tenantId": "1000000000000000000",
        "tenantName": "平台运营中心",
        "activeContextId": "ctx_platform_delivery_owner",
        "currentRoleCode": "PLATFORM_SUPER_ADMIN",
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def _seed_ready_except_smoke() -> str:
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (
        PlatformConfig,
        PlatformOrder,
        SystemImplementationProject,
        Tenant,
        User,
    )
    from app.models.tenant_provisioning import ProvisioningJob

    digest = "a" * 64
    db = get_sessionmaker()()
    try:
        tenant = Tenant(
            id=TENANT_ID,
            tenant_code="v8-delivery",
            school_name="V8 真实交付测试学校",
            status="ACTIVE",
        )
        db.add(tenant)
        db.add(PlatformConfig(
            tenant_id=TENANT_ID,
            config_type="TENANT_META",
            config_key="-",
            config_json={
                "status": "active",
                "packageCode": "standard",
                "expireAt": (datetime.utcnow() + timedelta(days=365)).isoformat(timespec="seconds"),
            },
            enabled=True,
        ))
        db.add(PlatformOrder(
            tenant_id=TENANT_ID,
            order_no="PO-V8-DELIVERY-001",
            order_type="NEW",
            package_code="standard",
            amount=49800,
            paid_amount=49800,
            status="paid",
            start_at=datetime.utcnow(),
            end_at=datetime.utcnow() + timedelta(days=365),
        ))
        db.add(ProvisioningJob(
            idempotency_key="v8-delivery-ready-001",
            tenant_code="v8-delivery",
            tenant_id=TENANT_ID,
            input_json={"targetPackageCode": "standard"},
            status="SUCCEEDED",
            current_step="HEALTH_CHECK",
        ))
        db.add(User(
            tenant_id=TENANT_ID,
            login_name="v8_delivery_admin",
            real_name="V8 学校管理员",
            password_hash=hash_password("V8Delivery#2026"),
            user_type="SCHOOL_ADMIN",
            status="ACTIVE",
            must_change_password=False,
        ))
        db.add(SystemImplementationProject(
            tenant_id=TENANT_ID,
            project_no="IMP-V8-DELIVERY-001",
            project_name="V8 真实交付实施项目",
            profile_code="HIGHER_VOCATIONAL",
            status="ACCEPTED",
            accepted_at=datetime.utcnow(),
            acceptance_comment="学校已完成真实验收",
            acceptance_digest=digest,
            acceptance_summary={"status": "ACCEPTED", "source": "school"},
        ))
        db.commit()
    finally:
        db.close()
    return digest


def _checks() -> list[dict]:
    from app.services.platform_delivery_service import REQUIRED_CONSUMER_SURFACES

    return [{
        "surface": surface,
        "readStatus": "PASS",
        "actionStatus": "PASS",
        "scopeStatus": "PASS",
        "evidenceRef": f"artifacts/consumer-smoke/{surface.lower()}.json",
    } for surface in sorted(REQUIRED_CONSUMER_SURFACES)]


def test_delivery_requires_current_complete_consumer_evidence(client, db_mode, monkeypatch):
    acceptance_digest = _seed_ready_except_smoke()
    headers = _owner_headers()
    monkeypatch.setenv("DEPLOYED_COMMIT_SHA", "b" * 40)

    initial = client.get(
        f"/api/v1/platform/tenants/{TENANT_ID}/delivery", headers=headers,
    ).json()
    assert initial["code"] == 0, initial
    row = initial["data"]
    assert row["provisioningState"] == "BOOTSTRAP_READY"
    assert row["commercialState"] == "PAID_ACTIVE"
    assert row["firstAdminState"] == "PASSWORD_CHANGED"
    assert row["deliveryState"] == "BLOCKED"
    assert {item["code"] for item in row["blockers"]} == {"CONSUMER_SMOKE_NOT_PASS"}

    incomplete = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/consumer-smoke",
        headers=headers,
        json={
            "exactHead": "b" * 40,
            "status": "PASS",
            "acceptanceDigest": acceptance_digest,
            "checks": _checks()[:-1],
        },
    ).json()
    assert incomplete["code"] == 409001

    wrong_head = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/consumer-smoke",
        headers=headers,
        json={
            "exactHead": "c" * 40,
            "status": "PASS",
            "acceptanceDigest": acceptance_digest,
            "checks": _checks(),
        },
    ).json()
    assert wrong_head["code"] == 409001

    smoke_body = {
        "exactHead": "b" * 40,
        "status": "PASS",
        "acceptanceDigest": acceptance_digest,
        "checks": _checks(),
    }
    smoke = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/consumer-smoke",
        headers=headers,
        json=smoke_body,
    ).json()
    assert smoke["code"] == 0, smoke
    row = smoke["data"]
    assert row["consumerSmokeState"] == "PASS"
    assert row["deliveryState"] == "READY_FOR_PLATFORM_ACCEPTANCE"

    stale = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/delivery-acceptance",
        headers=headers,
        json={
            "confirmText": "确认交付",
            "comment": "平台交付确认",
            "expectedReadModelDigest": "stale",
        },
    ).json()
    assert stale["code"] == 409001

    accepted = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/delivery-acceptance",
        headers=headers,
        json={
            "confirmText": "确认交付",
            "comment": "平台交付确认",
            "expectedReadModelDigest": row["readModelDigest"],
        },
    ).json()
    assert accepted["code"] == 0, accepted
    assert accepted["data"]["platformAcceptanceState"] == "ACCEPTED"
    assert accepted["data"]["deliveryState"] == "SCHOOL_DELIVERY_PRODUCTION_READY"
    assert accepted["data"]["acceptanceDigest"] == acceptance_digest

    # Same evidence is idempotent; a new exact-head seal on the same school digest
    # makes the old platform acceptance stale and can be accepted as a second immutable record.
    replay = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/consumer-smoke",
        headers=headers,
        json=smoke_body,
    ).json()
    assert replay["data"]["platformAcceptanceState"] == "ACCEPTED"

    monkeypatch.setenv("DEPLOYED_COMMIT_SHA", "c" * 40)
    drifted = client.get(
        f"/api/v1/platform/tenants/{TENANT_ID}/delivery", headers=headers,
    ).json()
    assert drifted["code"] == 0, drifted
    assert drifted["data"]["consumerSmokeState"] == "STALE_HEAD"
    assert drifted["data"]["platformAcceptanceState"] == "STALE"
    assert drifted["data"]["deliveryState"] == "BLOCKED"
    assert drifted["data"]["deployedExactHead"] == "c" * 40

    next_head = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/consumer-smoke",
        headers=headers,
        json={**smoke_body, "exactHead": "c" * 40},
    ).json()
    assert next_head["code"] == 0, next_head
    assert next_head["data"]["platformAcceptanceState"] == "STALE"
    assert next_head["data"]["deliveryState"] == "READY_FOR_PLATFORM_ACCEPTANCE"

    reaccepted = client.post(
        f"/api/v1/platform/tenants/{TENANT_ID}/delivery-acceptance",
        headers=headers,
        json={
            "confirmText": "确认交付",
            "comment": "新 exact-head 重新确认",
            "expectedReadModelDigest": next_head["data"]["readModelDigest"],
        },
    ).json()
    assert reaccepted["code"] == 0, reaccepted
    assert reaccepted["data"]["platformAcceptanceState"] == "ACCEPTED"
    assert reaccepted["data"]["acceptanceDigest"] == acceptance_digest

    from sqlalchemy import func, select
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig
    from app.services.platform_delivery_service import (
        CONSUMER_SMOKE_CONFIG,
        PLATFORM_ACCEPTANCE_CONFIG,
    )

    db = get_sessionmaker()()
    try:
        counts = dict(db.execute(select(
            PlatformConfig.config_type, func.count(PlatformConfig.id),
        ).where(
            PlatformConfig.tenant_id == TENANT_ID,
            PlatformConfig.config_type.in_((CONSUMER_SMOKE_CONFIG, PLATFORM_ACCEPTANCE_CONFIG)),
        ).group_by(PlatformConfig.config_type)).all())
    finally:
        db.close()
    assert counts == {CONSUMER_SMOKE_CONFIG: 2, PLATFORM_ACCEPTANCE_CONFIG: 2}


def test_account_counts_never_claim_acceptance_readiness(client, db_mode):
    _seed_ready_except_smoke()
    headers = _owner_headers()
    tenant = client.get(f"/api/v1/platform/tenants/{TENANT_ID}", headers=headers).json()
    assert tenant["code"] == 0, tenant
    assert tenant["data"]["onboarding"] == {
        "phase": "ACCOUNT_INVENTORY_ONLY",
        "label": "只读账号统计（不代表交付就绪）",
        "schoolAdminCount": 1,
        "teacherAccountCount": 0,
        "studentAccountCount": 0,
        "readyForAcceptance": False,
    }
