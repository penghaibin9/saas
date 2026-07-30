from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete

from app.api.v1 import files as files_router
from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models.file import FileBinding, FileJob, FileObject, FileRetentionPolicy, TenantStorageQuota
from app.services import file_storage_governance_service as governance
from app.services.storage import _config_cache_key

TENANT_ID = 90991


class FakeBackend:
    kind = "local"

    def __init__(self):
        self.deleted: list[str] = []

    def delete(self, key: str) -> None:
        self.deleted.append(key)


@pytest.fixture(autouse=True)
def tenant_context_and_cleanup(db_mode):
    """复用全仓 MySQL 测试夹具；禁止治理测试自行打开默认/生产数据库。"""
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user({"userId": "1", "userType": "STAFF", "realName": "治理测试"})
    db = get_sessionmaker()()
    try:
        for model in (FileBinding, FileJob, FileObject, FileRetentionPolicy, TenantStorageQuota):
            db.execute(delete(model).where(model.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    yield
    db = get_sessionmaker()()
    try:
        for model in (FileBinding, FileJob, FileObject, FileRetentionPolicy, TenantStorageQuota):
            db.execute(delete(model).where(model.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    set_current_user(None)
    set_tenant(None)


def _file(name: str, *, size: int = 10, hold: bool = False, expired: bool = False) -> FileObject:
    now = datetime.utcnow()
    return FileObject(
        tenant_id=TENANT_ID,
        file_key=f"clean/{TENANT_ID}/{name}",
        object_key=f"clean/{TENANT_ID}/{name}",
        file_name=name,
        ext="pdf",
        size_bytes=size,
        biz_type="GRADUATION_MATERIAL",
        status="AVAILABLE",
        storage_backend="local",
        storage_zone="CLEAN",
        legal_hold=hold,
        retention_until=now - timedelta(days=1) if expired else now + timedelta(days=30),
        scan_required=False,
        scan_status="NOT_REQUIRED",
    )


def test_static_governance_routes_are_before_dynamic_file_id():
    paths = [route.path for route in files_router.router.routes]
    governance_index = paths.index("/files/governance/overview")
    dynamic_index = paths.index("/files/{file_id}")
    assert governance_index < dynamic_index


def test_backend_cache_key_changes_for_tenant_bucket_and_credentials():
    base = {"backend": "cos", "cosRegion": "ap-guangzhou", "cosBucket": "school-a", "cosSecretId": "id-a", "cosSecretKey": "key-a"}
    same = dict(base)
    other_bucket = {**base, "cosBucket": "school-b"}
    other_key = {**base, "cosSecretKey": "key-b"}
    assert _config_cache_key(base) == _config_cache_key(same)
    assert _config_cache_key(base) != _config_cache_key(other_bucket)
    assert _config_cache_key(base) != _config_cache_key(other_key)
    assert "key-a" not in repr(_config_cache_key(base))


def test_hard_quota_rejects_server_and_direct_upload_boundary():
    db = get_sessionmaker()()
    try:
        db.add(TenantStorageQuota(
            tenant_id=TENANT_ID,
            total_quota_bytes=100,
            warning_percent=80,
            hard_limit_enabled=True,
        ))
        db.add(_file("used.pdf", size=90))
        db.commit()
    finally:
        db.close()
    with pytest.raises(Exception) as exc:
        governance.assert_quota_available(20, tenant_id=TENANT_ID, module_code="GRADUATION")
    assert "TENANT_STORAGE_QUOTA_EXCEEDED" in str(getattr(exc.value, "code", "")) or "存储空间已满" in str(exc.value)


def test_retention_policy_priority_assigns_deadline():
    db = get_sessionmaker()()
    try:
        db.add(FileRetentionPolicy(
            tenant_id=TENANT_ID,
            policy_code="GRAD_30D",
            module_code="GRADUATION",
            biz_type="GRADUATION_MATERIAL",
            storage_zone="CLEAN",
            retention_days=30,
            cleanup_action="DELETE_BYTES",
            priority=10,
            is_active=True,
        ))
        row = _file("policy.pdf")
        row.retention_until = None
        row.created_at = datetime.utcnow()
        db.add(row)
        db.flush()
        deadline = governance.assign_retention(row, module_code="GRADUATION", db=db)
        db.commit()
        assert 29 <= (deadline - row.created_at).days <= 30
    finally:
        db.close()


def test_cleanup_deletes_only_unreferenced_and_never_legal_hold(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr("app.services.storage.get_backend", lambda: fake)
    db = get_sessionmaker()()
    try:
        eligible = _file("eligible.pdf", expired=True)
        held = _file("held.pdf", hold=True, expired=True)
        referenced = _file("referenced.pdf", expired=True)
        db.add_all([eligible, held, referenced])
        db.flush()
        db.add(FileBinding(
            tenant_id=TENANT_ID,
            file_id=referenced.id,
            biz_type="GRADUATION_MATERIAL",
            biz_id="student-1",
            relation_type="ATTACHMENT",
            subject_type="STUDENT",
            subject_id="1",
            is_current=True,
            status="ACTIVE",
        ))
        db.commit()
        eligible_id, held_id, referenced_id = eligible.id, held.id, referenced.id
    finally:
        db.close()

    preview = governance.cleanup_expired(tenant_id=TENANT_ID, dry_run=True, limit=50)
    assert preview["deleted"] == 0
    assert preview["skippedLegalHold"] == 1
    assert preview["skippedReferenced"] == 1
    assert fake.deleted == []

    result = governance.cleanup_expired(tenant_id=TENANT_ID, dry_run=False, limit=50)
    assert result["deleted"] == 1
    assert fake.deleted == [f"clean/{TENANT_ID}/eligible.pdf"]
    db = get_sessionmaker()()
    try:
        assert db.get(FileObject, eligible_id).is_deleted is True
        assert db.get(FileObject, held_id).is_deleted is False
        assert db.get(FileObject, referenced_id).is_deleted is False
    finally:
        db.close()
