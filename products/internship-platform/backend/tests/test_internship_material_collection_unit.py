"""Non-database checks for C-session filters, pinned templates and original-byte packages.

These substitutes exercise code/ZIP integrity only; they are not MySQL, scan-engine or UI acceptance.
"""
import hashlib
import json
from contextlib import nullcontext
from types import SimpleNamespace as N
from unittest.mock import MagicMock
import zipfile

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import mysql

from app.core.exceptions import AppException
from app.models import InternshipMaterialSubmission, InternshipRecord, StudentProfile, SchoolClass
from app.models.file import FileAsset, FileVersion
from app.modules.internship.services import internship_material_requirement_service as svc


def test_material_extensions_reuse_file_contract_without_allowing_unuploadable_types():
    assert svc._extensions(["pdf", "doc", "docx", "xls", "xlsx", "zip"]) == ["pdf", "doc", "docx", "xls", "xlsx", "zip"]
    assert svc._extensions([".PNG", "png"]) == ["png"]
    for ext in ("exe", "unsupported", "../pdf"):
        with pytest.raises(AppException):
            svc._extensions([ext])


def test_collection_filters_narrow_sql_and_reject_unknown_state(monkeypatch):
    monkeypatch.setattr(svc, "_tid", lambda: 11)
    query = select(InternshipRecord, StudentProfile, InternshipMaterialSubmission)
    filtered = svc._filter_students(query, state="RETURNED", keyword="_%", college_id="11",
        major_id="12", class_id="13")
    compiled = filtered.compile(dialect=mysql.dialect())
    assert set(compiled.params.values()) >= {"RETURNED", 11, 12, 13, "/_/%"}
    assert "LIKE" in str(compiled) and "ESCAPE" in str(compiled)
    assert "coalesce" in str(compiled) and SchoolClass.__tablename__ in str(compiled)
    for state in ("UNKNOWN", "APPROVED OR 1=1"):
        with pytest.raises(AppException):
            svc._filter_students(query, state=state)
    for value in (0, "wrong", "-1", True):
        with pytest.raises(AppException):
            svc._filter_students(query, class_id=value)
    missing = svc._filter_students(query, state="MISSING").compile(dialect=mysql.dialect())
    assert any(isinstance(value, (list, tuple, set)) and set(value) == {"SUBMITTED", "APPROVED"}
        for value in missing.params.values())


def setup_package(monkeypatch, tmp_path, *, bad=None, denied=False, count=6):
    from app.modules.internship.services import internship_audit_service as audit
    from app.services import storage, streaming_archive_service as streams
    rows, sources = [], {}
    # Synthetic payloads test unchanged bytes across six filenames, not validity of office formats.
    for index, ext in enumerate(["pdf", "doc", "docx", "xls", "xlsx", "zip"] * 34, start=1):
        if index > count:
            break
        data = f"并行C-材料-{index}-原字节".encode()
        path = tmp_path / f"source-{index}"
        path.write_bytes(data)
        file = N(id=index, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
            file_name=f"../并行C-材料.{ext}", file_key=str(index), status="AVAILABLE", scan_status="CLEAN", is_deleted=False)
        if bad == "digest" and index == 1:
            file.sha256 = "0" * 64
        if bad == "scan" and index == 1:
            file.scan_status = "PENDING"
        version = N(id=index + 100, version_no=2, asset_id=index + 200, is_current=True,
            file_object_id=index, status="APPROVED")
        if bad == "version" and index == 1:
            version.file_object_id = 999
        rows.append((N(asset_id=index + 200, slot_no=index),
            N(id=88, internship_id=66, student_id=77, version=4, status="APPROVED"), version, file))
        sources[str(index)] = path
    db = MagicMock()
    db.execute.return_value.all.return_value = rows
    db.scalar.return_value = None if bad == "binding" else 1
    monkeypatch.setattr(svc, "session", lambda: nullcontext(db))
    monkeypatch.setattr(svc, "_tid", lambda: 11)
    monkeypatch.setattr(svc, "_requirement", lambda *a, **kw: N(id=55, batch_id=44))
    monkeypatch.setattr(svc, "_scoped_student_query", lambda *a: select(InternshipMaterialSubmission))
    monkeypatch.setattr(audit, "assert_high_risk_write_available", lambda db: None)
    checks = []
    def require_access(file_id, **kw):
        checks.append((file_id, kw))
        if denied:
            raise AppException("NO_PERMISSION", "撤权后拒绝下载", http_status=403)
    monkeypatch.setattr(svc.file_access_service, "require_file_access", require_access)
    monkeypatch.setattr(storage, "get_backend", lambda: N(fetch_local=lambda key: sources[key]))
    created = []
    original = streams.temporary_zip
    def temporary_zip(**kw):
        path, archive = original(**kw)
        created.append(path)
        return path, archive
    monkeypatch.setattr(streams, "temporary_zip", temporary_zip)
    return db, rows, sources, checks, created


def test_process_package_preserves_original_bytes_and_audits_without_archiving(monkeypatch, tmp_path):
    db, rows, sources, checks, created = setup_package(monkeypatch, tmp_path)
    path, filename = svc.build_material_package(55, {"userType": "TEACHER", "realName": "并行C-材料"})
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("实施人员使用-版本与校验清单.json"))["items"]
            assert len(manifest) == 6 and len(checks) == 6
            for fact in manifest:
                assert archive.read(fact["archivePath"]) == sources[fact["fileId"]].read_bytes()
                assert ".." not in fact["archivePath"].split("/")
                assert fact["submissionId"] == "88" and fact["fileVersionId"]
        assert filename == "材料文件包_55.zip"
        assert db.add.call_args.args[0].action == "MATERIAL_PACKAGE_DOWNLOAD"
        db.commit.assert_called_once()
        sql = str(db.execute.call_args.args[0].compile(dialect=mysql.dialect()))
        assert "FOR UPDATE" in sql and "LIMIT" in sql
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("bad", ["scan", "digest", "version", "binding"])
def test_package_failures_remove_partial_file_and_never_commit(monkeypatch, tmp_path, bad):
    db, _, _, _, created = setup_package(monkeypatch, tmp_path, bad=bad)
    with pytest.raises(AppException):
        svc.build_material_package(55, {"userType": "TEACHER"})
    assert created and all(not path.exists() for path in created)
    db.commit.assert_not_called()


def test_revoked_file_permission_and_oversized_package_fail_closed(monkeypatch, tmp_path):
    db, _, _, _, created = setup_package(monkeypatch, tmp_path, denied=True)
    with pytest.raises(AppException):
        svc.build_material_package(55, {"userType": "TEACHER"})
    assert all(not path.exists() for path in created)
    db.commit.assert_not_called()
    db, _, _, _, created = setup_package(monkeypatch, tmp_path, count=201)
    with pytest.raises(AppException):
        svc.build_material_package(55, {"userType": "TEACHER"})
    assert not created
    db.commit.assert_not_called()


def test_pinned_template_download_uses_requested_version_and_verifies_bytes(monkeypatch, tmp_path):
    path = tmp_path / "template"
    path.write_bytes(b"parallel-C-template-v1")
    requirement = N(id=55, batch_id=44, status="PUBLISHED", audience_type="ALL", audience_filter_json={})
    old = N(id=101, file_id=99, file_name_snapshot="并行C-材料-第一版.pdf",
        sha256_snapshot=hashlib.sha256(path.read_bytes()).hexdigest())
    db = MagicMock()
    db.scalar.side_effect = [old, 1]
    monkeypatch.setattr(svc, "session", lambda: nullcontext(db))
    monkeypatch.setattr(svc, "_tid", lambda: 11)
    monkeypatch.setattr(svc, "_requirement", lambda *a, **kw: requirement)
    monkeypatch.setattr(svc, "require_explicit_context", lambda *a, **kw: (N(batch_id=44), N(id=77), None))
    resolve = MagicMock(return_value=(path, "current-name.pdf"))
    monkeypatch.setattr(svc.file_service, "resolve_download", resolve)
    result = svc.template_download(55, {"userType": "STUDENT"}, batch_id=44,
        internship_id=66, template_version_id="101")
    assert result == (path, old.file_name_snapshot)
    resolve.assert_called_once_with("99", user={"userType": "STUDENT"})
    params = db.scalar.call_args_list[0].args[0].compile(dialect=mysql.dialect()).params
    assert 101 in params.values() and 55 in params.values() and 11 in params.values()
    db.scalar.side_effect = [old, 1]
    path.write_bytes(b"changed-template")
    with pytest.raises(AppException, match="指定版本"):
        svc.template_download(55, {"userType": "STUDENT"}, batch_id=44,
            internship_id=66, template_version_id="101")


def test_unknown_template_version_does_not_fall_back_to_latest(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setattr(svc, "session", lambda: nullcontext(db))
    monkeypatch.setattr(svc, "_tid", lambda: 11)
    monkeypatch.setattr(svc, "_requirement", lambda *a, **kw: N(id=55, batch_id=44, status="PUBLISHED", audience_type="ALL", audience_filter_json={}))
    monkeypatch.setattr(svc, "require_explicit_context", lambda *a, **kw: (N(batch_id=44), N(id=77), None))
    latest = MagicMock()
    monkeypatch.setattr(svc, "_template", latest)
    with pytest.raises(AppException):
        svc.template_download(55, {"userType": "STUDENT"}, batch_id=44, internship_id=66,
            template_version_id="999")
    latest.assert_not_called()


def test_material_readiness_never_invents_a_scan_result():
    from app.modules.internship.services.internship_material_center_service import _file_ready, _version_state
    file = N(is_deleted=False, status="AVAILABLE", scan_status=None)
    for scan in (None, "", "PENDING", "SCANNING", "INFECTED", "ERROR", "UNKNOWN"):
        file.scan_status = scan
        assert not _file_ready(file)
        assert _version_state(file, "APPROVED") == ("REJECTED" if scan in {"INFECTED", "ERROR"} else "SCANNING")
    for scan in ("CLEAN", "NOT_REQUIRED"):
        file.scan_status = scan
        assert _file_ready(file)
        assert _version_state(file, "APPROVED") == "APPROVED"
    file.is_deleted = True
    assert not _file_ready(file)


@pytest.mark.parametrize("bad", ["missing_scan", "pending", "infected", "deleted", "digest", "revoked"])
def test_publish_rechecks_template_safety_and_permission_before_any_transition(monkeypatch, bad):
    db = MagicMock()
    row = N(id=55, batch_id=44, status="DRAFT", version=0)
    template = N(file_id=99, sha256_snapshot="current-template-digest")
    file = N(id=99, is_deleted=False, status="AVAILABLE", scan_status="CLEAN", sha256=template.sha256_snapshot)
    if bad == "missing_scan":
        file.scan_status = None
    elif bad == "pending":
        file.scan_status = "PENDING"
    elif bad == "infected":
        file.scan_status = "INFECTED"
    elif bad == "deleted":
        file.is_deleted = True
    elif bad == "digest":
        file.sha256 = "changed-template-digest"
    access = MagicMock(return_value=file)
    if bad == "revoked":
        access.side_effect = AppException("NO_PERMISSION", "并行C-材料模板授权已撤销", http_status=403)
    monkeypatch.setattr(svc, "session", lambda: nullcontext(db))
    monkeypatch.setattr(svc, "_requirement", lambda *a, **kw: row)
    monkeypatch.setattr(svc, "_template", lambda *a: template)
    monkeypatch.setattr(svc.file_access_service, "require_file_access", access)
    user = {"userType": "SCHOOL_ADMIN", "realName": "并行C-材料"}
    with pytest.raises(AppException):
        svc.publish_requirement(55, user)
    access.assert_called_once_with("99", user=user, action="download")
    assert row.status == "DRAFT" and row.version == 0
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_publish_ready_template_keeps_the_existing_transition_and_audit(monkeypatch):
    db = MagicMock()
    row = N(id=55, batch_id=44, material_code="PARALLEL_C_MATERIAL_001", status="DRAFT", version=0)
    template = N(file_id=99, sha256_snapshot="current-template-digest")
    file = N(id=99, is_deleted=False, status="AVAILABLE", scan_status="CLEAN", sha256=template.sha256_snapshot)
    monkeypatch.setattr(svc, "session", lambda: nullcontext(db))
    monkeypatch.setattr(svc, "_tid", lambda: 11)
    monkeypatch.setattr(svc, "_requirement", lambda *a, **kw: row)
    monkeypatch.setattr(svc, "_template", lambda *a: template)
    monkeypatch.setattr(svc.file_access_service, "require_file_access", lambda *a, **kw: file)
    monkeypatch.setattr(svc, "_requirement_view", lambda db, row: {"id": str(row.id), "status": row.status})
    assert svc.publish_requirement(55, {"userType": "SCHOOL_ADMIN"}) == {"id": "55", "status": "PUBLISHED"}
    assert row.version == 1 and db.add.call_args.args[0].action == "REQUIREMENT_PUBLISH"
    db.commit.assert_called_once()


@pytest.mark.parametrize("action", ["APPROVE", "RETURN"])
def test_review_missing_scan_cannot_use_a_legacy_ready_metadata_fallback(monkeypatch, action):
    from app.modules.internship.services import internship_scope
    db = MagicMock()
    row = N(id=88, requirement_id=55, internship_id=66, version=4, status="SUBMITTED")
    version = N(id=199, status="SUBMITTED", version=2)
    file = N(id=99, is_deleted=False, status="AVAILABLE", scan_status=None)
    db.scalar.return_value = row
    db.get.side_effect = [version, file]
    monkeypatch.setattr(svc, "session", lambda: nullcontext(db))
    monkeypatch.setattr(svc, "_tid", lambda: 11)
    monkeypatch.setattr(svc, "_submission_files", lambda *a: [N(current_version_id=199, file_id=99, slot_no=1)])
    monkeypatch.setattr(internship_scope, "assert_internship_record_scope", lambda *a, **kw: N(id=66))
    meta = MagicMock(return_value={"fileId": "99", "readyForBusiness": True, "scanStatus": None})
    monkeypatch.setattr(svc.file_service, "get_file_meta", meta)
    with pytest.raises(AppException, match="安全就绪"):
        svc.review_submission(88, {"action": action, "expectedVersion": 4, "comment": "并行C-材料安全缺失"},
                              {"userType": "TEACHER"})
    assert row.status == "SUBMITTED" and row.version == 4
    assert version.status == "SUBMITTED" and version.version == 2
    meta.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("status,restoring", [("RETURNED", False), ("DRAFT", False), ("RETURNED", True)])
def test_resubmit_retires_removed_files_and_reuses_restored_slots(monkeypatch, status, restoring):
    db = MagicMock()
    requirement = N(id=3, batch_id=19, status="PUBLISHED", audience_type="ALL", audience_filter_json={},
        material_code="PARALLEL_C_MATERIAL_001", allowed_extensions_json=["pdf"], min_files=1, max_files=6)
    student = N(id=20, real_name="并行C-材料学生", college_id=3, class_id=3)
    record = N(id=20, batch_id=19)
    submission = N(id=3, status=status, version=2)
    slots = [N(slot_no=i, asset_id=8+i, current_version_id=10+i, file_id=87+i,
        version=0, is_deleted=False) for i in (1, 2)]
    versions = {10+i: N(id=10+i, is_current=True, status="REJECTED") for i in (1, 2)}
    assets = {8+i: N(id=8+i, current_version_id=10+i, version_count=1, version=0) for i in (1, 2)}
    bindings = [N(is_current=True, status="ACTIVE") for _ in slots]
    if restoring:
        slots[0].is_deleted = True
        versions[11].is_current = False
        versions[11].invalidated_at = "original-retirement"
        assets[9].current_version_id = None
        bindings[0].is_current = False
        bindings[0].status = "SUPERSEDED"
    db.get.side_effect = lambda model, key: (versions if model is FileVersion else assets)[key]
    db.scalar.return_value = 1
    db.scalars.return_value.all.side_effect = [[bindings[1]]] if restoring else [[bindings[0]], [bindings[1]]]
    def add(row):
        if isinstance(row, FileVersion):
            row.id = 20
    db.add.side_effect = add
    monkeypatch.setattr(svc, "session", lambda: nullcontext(db))
    monkeypatch.setattr(svc, "_tid", lambda: 12)
    monkeypatch.setattr(svc, "require_explicit_context", lambda *a, **kw: (record, student, None))
    monkeypatch.setattr(svc, "_requirement", lambda *a, **kw: requirement)
    monkeypatch.setattr(svc, "_submission", lambda *a, **kw: submission)
    monkeypatch.setattr(svc, "_submission_files", lambda *a, include_deleted=False:
        slots if include_deleted else [item for item in slots if not item.is_deleted])
    monkeypatch.setattr(svc, "_asset", lambda *a: assets[9])
    monkeypatch.setattr(svc.file_access_service, "require_file_access", lambda *a, **kw: N(id=98, ext="pdf"))
    monkeypatch.setattr(svc.file_business_binding_service, "bind_file_to_business", lambda *a, **kw: N())
    monkeypatch.setattr(svc, "_trail", lambda *a, **kw: None)
    monkeypatch.setattr(svc, "_submission_view", lambda db, row: {"id": str(row.id), "version": row.version})
    assert svc.submit_material({"userType": "STUDENT", "userId": "39"}, 3,
        {"fileIds": ["98"], "expectedVersion": 2}) == {"id": "3", "version": 3}
    assert submission.status == "SUBMITTED" and slots[0].file_id == 98 and not slots[0].is_deleted
    assert slots[1].is_deleted and not versions[12].is_current
    assert versions[12].status == ("REJECTED" if status == "RETURNED" else "INVALIDATED")
    assert all(not item.is_current and item.status == "SUPERSEDED" for item in bindings)
    assert assets[10].current_version_id is None and assets[10].version_count == 1
    if restoring:
        assert versions[11].invalidated_at == "original-retirement"
    db.commit.assert_called_once()
