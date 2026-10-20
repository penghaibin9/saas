import io
import json
import zipfile
import pytest

from app.core.exceptions import AppException
from app.modules.internship.services.internship_audit_service import _sanitize
from app.modules.internship.services.internship_evidence_package_service import (
    _build_zip,
    archive_zip_from_snapshot,
)
from app.modules.internship.services.internship_export_util import (
    SAFE_EXPORT_MAX,
    pack_export_meta,
    require_exportable,
)


def test_export_10001_is_rejected_before_projection_contract():
    with pytest.raises(AppException):
        require_exportable(SAFE_EXPORT_MAX + 1)


def test_export_metadata_is_never_silently_truncated():
    assert pack_export_meta(10, 10) == {
        "totalRows": 10, "exportedRows": 10, "truncated": False,
        "safeExportMax": SAFE_EXPORT_MAX,
    }


def test_audit_payload_hashes_sensitive_values_recursively():
    payload = _sanitize({
        "mobile": "13800138000",
        "nested": {"guardianPhone": "13900139000", "reason": "正常字段"},
        "token": "plain-secret",
    })
    assert payload["mobile"].startswith("sha256:")
    assert payload["nested"]["guardianPhone"].startswith("sha256:")
    assert payload["token"].startswith("sha256:")
    assert payload["nested"]["reason"] == "正常字段"
    assert "13800138000" not in json.dumps(payload, ensure_ascii=False)


def test_zip_contains_manifest_and_real_evidence_catalog():
    manifest = {
        "packageStatus": "READY", "packageSha256": None,
        "files": [], "missingItems": [],
    }
    data = _build_zip({
        "summary.xlsx": b"xlsx",
        "rules/compliance-rule-snapshot.json": b"{}",
        "evidence/agreements.json": b"[]",
        "audit/internship-audit.json": b"[]",
    }, manifest)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert {
            "manifest.json", "summary.xlsx",
            "rules/compliance-rule-snapshot.json",
            "evidence/agreements.json",
            "audit/internship-audit.json",
        } <= names


def test_archive_zip_embeds_package_identity_before_compression():
    data, _manifest = archive_zip_from_snapshot({
        "snapshotSchemaVersion": "INTERNSHIP_ARCHIVE_SNAPSHOT_V2",
        "capturedAt": "2026-07-26T00:00:00Z", "ruleVersion": "rv-1",
        "compliance": {"passed": True}, "audit": [], "datasets": {}, "fileRefs": [],
    }, manifest_extra={
        "packageId": "88", "packageType": "ARCHIVE", "packageVersion": 3,
        "tenantId": "1001", "targetId": "99",
    })
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        embedded = json.loads(archive.read("manifest.json"))
    assert embedded["packageId"] == "88"
    assert embedded["packageVersion"] == 3
    assert embedded["targetId"] == "99"


def test_package_versions_have_database_unique_constraint():
    from app.models import InternshipEvidencePackage
    constraints = {
        constraint.name for constraint in InternshipEvidencePackage.__table__.constraints
    }
    assert "uk_ix_evpkg_target_version" in constraints


def test_audit_outbox_event_id_has_database_unique_constraint():
    from app.models import AuditOutbox
    constraints = {constraint.name for constraint in AuditOutbox.__table__.constraints}
    assert "uk_audit_outbox_event" in constraints
