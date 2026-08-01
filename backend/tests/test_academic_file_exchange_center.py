from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models.file import FileObject
from app.modules.academic_affairs.routers.academic_file_exchange_router import ConfirmRequest, router
from app.modules.academic_affairs.services import academic_file_exchange_service as exchange
from app.services import data_exchange_confirm_service as confirm_service

TENANT_ID = 1000000000000000001


def test_academic_confirm_contract_forbids_frontend_rows():
    assert ConfirmRequest(expectedVersion=2).expectedVersion == 2
    with pytest.raises(ValidationError):
        ConfirmRequest(expectedVersion=2, rows=[{"studentNo": "S001"}])
    with pytest.raises(ValidationError):
        ConfirmRequest(expectedVersion=2, batchNo="legacy")


def test_academic_exchange_routes_are_registered_as_job_contracts():
    signatures = {
        (route.path, frozenset((route.methods or set()) - {"HEAD", "OPTIONS"}))
        for route in router.routes
    }
    assert ("/academic-affairs/file-exchange/roster/import-jobs", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/grade-tasks/{task_id}/import-jobs", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/schedule-batches/{batch_id}/import-jobs", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/imports/{job_id}/confirm", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/roster/export-jobs", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/exports/{job_id}/download-ticket", frozenset({"POST"})) in signatures
    assert ("/academic-affairs/file-exchange/exports/{job_id}/revoke", frozenset({"POST"})) in signatures


def test_create_job_never_parses_quarantined_xlsx_source():
    source = inspect.getsource(exchange.create_academic_import_job)
    assert 'status="SCANNING"' in source
    assert '"authority": "SOURCE_FILE_OBJECT"' in source
    assert "read_xlsx" not in source
    assert "roster_import_read" not in source
    assert "grade_import_dry_run" not in source
    assert "sanitize_import_rows" not in source
    assert '"rows"' not in source

    refresh_source = inspect.getsource(exchange.refresh_import_job)
    source_reader = inspect.getsource(exchange._source_file_path)
    parser_source = inspect.getsource(exchange._parse_and_validate)
    assert "_source_file_path" in refresh_source
    assert "assert_file_ready_for_business" in source_reader
    assert "_read_xlsx_path" in parser_source
    assert "grade_import_dry_run" in parser_source
    assert "sanitize_import_rows" in parser_source


def test_quarantined_file_remains_scanning_without_preview_parse(db_mode):
    user = {
        "tenantId": str(TENANT_ID),
        "userId": "81001",
        "realName": "权威导入测试",
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_ADMIN",
        "permissions": ["*"],
        "dataScope": "ALL",
    }
    set_tenant({"tenantId": str(TENANT_ID)})
    set_current_user(user)
    db = get_sessionmaker()()
    try:
        file_row = FileObject(
            tenant_id=TENANT_ID,
            file_key="quarantine/academic/test.xlsx",
            file_name="test.xlsx",
            ext="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=128,
            biz_type="ACADEMIC_ROSTER_IMPORT_SOURCE",
            owner_user_id=81001,
            visibility="PRIVATE",
            security_level="SENSITIVE",
            status="QUARANTINED",
            storage_backend="local",
            storage_zone="QUARANTINE",
            scan_required=True,
            scan_status="PENDING",
        )
        db.add(file_row)
        db.commit()
        db.refresh(file_row)
        file_id = int(file_row.id)
    finally:
        db.close()

    result = exchange.create_academic_import_job(
        filename="test.xlsx",
        source_file_id=file_id,
        import_type=exchange.ACADEMIC_ROSTER_IMPORT,
        context={},
        user=user,
    )
    assert result["status"] == "SCANNING"
    assert result["totalRows"] == 0
    assert result["preview"]["rows"] == []
    assert result["preview"]["errors"] == []

    db = get_sessionmaker()()
    try:
        from app.models.data_exchange import ImportJob
        job = db.get(ImportJob, int(result["id"]))
        snapshot = dict(job.source_snapshot_json or {})
        assert snapshot["authority"] == "SOURCE_FILE_OBJECT"
        assert "rows" not in snapshot
        assert "rowDigest" not in snapshot
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_excel_dispatch_has_explicit_academic_adapter_whitelist():
    source = inspect.getsource(confirm_service.confirm_import_job)
    for import_type in ("ACADEMIC_ROSTER", "ACADEMIC_GRADE", "ACADEMIC_SCHEDULE"):
        assert import_type in source
    assert "confirm_academic_import" in source
    assert "assert_file_ready_for_business" in source
    assert "尚未迁移到服务端权威确认" in source


def test_authoritative_confirm_reloads_and_revalidates_same_file():
    source = inspect.getsource(exchange.confirm_academic_import)
    assert "_source_file_path" in source
    assert "_parse_and_validate" in source
    assert "_row_digest" in source
    assert "解析结果已变化" in source
    assert "roster_import_confirm" in source
    assert "grade_import_confirm" in source
    assert "schedule.import_items" in source


def test_academic_export_is_file_object_and_job_not_blob_contract():
    source = inspect.getsource(exchange.create_roster_export_job)
    assert "jobs._write_generated_file" in source
    assert "ExportJob(" in source
    assert 'status="SUCCEEDED"' in source
    assert "expires_at=" in source
