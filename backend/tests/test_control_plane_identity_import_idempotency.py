from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.data_exchange import ImportJob
from app.models.file import FileObject, FileUploadSession
from app.modules.system_admin.services import identity_import_control_plane_service as identity
from app.modules.system_admin.services import identity_import_idempotency_service as idem
from app.services import data_exchange_job_service as jobs

TENANT_ID = 94421
USER_ID = 944
USER = {
    "tenantId": str(TENANT_ID),
    "userId": str(USER_ID),
    "realName": "I1幂等测试",
    "userType": "ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
    "permissions": ["*"],
}


@pytest.fixture(autouse=True)
def _ctx_and_cleanup(db_mode):
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user(USER)
    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportJob).where(ImportJob.tenant_id == TENANT_ID))
        db.execute(delete(FileUploadSession).where(FileUploadSession.tenant_id == TENANT_ID))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    yield
    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportJob).where(ImportJob.tenant_id == TENANT_ID))
        db.execute(delete(FileUploadSession).where(FileUploadSession.tenant_id == TENANT_ID))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    set_current_user(None)
    set_tenant(None)


def _source_file(session_key: str) -> int:
    db = get_sessionmaker()()
    try:
        row = FileObject(
            tenant_id=TENANT_ID,
            file_key=f"identity-idempotency/{session_key}.xlsx",
            file_name="学生导入.xlsx",
            ext="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=2048,
            sha256="c" * 64,
            biz_type="DATA_IMPORT_SOURCE",
            biz_id=session_key,
            owner_user_id=USER_ID,
            created_by=USER_ID,
            visibility="PRIVATE",
            security_level="SENSITIVE",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            upload_source="USER",
            scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    finally:
        db.close()


def test_request_replay_survives_adapter_ref_transition_without_duplicate_file_or_job():
    key = "identity-upload-students-94421-000001"
    first = idem.prepare_request(kind="STUDENT", idempotency_key=key, filename="学生导入.xlsx", user=USER)
    assert first["sourceFileId"] is None
    assert first["replayJob"] is None

    with pytest.raises(AppException):
        idem.prepare_request(kind="STUDENT", idempotency_key=key, filename="学生导入.xlsx", user=USER)

    file_id = _source_file(first["sessionKey"])
    idem.complete_request(session_key=first["sessionKey"], source_file_id=file_id, user=USER)
    job = identity.create_identity_import_job(
        kind="STUDENT",
        source_file_id=file_id,
        filename="学生导入.xlsx",
        user=USER,
        upload_session_key=first["sessionKey"],
    )
    assert job["status"] == "SCANNING"
    assert job["result"]["workerRequired"] is True

    db = get_sessionmaker()()
    try:
        row = db.scalar(select(ImportJob).where(ImportJob.id == int(job["id"])).with_for_update())
        assert row is not None
        assert (row.source_snapshot_json or {}).get("uploadSessionKey") == first["sessionKey"]
        row.adapter_type = jobs.IMPORT_ADAPTER_IDENTITY
        row.adapter_ref = "BATCH-I1-IDEMPOTENT-94421"
        row.status = "VALIDATED"
        row.version = int(row.version or 0) + 1
        db.commit()
    finally:
        db.close()

    replay = idem.prepare_request(kind="STUDENT", idempotency_key=key, filename="学生导入.xlsx", user=USER)
    assert replay["idempotentReplay"] is True
    assert replay["sourceFileId"] == file_id
    assert replay["replayJob"]["id"] == job["id"]
    assert replay["replayJob"]["adapterRef"] == "BATCH-I1-IDEMPOTENT-94421"

    db = get_sessionmaker()()
    try:
        assert db.scalar(select(func.count(FileObject.id)).where(FileObject.tenant_id == TENANT_ID)) == 1
        assert db.scalar(select(func.count(ImportJob.id)).where(ImportJob.tenant_id == TENANT_ID)) == 1
    finally:
        db.close()

    with pytest.raises(AppException):
        idem.prepare_request(kind="TEACHER", idempotency_key=key, filename="教师导入.xlsx", user=USER)


def test_fileobject_crash_window_is_recovered_before_reupload():
    key = "identity-upload-students-94421-000002"
    first = idem.prepare_request(kind="STUDENT", idempotency_key=key, filename="学生导入.xlsx", user=USER)
    file_id = _source_file(first["sessionKey"])
    db = get_sessionmaker()()
    try:
        session = db.scalar(select(FileUploadSession).where(
            FileUploadSession.tenant_id == TENANT_ID,
            FileUploadSession.session_key == first["sessionKey"],
        ).with_for_update())
        session.status = "FAILED"
        db.commit()
    finally:
        db.close()

    recovered = idem.prepare_request(kind="STUDENT", idempotency_key=key, filename="学生导入.xlsx", user=USER)
    assert recovered["sourceFileId"] == file_id
    assert recovered["idempotentReplay"] is True


def test_formal_router_reserves_before_file_store_and_never_parses_on_create():
    root = Path(__file__).resolve().parents[2]
    router = (root / "backend/app/modules/system_admin/routers/data_exchange_router.py").read_text(encoding="utf-8")
    service = (root / "backend/app/modules/system_admin/services/identity_import_idempotency_service.py").read_text(encoding="utf-8")
    orchestration = (root / "backend/app/modules/system_admin/services/identity_import_control_plane_service.py").read_text(encoding="utf-8")
    frontend = (root / "frontend/src/modules/system/api/dataExchange.api.js").read_text(encoding="utf-8")

    assert 'alias="Idempotency-Key"' in router
    assert router.index("upload_idem.prepare_request(") < router.index("file_service.store_upload(")
    assert 'biz_id=str(reservation["sessionKey"])' in router
    assert "identity.create_identity_import_job(" in router
    assert "create_identity_import_scan_job(" not in router
    assert "refresh_identity_import_job(" not in router
    assert "FileUploadSession.tenant_id == tenant_id" in service
    assert ".with_for_update()" in service
    assert "except IntegrityError" in service
    assert "FileObject.biz_id == str(session.session_key)" in service
    create_body = orchestration.split("def create_identity_import_job", 1)[1].split("def read_identity_import_job", 1)[0]
    assert 'status="SCANNING"' in create_body
    assert '"workerRequired": True' in create_body
    assert "refresh_identity_import_job" not in create_body
    assert "const identityUploadKeys = new WeakMap()" in frontend
    assert "'Idempotency-Key': idempotencyKey" in frontend
    assert "return governedUploadRequest(" in frontend
