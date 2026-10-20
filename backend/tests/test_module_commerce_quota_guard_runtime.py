from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException

BASE = 1000000000000018000


def _seed(tid: int, *, school_module_limit: int):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig, Tenant
    from app.models.file import TenantStorageQuota
    db = get_sessionmaker()()
    try:
        db.add(Tenant(id=tid, tenant_code=f"m3-quota-{tid}", school_name=f"M3Quota-{tid}",
                      deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE"))
        db.add(PlatformConfig(
            tenant_id=tid, config_type="TENANT_META", config_key="-",
            config_json={"status": "trial", "packageCode": "trial", "environment": "test"},
            enabled=True, status="ACTIVE",
        ))
        db.add(TenantStorageQuota(
            tenant_id=tid, total_quota_bytes=10_000, hard_limit_enabled=True,
            warning_percent=80,
            module_quota_json={"INTERNSHIP": school_module_limit, "GRADUATION": school_module_limit},
            description="M3 commercial quota test",
        ))
        db.commit()
    finally:
        db.close()


def _sku(code: str, *, storage_limit: int):
    from app.services import commercial_catalog_service as catalog
    payload = {
        "skuCode": code, "revision": 1, "name": code, "productType": "MODULE",
        "moduleKey": "internship", "features": {"internship": True, "fileUpload": True},
        "quotas": {"storageBytes": {"limit": storage_limit, "unit": "BYTES", "aggregation": "MAX"}},
        "pricePolicy": {"unitPrice": "100.00", "currency": "CNY", "taxTreatment": "UNSPECIFIED"},
        "lifecyclePolicyVersion": "M3-QUOTA-1",
    }
    published = catalog.publish_sku(payload, reason="M3商业存储额度测试")
    return catalog.get_sku_snapshot(published["skuCode"], published["revision"])


def _pay(tid: int, snapshot, key: str):
    from app.services import commercial_order_item_service as orders, platform_service
    start = datetime.now(timezone.utc) - timedelta(minutes=1)
    end = start + timedelta(days=30)
    sku = snapshot.as_dict()
    created = orders.create_itemized_order({
        "tenantId": str(tid), "currency": "CNY", "totalAmount": "100.00", "orderType": "NEW",
        "remark": "M3商业额度测试",
        "items": [{
            "lineNo": 1, "skuCode": sku["skuCode"], "skuRevision": sku["revision"],
            "skuContentHash": snapshot.content_hash, "quantity": 1, "unitPrice": "100.00",
            "discountAmount": "0.00", "netAmount": "100.00",
            "startAt": start.isoformat(), "endAt": end.isoformat(), "requestedGeneration": 1,
        }],
    }, idempotency_key=key, actor_id="0")
    paid = platform_service.order_action(
        created["orderNo"], "mark-paid", expected_version=created["version"],
        reason="M3商业额度支付激活测试",
    )
    assert paid["readerVersion"] == "MODULE_V2" and paid["repairTaskRequired"] is False


def _reserve(tid: int, key: str, amount: int, module: str = "INTERNSHIP"):
    from app.services.file_storage_quota_reservation_service import reserve_quota
    return reserve_quota(
        tenant_id=tid, reservation_key=key, source_type="TEST", source_id=key,
        size_bytes=amount, module_code=module, ttl_seconds=3600,
    )


def test_m3_commercial_module_limit_caps_looser_school_quota(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.file_quota import FileStorageQuotaReservation
    tid = BASE + 1
    _seed(tid, school_module_limit=1000)
    _pay(tid, _sku("M3-Q-COMMERCIAL", storage_limit=100), "m3-q-commercial")
    row = _reserve(tid, "m3-q-60", 60)
    assert row.status == "HELD" and int(row.reserved_bytes) == 60
    with pytest.raises(AppException) as caught:
        _reserve(tid, "m3-q-41", 41)
    assert caught.value.code == "COMMERCIAL_MODULE_STORAGE_QUOTA_EXCEEDED"
    assert caught.value.http_status == 409
    db = get_sessionmaker()()
    try:
        assert int(db.scalar(select(func.count(FileStorageQuotaReservation.id)).where(
            FileStorageQuotaReservation.tenant_id == tid,
            FileStorageQuotaReservation.status == "HELD",
        )) or 0) == 1
    finally:
        db.close()


def test_m3_school_quota_can_be_stricter_than_commercial_limit(db_mode):
    tid = BASE + 2
    _seed(tid, school_module_limit=70)
    _pay(tid, _sku("M3-Q-SCHOOL", storage_limit=1000), "m3-q-school")
    _reserve(tid, "m3-school-60", 60)
    with pytest.raises(AppException) as caught:
        _reserve(tid, "m3-school-20", 20)
    assert caught.value.code == "MODULE_STORAGE_QUOTA_EXCEEDED"
    assert caught.value.http_status == 409


def test_m3_unpurchased_module_cannot_consume_shared_file_upload_capability(db_mode):
    tid = BASE + 3
    _seed(tid, school_module_limit=1000)
    _pay(tid, _sku("M3-Q-NO-GRAD", storage_limit=100), "m3-q-no-grad")
    with pytest.raises(AppException) as caught:
        _reserve(tid, "m3-grad-deny", 1, module="GRADUATION")
    assert caught.value.http_status == 403
    assert caught.value.code in {"MODULE_NOT_WRITABLE", "MODULE_NOT_AUTHORIZED"}


def test_m3_cancel_at_period_end_keeps_contract_quota_until_service_end(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleSubscriptionSource
    from app.services import module_commerce_lifecycle_service as lifecycle
    tid = BASE + 4
    _seed(tid, school_module_limit=1000)
    _pay(tid, _sku("M3-Q-SCHEDULE", storage_limit=100), "m3-q-schedule")
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.tenant_id == tid,
            TenantModuleSubscriptionSource.module_key == "internship",
        )).one()
        source_id, version = int(source.id), int(source.version or 0)
    finally:
        db.close()
    planned = lifecycle.schedule_source_cancellation(
        {"userId": "0"}, tid, source_id, expected_version=version,
        reason="本期结束后停止续费但不提前断额度",
    )
    assert planned["status"] == "CANCEL_SCHEDULED"
    assert _reserve(tid, "m3-scheduled-50", 50).status == "HELD"


def test_m3_cancelled_source_cannot_reserve_new_module_bytes(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleSubscriptionSource
    from app.services import module_subscription_service as subscriptions
    tid = BASE + 5
    _seed(tid, school_module_limit=1000)
    _pay(tid, _sku("M3-Q-CANCELLED", storage_limit=100), "m3-q-cancelled")
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.tenant_id == tid,
            TenantModuleSubscriptionSource.module_key == "internship",
        )).one()
        source_id, version = int(source.id), int(source.version or 0)
    finally:
        db.close()
    subscriptions.cancel_subscription_source_now(
        tid, source_id, expected_version=version, reason="合同来源已正式取消",
    )
    with pytest.raises(AppException) as caught:
        _reserve(tid, "m3-after-cancel", 1)
    assert caught.value.code == "MODULE_NOT_AUTHORIZED" and caught.value.http_status == 403


def test_m3_concurrent_reservations_cannot_oversubscribe_commercial_limit(db_mode):
    tid = BASE + 6
    _seed(tid, school_module_limit=1000)
    _pay(tid, _sku("M3-Q-CONCURRENT", storage_limit=100), "m3-q-concurrent")
    barrier = threading.Barrier(8)

    def reserve(index: int):
        barrier.wait(10)
        try:
            _reserve(tid, f"m3-concurrent-{index}", 20)
            return "OK"
        except AppException as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(8)))
    assert results.count("OK") == 5, results
    assert results.count("COMMERCIAL_MODULE_STORAGE_QUOTA_EXCEEDED") == 3, results
