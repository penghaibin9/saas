from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete

from app.core.config import settings
from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models.data_exchange import IdentityImportStagingRow, ImportJob, ImportRowError
from app.models.file import FileObject
from app.services import storage
from app.services.identity_import_scan_orchestrator import (
    PENDING_ADAPTER,
    refresh_identity_import_job,
)
from app.workers import identity_import_worker

TENANT_ID = 93991
USER_ID = 939
USER = {
    "tenantId": str(TENANT_ID),
    "userId": str(USER_ID),
    "realName": "身份导入扫描测试",
    "userType": "ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
    "permissions": ["systemAdmin.user.import", "student.import"],
}


@pytest.fixture(autouse=True)
def _context_and_cleanup(db_mode, tmp_path, monkeypatch):
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user(USER)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "FILE_STORAGE_BACKEND", "local", raising=False)
    storage.reset_backend()
    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportRowError).where(ImportRowError.tenant_id == TENANT_ID))
        db.execute(delete(IdentityImportStagingRow).where(IdentityImportStagingRow.tenant_id == TENANT_ID))
        db.execute(delete(ImportJob).where(ImportJob.tenant_id == TENANT_ID))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    yield
    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportRowError).where(ImportRowError.tenant_id == TENANT_ID))
        db.execute(delete(IdentityImportStagingRow).where(IdentityImportStagingRow.tenant_id == TENANT_ID))
        db.execute(delete(ImportJob).where(ImportJob.tenant_id == TENANT_ID))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    storage.reset_backend()
    set_current_user(None)
    set_tenant(None)


def _source_file(*, status: str, scan_status: str, body: bytes = b"fixture") -> int:
    backend = storage.get_backend()
    key = f"identity-scan/{status}-{scan_status}-{id(body)}.xlsx"
    staged = backend.staging_path(key)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(body)
    backend.persist(key, staged)
    db = get_sessionmaker()()
    try:
        row = FileObject(
            tenant_id=TENANT_ID,
            file_key=key,
            file_name="教师导入.xlsx",
            ext="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=len(body),
            sha256="a" * 64,
            biz_type="DATA_IMPORT_SOURCE",
            status=status,
            storage_backend="local",
            storage_zone="QUARANTINE" if status == "QUARANTINED" else "ACTIVE",
            scan_required=True,
            scan_status=scan_status,
            owner_user_id=USER_ID,
            visibility="PRIVATE",
            security_level="SENSITIVE",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    finally:
        db.close()


def _pending_job(file_id: int, *, kind: str = "TEACHER") -> int:
    db = get_sessionmaker()()
    try:
        row = ImportJob(
            tenant_id=TENANT_ID,
            module_code="SYSTEM",
            import_type=f"IDENTITY_{kind}",
            source_file_id=file_id,
            adapter_type=PENDING_ADAPTER,
            adapter_ref=f"{kind}:{file_id}",
            template_version="v1",
            status="SCANNING",
            operator_id=USER_ID,
            operator_name=USER["realName"],
            source_snapshot_json={"kind": kind, "fileName": "教师导入.xlsx"},
            result_json={"scanRequired": True, "workerRequired": True},
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    finally:
        db.close()


def test_scanning_file_never_enters_normalized_staging(monkeypatch):
    file_id = _source_file(status="QUARANTINED", scan_status="PENDING")
    job_id = _pending_job(file_id)
    called = {"stage": 0}

    def forbidden(*args, **kwargs):
        called["stage"] += 1
        raise AssertionError("scanner-pending file must not enter staging")

    monkeypatch.setattr("app.services.identity_import_staging_service.stage_identity_xlsx", forbidden)
    refreshed = refresh_identity_import_job(str(job_id), user=USER)
    assert refreshed["status"] == "SCANNING"
    assert called["stage"] == 0


def test_clean_file_uses_normalized_staging_and_converts_same_job(monkeypatch):
    file_id = _source_file(status="AVAILABLE", scan_status="CLEAN")
    job_id = _pending_job(file_id)
    calls = {"stage": 0, "validate": 0, "batch": 0}

    def stage_stub(**kwargs):
        calls["stage"] += 1
        assert Path(kwargs["path"]).is_file()
        assert kwargs["kind"] == "TEACHER"
        return {
            "totalRows": 1,
            "fileName": kwargs["filename"],
            "fileSha256": "b" * 64,
            "kind": "TEACHER",
            "parserErrors": [],
            "stagingDigest": "c" * 64,
        }

    def validate_stub(**kwargs):
        calls["validate"] += 1
        assert kwargs["job_id"] == job_id
        return {"total": 1, "valid": 1, "invalid": 0, "errors": []}

    def batch_stub(**kwargs):
        calls["batch"] += 1
        return {
            "batchNo": f"IDENTITY-SCAN-{job_id}",
            "total": 1,
            "valid": 1,
            "invalid": 0,
            "errors": [],
            "roleTemplateVersion": "test",
        }

    monkeypatch.setattr("app.services.identity_import_staging_service.stage_identity_xlsx", stage_stub)
    monkeypatch.setattr("app.services.identity_import_staging_service.validate_staging", validate_stub)
    monkeypatch.setattr("app.services.identity_import_staging_service.create_staging_batch", batch_stub)
    result = refresh_identity_import_job(str(job_id), user=USER)
    assert result["id"] == str(job_id)
    assert result["status"] == "VALIDATED"
    assert result["adapterType"] == "IDENTITY_IMPORT_BATCH"
    assert result["sourceFileId"] == str(file_id)
    assert calls == {"stage": 1, "validate": 1, "batch": 1}


def test_identity_worker_claims_only_clean_file_and_consumes_claim(monkeypatch):
    pending_file = _source_file(status="QUARANTINED", scan_status="PENDING")
    _pending_job(pending_file)
    clean_file = _source_file(status="AVAILABLE", scan_status="CLEAN", body=b"clean")
    clean_job = _pending_job(clean_file)
    seen = {}

    def advance(job_id, *, user, worker_claimed=False, **kwargs):
        seen["jobId"] = job_id
        seen["user"] = user
        seen["workerClaimed"] = worker_claimed
        return {"status": "VALIDATED", "totalRows": 1, "validRows": 1, "invalidRows": 0}

    monkeypatch.setattr(identity_import_worker, "refresh_identity_import_job", advance)
    result = identity_import_worker.process_next_identity_import("pytest-i4-worker")
    assert result["processed"] is True
    assert result["jobId"] == str(clean_job)
    assert result["status"] == "VALIDATED"
    assert seen["workerClaimed"] is True
    assert seen["user"]["serviceActor"] == "IDENTITY_IMPORT_WORKER"

    db = get_sessionmaker()()
    try:
        claimed = db.get(ImportJob, clean_job)
        pending = db.scalars(ImportJob.__table__.select().where(ImportJob.source_file_id == pending_file)).first()
        assert claimed.status == identity_import_worker.CLAIMED
        assert dict(claimed.result_json or {})["workerId"] == "pytest-i4-worker"
        assert pending is not None
    finally:
        db.close()


def test_source_contract_freezes_scan_worker_before_parser():
    root = Path(__file__).resolve().parents[2]
    router = (root / "backend/app/modules/system_admin/routers/data_exchange_router.py").read_text(encoding="utf-8")
    orchestrator = (root / "backend/app/services/identity_import_scan_orchestrator.py").read_text(encoding="utf-8")
    worker = (root / "backend/app/workers/identity_import_worker.py").read_text(encoding="utf-8")
    file_worker = (root / "backend/app/workers/file_scan_worker.py").read_text(encoding="utf-8")
    assert "file_service.store_upload(" in router
    assert "identity.create_identity_import_job(" in router
    assert router.index("file_service.store_upload(") < router.index("identity.create_identity_import_job(")
    assert 'summary="导入任务详情（纯读）"' in router
    assert "/imports/{job_id}/process" in router
    assert "READY_SCAN_STATES" in orchestrator
    assert 'row.status = "PARSING"' in orchestrator
    assert "WORKER_CLAIMED" in orchestrator
    assert "process_next_identity_import" in worker
    assert ".with_for_update(skip_locked=True)" in worker
    assert "process_next_scan_job" in file_worker
    assert "parse_identity_xlsx_path" not in orchestrator
