import ast
import os
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase5_python_files_parse_before_app_import():
    paths = (
        "backend/app/services/affairs_archive_service.py",
        "backend/app/services/affairs_attachment_service.py",
        "backend/app/modules/student_affairs/services/affairs_material_center_service.py",
        "backend/app/modules/student_affairs/routers/affairs_material_center.py",
        "backend/app/api/v1/affairs_operations_api.py",
        "backend/app/api/v1/router.py",
        "backend/alembic/versions/0149_affairs_material_center.py",
    )
    for path in paths:
        ast.parse(read(path), filename=path)


def test_phase5_schema_is_additive_and_keeps_legacy_fields():
    migration = read("backend/alembic/versions/0149_affairs_material_center.py")
    operations = read("backend/app/models/affairs_operations.py")
    attachment = read("backend/app/models/affairs_attachment.py")
    archive = read("backend/app/models/affairs_archive.py")

    assert 'down_revision = "0148_internship_material_center"' in migration
    for table in (
        "t_affairs_material_requirement",
        "t_affairs_material_submission",
        "t_affairs_attachment",
        "t_affairs_archive_package",
    ):
        assert table in migration
    for field in ("asset_id", "file_version_id", "binding_id", "sensitivity_level"):
        assert field in operations or field in attachment
    for legacy_field in ("affairs_attachment_id", "file_id", "file_name"):
        assert legacy_field in operations
    for field in ("package_asset_id", "package_version_id", "manifest_id", "manifest_sha256"):
        assert field in archive


def test_old_material_urls_delegate_to_the_public_facade():
    api = read("backend/app/api/v1/affairs_operations_api.py")
    assert "affairs_material_center_service as operations" in api
    for path in (
        '/student-affairs/material-requirements',
        '/student-affairs/material-requirements/{requirement_id}/review',
        '/mobile/affairs/material-requirements',
        '/mobile/affairs/material-requirements/{requirement_id}/submissions',
    ):
        assert path in api
    assert "affairs_operations_service as operations" not in api


def test_requirement_submission_and_attachment_use_public_versions():
    service = read("backend/app/modules/student_affairs/services/affairs_material_center_service.py")
    attachment = read("backend/app/services/affairs_attachment_service.py")

    for token in (
        "FileAsset", "FileVersion", "FileBinding", "asset.current_version_id",
        'source_channel="STUDENT_SUBMISSION"', "SUPERSEDED",
        "file_version_id", "binding_id",
    ):
        assert token in service
    assert "link_legacy_attachment" in attachment
    assert "center.link_legacy_attachment" in attachment
    assert "file_service.bind_file_biz" not in attachment


def test_strong_sensitive_materials_are_filtered_before_counting():
    service = read("backend/app/modules/student_affairs/services/affairs_material_center_service.py")
    resolvers = read("backend/app/services/file_access_resolvers.py")

    assert 'return "HIGHLY_SENSITIVE", "PSY_STUDENT"' in service
    assert 'return "HIGHLY_SENSITIVE", "AID_RESTRICTED"' in service
    assert "visible_biz" in service
    assert "psy_scope_ids" in service
    assert "total = int(db.scalar" in service
    assert '@register_file_resolver("MATERIAL_REQUIREMENT")' in resolvers
    assert "强敏感不接受 systemAdmin.file.manage" in resolvers
    assert "center._psy_scope_allows" in resolvers
    assert "center._require_student_scope" in resolvers


def test_archive_service_owns_true_manifest_without_runtime_replacement():
    archive = read("backend/app/services/affairs_archive_service.py")
    center = read("backend/app/modules/student_affairs/services/affairs_material_center_service.py")
    router = read("backend/app/api/v1/router.py")

    assert "center.freeze_archive_manifest" in archive
    assert "ArchiveManifest(" in center
    assert "ArchiveManifestItem(" in center
    for token in ("version_id", "file_object_id", "sha256_snapshot", "scan_result"):
        assert token in center
    for forbidden in (
        "install_archive_guard",
        "install_archive_file_guard",
        "install_affairs_operations",
        "install_affairs_operations_final_guard",
    ):
        assert forbidden not in router
    assert "archive.collect =" not in archive
    assert "archive.advance =" not in archive


def test_management_pc_uses_shared_file_sdk_and_real_manifest():
    api = read("frontend/src/modules/studentAffairs/api/operations.api.js")
    view = read("frontend/src/modules/studentAffairs/views/MaterialOperationsView.vue")

    assert "fileSdk" in api
    assert "requestBlob" not in api
    for token in ("fileVersionId", "assetId", "manifestSha256", "sensitivityLevel"):
        assert token in view
    assert "心理与困难认定材料不会先拉全量" in view
    assert "getLatestManifest" in api


def test_phase5_router_exposes_overview_backfill_and_manifest():
    router = read("backend/app/modules/student_affairs/routers/affairs_material_center.py")
    aggregator = read("backend/app/api/v1/router.py")
    for path in (
        '/student-affairs/material-center',
        '/student-affairs/material-center/backfill',
        '/student-affairs/material-center/students/{student_id}/manifest',
        '/student-affairs/archive/packages/{package_id}/manifest',
    ):
        assert path in router
    assert "affairs_material_center_router" in aggregator
    assert "affairs_material_center_router," in aggregator


def test_phase5_real_mysql_resubmit_manifest_and_sensitivity():
    if not os.getenv("DATABASE_URL") or os.getenv("DB_ENABLED", "").lower() != "true":
        pytest.skip("real MySQL is required")
    runpy.run_path(
        str(ROOT / "backend/tests/affairs_material_center_mysql_acceptance.py"),
        run_name="__main__",
    )
