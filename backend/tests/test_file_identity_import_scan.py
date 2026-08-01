from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import delete

from app.core.config import settings
from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models.data_exchange import ImportJob, ImportRowError
from app.models.file import FileObject
from app.services import storage
from app.services.identity_import_path_parser import parse_identity_xlsx_path
from app.services.identity_import_scan_orchestrator import (
    create_identity_import_scan_job,
    refresh_identity_import_job,
)

TENANT_ID = 93991
USER = {
    "tenantId": str(TENANT_ID),
    "userId": "939",
    "realName": "身份导入扫描测试",
    "userType": "ADMIN",
    "currentRoleCode": "SCHOOL_ADMIN",
    "permissions": ["*"],
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
        db.execute(delete(ImportJob).where(ImportJob.tenant_id == TENANT_ID))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()
    yield
    db = get_sessionmaker()()
    try:
        db.execute(delete(ImportRowError).where(ImportRowError.tenant_id == TENANT_ID))
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
    key = f"identity-scan/{status}-{scan_status}.xlsx"
    staged = backend.staging_path(key)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(body)
    backend.persist(key, staged)
    db = get_sessionmaker()()
    try:
        row = FileObject(
            tenant_id=TENANT_ID,
            file_key=key,
            file_name="学生导入.xlsx",
            ext="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=len(body),
            sha256="a" * 64,
            biz_type="DATA_IMPORT_SOURCE",
            status=status,
            storage_backend="local",
            storage_zone="QUARANTINE" if status == "QUARANTINED" else "ACTIVE",
            scan_required=scan_status != "NOT_REQUIRED",
            scan_status=scan_status,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    finally:
        db.close()


def test_scanning_file_never_calls_parser(monkeypatch):
    file_id = _source_file(status="QUARANTINED", scan_status="PENDING")
    called = {"parse": 0}

    def forbidden(*_args, **_kwargs):
        called["parse"] += 1
        raise AssertionError("scanner pending file must not be parsed")

    monkeypatch.setattr(
        "app.services.identity_import_scan_orchestrator.parse_identity_xlsx_path",
        forbidden,
    )
    job = create_identity_import_scan_job(
        kind="STUDENT",
        source_file_id=file_id,
        filename="学生导入.xlsx",
        user=USER,
    )
    assert job["status"] == "SCANNING"
    assert called["parse"] == 0
    refreshed = refresh_identity_import_job(job["id"], user=USER)
    assert refreshed["status"] == "SCANNING"
    assert called["parse"] == 0


def test_clean_file_parses_once_and_converts_same_job(monkeypatch):
    file_id = _source_file(status="AVAILABLE", scan_status="CLEAN")
    calls = {"parse": 0, "preview": 0, "batch": 0}

    def parse_stub(path, filename, kind):
        calls["parse"] += 1
        assert Path(path).is_file()
        assert filename == "学生导入.xlsx"
        assert kind == "STUDENT"
        return {
            "students": [{"_rowNo": 2, "studentNo": "20260001", "name": "测试学生", "className": "软件2601"}],
            "teachers": [],
            "rawRows": [{"row": 2, "accountType": "STUDENT", "accountNo": "20260001", "name": "测试学生"}],
            "relationships": [],
            "relationErrors": [],
            "errors": [],
            "totalRows": 1,
            "importKind": "STUDENT",
            "fileName": filename,
            "fileSha256": "b" * 64,
        }

    def preview_stub(_user, payload, pre_errors=None):
        calls["preview"] += 1
        assert payload["students"][0]["studentNo"] == "20260001"
        assert pre_errors == []
        return {"total": 1, "valid": 1, "invalid": 0, "errors": []}

    def batch_stub(_user, parsed, report):
        calls["batch"] += 1
        assert parsed["totalRows"] == 1
        assert report["valid"] == 1
        return {
            "batchNo": "IDENTITY-SCAN-93991",
            "total": 1,
            "valid": 1,
            "invalid": 0,
            "errors": [],
            "relations": {"errors": []},
            "roleTemplateVersion": "test",
        }

    monkeypatch.setattr(
        "app.services.identity_import_scan_orchestrator.parse_identity_xlsx_path",
        parse_stub,
    )
    monkeypatch.setattr(
        "app.services.identity_import_service.preview_identity_import",
        preview_stub,
    )
    monkeypatch.setattr(
        "app.services.identity_import_file_service.create_batch",
        batch_stub,
    )
    job = create_identity_import_scan_job(
        kind="STUDENT",
        source_file_id=file_id,
        filename="学生导入.xlsx",
        user=USER,
    )
    assert job["status"] == "VALIDATED"
    assert job["adapterType"] == "IDENTITY_IMPORT_BATCH"
    assert job["adapterRef"] == "IDENTITY-SCAN-93991"
    assert job["sourceFileId"] == str(file_id)
    same = refresh_identity_import_job(job["id"], user=USER)
    assert same["id"] == job["id"]
    assert same["status"] == "VALIDATED"
    assert calls == {"parse": 1, "preview": 1, "batch": 1}


def test_path_parser_reads_real_xlsx_without_whole_file_buffer(tmp_path):
    path = tmp_path / "学生导入.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "导入模板"
    sheet.append(["学号", "姓名", "所属学院", "所属专业", "班级名称", "年级", "性别", "身份证号"])
    sheet.append(["20260001", "测试学生", "信息学院", "软件技术", "软件2601", "2026", "男", ""])
    workbook.save(path)
    workbook.close()

    parsed = parse_identity_xlsx_path(path, path.name, "STUDENT")
    assert parsed["totalRows"] == 1
    assert parsed["students"][0]["studentNo"] == "20260001"
    assert len(parsed["fileSha256"]) == 64


def test_api_and_parser_freeze_scan_before_parse_and_no_whole_upload_join():
    root = Path(__file__).resolve().parents[2]
    api = (root / "backend/app/api/v1/data_exchange.py").read_text(encoding="utf-8")
    parser = (root / "backend/app/services/identity_import_path_parser.py").read_text(encoding="utf-8")
    orchestrator = (root / "backend/app/services/identity_import_scan_orchestrator.py").read_text(encoding="utf-8")
    assert "file_service.store_upload(" in api
    assert "create_identity_import_scan_job(" in api
    assert api.index("file_service.store_upload(") < api.index("create_identity_import_scan_job(")
    assert "_read_identity_file" not in api
    assert 'b"".join' not in api
    assert "parse_student_xlsx(content" not in api
    assert "parse_teacher_xlsx(content" not in api
    assert "load_workbook(path" in parser
    assert ".read_bytes(" not in parser
    assert 'b"".join' not in parser
    assert "READY_SCAN_STATES" in orchestrator
    assert 'row.status = "PARSING"' in orchestrator
