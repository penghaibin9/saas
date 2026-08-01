from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.file import FileObject, TenantStorageQuota
from app.models.file_quota import FileStorageQuotaReservation
from app.services.file_storage_quota_reservation_service import (
    consume_quota,
    expire_reservations,
    held_bytes,
    release_quota,
    reserve_quota,
)

TENANT_ID = 91991


@pytest.fixture(autouse=True)
def _context_and_cleanup(db_mode):
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user({"userId": "919", "userType": "STAFF", "realName": "配额预留测试"})
    db = get_sessionmaker()()
    try:
        db.execute(delete(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == TENANT_ID
        ))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.execute(delete(TenantStorageQuota).where(TenantStorageQuota.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    yield
    db = get_sessionmaker()()
    try:
        db.execute(delete(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == TENANT_ID
        ))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.execute(delete(TenantStorageQuota).where(TenantStorageQuota.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    set_current_user(None)
    set_tenant(None)


def _quota(total: int = 100, module: dict | None = None) -> None:
    db = get_sessionmaker()()
    try:
        db.add(TenantStorageQuota(
            tenant_id=TENANT_ID,
            total_quota_bytes=total,
            warning_percent=80,
            hard_limit_enabled=True,
            module_quota_json=module or {},
        ))
        db.commit()
    finally:
        db.close()


def _file(key: str, size: int, *, biz_type: str = "ATTACHMENT") -> int:
    db = get_sessionmaker()()
    try:
        row = FileObject(
            tenant_id=TENANT_ID,
            file_key=key,
            object_key=key,
            file_name=key.rsplit("/", 1)[-1],
            ext="txt",
            mime_type="text/plain",
            size_bytes=size,
            sha256="a" * 64,
            biz_type=biz_type,
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    finally:
        db.close()


def test_two_concurrent_reservations_cannot_oversell_same_quota():
    _quota(100)
    first = reserve_quota(
        reservation_key="first",
        source_type="COS_UPLOAD_SESSION",
        source_id="session-1",
        size_bytes=60,
        module_code="GRADUATION",
    )
    assert first is not None and first.status == "HELD"
    with pytest.raises(AppException) as exc:
        reserve_quota(
            reservation_key="second",
            source_type="COS_UPLOAD_SESSION",
            source_id="session-2",
            size_bytes=50,
            module_code="GRADUATION",
        )
    assert exc.value.code == "TENANT_STORAGE_QUOTA_EXCEEDED"
    assert held_bytes() == 60


def test_idempotent_retry_does_not_double_reserve():
    _quota(100)
    first = reserve_quota(
        reservation_key="same-key",
        source_type="COS_UPLOAD_SESSION",
        source_id="same-session",
        size_bytes=40,
    )
    retry = reserve_quota(
        reservation_key="same-key",
        source_type="COS_UPLOAD_SESSION",
        source_id="same-session",
        size_bytes=40,
    )
    assert first is not None and retry is not None
    assert int(first.id) == int(retry.id)
    assert held_bytes() == 40


def test_consumed_reservation_stops_double_counting_and_real_file_remains_used():
    _quota(100)
    reserve_quota(
        reservation_key="consume-key",
        source_type="COS_UPLOAD_SESSION",
        source_id="session-consume",
        size_bytes=60,
    )
    file_id = _file("quarantine/consume.txt", 60, biz_type="GRADUATION_MATERIAL")
    assert consume_quota("consume-key", file_id=file_id) is True
    assert held_bytes() == 0
    with pytest.raises(AppException) as exc:
        reserve_quota(
            reservation_key="after-consume",
            source_type="COS_UPLOAD_SESSION",
            source_id="session-after",
            size_bytes=50,
        )
    assert exc.value.code == "TENANT_STORAGE_QUOTA_EXCEEDED"


def test_release_after_failed_or_abandoned_write_restores_capacity():
    _quota(100)
    reserve_quota(
        reservation_key="release-key",
        source_type="COS_UPLOAD_SESSION",
        source_id="session-release",
        size_bytes=80,
    )
    assert release_quota("release-key", reason="ABANDONED") is True
    assert held_bytes() == 0
    replacement = reserve_quota(
        reservation_key="replacement-key",
        source_type="COS_UPLOAD_SESSION",
        source_id="session-replacement",
        size_bytes=80,
    )
    assert replacement is not None and replacement.status == "HELD"


def test_server_persist_reservation_reconciles_to_file_object():
    _quota(100)
    source_key = "2026/07/server-generated.txt"
    reserve_quota(
        reservation_key="persist-key",
        source_type="STORAGE_PERSIST",
        source_id=source_key,
        size_bytes=30,
    )
    file_id = _file(source_key, 30)
    assert held_bytes() == 0
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == TENANT_ID,
            FileStorageQuotaReservation.reservation_key == "persist-key",
        )).one()
        assert row.status == "CONSUMED"
        assert int(row.consumed_file_id) == file_id
    finally:
        db.close()


def test_expired_orphan_reservation_is_released_by_worker_contract():
    _quota(100)
    row = reserve_quota(
        reservation_key="expired-key",
        source_type="STORAGE_PERSIST",
        source_id="missing/object.txt",
        size_bytes=70,
    )
    db = get_sessionmaker()()
    try:
        current = db.get(FileStorageQuotaReservation, int(row.id), with_for_update=True)
        current.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    result = expire_reservations(tenant_id=TENANT_ID)
    assert result["expired"] == 1
    assert held_bytes() == 0


def test_direct_session_and_physical_storage_paths_use_reservations():
    api = open("app/api/v1/file.py", encoding="utf-8").read()
    governed = open("app/services/storage/governed.py", encoding="utf-8").read()
    cleanup = open("app/services/file_upload_session_cleanup_service.py", encoding="utf-8").read()
    worker = open("app/workers/file_governance_worker.py", encoding="utf-8").read()
    assert "reserve_quota(" in api
    assert "consume_quota(" in api
    assert "release_quota(" in api
    assert "reserve_quota(" in governed
    assert "PHYSICAL_PERSIST_FAILED" in governed
    assert "COS_UPLOAD_SESSION_EXPIRED" in cleanup
    assert "expire_reservations" in worker
