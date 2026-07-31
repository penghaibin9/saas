from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models.file import TenantStorageQuota
from app.models.file_quota import FileStorageQuotaReservation
from app.services import storage
from app.services.file_storage_write_context import current_storage_module, storage_write_scope

TENANT_ID = 92991
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _context_and_cleanup(db_mode, tmp_path, monkeypatch):
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user({"userId": "929", "userType": "STAFF", "realName": "模块配额测试"})
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "FILE_STORAGE_BACKEND", "local", raising=False)
    storage.reset_backend()
    db = get_sessionmaker()()
    try:
        db.execute(delete(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == TENANT_ID
        ))
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
        db.execute(delete(TenantStorageQuota).where(TenantStorageQuota.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    storage.reset_backend()
    set_current_user(None)
    set_tenant(None)


def test_context_is_request_local_and_restored_after_write_scope():
    assert current_storage_module() == "SHARED"
    with storage_write_scope("GRADUATION_MATERIAL"):
        assert current_storage_module() == "GRADUATION"
        with storage_write_scope("INTERNSHIP"):
            assert current_storage_module() == "INTERNSHIP"
        assert current_storage_module() == "GRADUATION"
    assert current_storage_module() == "SHARED"


def test_physical_boundary_records_declared_module_reservation():
    db = get_sessionmaker()()
    try:
        db.add(TenantStorageQuota(
            tenant_id=TENANT_ID,
            total_quota_bytes=100,
            warning_percent=80,
            hard_limit_enabled=True,
            module_quota_json={"GRADUATION": 50, "SHARED": 100},
        ))
        db.commit()
    finally:
        db.close()

    backend = storage.get_backend()
    key = "quota-context/graduation.txt"
    staged = backend.staging_path(key)
    staged.write_bytes(b"x" * 30)
    with storage_write_scope("GRADUATION_MATERIAL"):
        backend.persist(key, staged)

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(FileStorageQuotaReservation).where(
            FileStorageQuotaReservation.tenant_id == TENANT_ID,
            FileStorageQuotaReservation.source_type == "STORAGE_PERSIST",
            FileStorageQuotaReservation.source_id == key,
        )).one()
        assert row.status == "HELD"
        assert row.module_code == "GRADUATION"
        assert row.reserved_bytes == 30
    finally:
        db.close()


def test_all_authoritative_server_write_paths_enter_explicit_scope():
    file_service = (ROOT / "backend/app/services/file_service.py").read_text(encoding="utf-8")
    generated = (ROOT / "backend/app/services/generated_file_path_service.py").read_text(encoding="utf-8")
    governed = (ROOT / "backend/app/services/storage/governed.py").read_text(encoding="utf-8")
    assert "from app.services.file_storage_write_context import storage_write_scope" in file_service
    assert file_service.count("with storage_write_scope(biz_type):") >= 2
    assert "with storage_write_scope(biz_type):" in generated
    assert "current_storage_module()" in governed
    assert "module_code=\"SHARED\"" not in governed
