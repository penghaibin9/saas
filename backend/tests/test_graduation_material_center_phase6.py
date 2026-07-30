"""阶段 6固定门禁：编译、旧 URL优先接管、版本审核、真实 Manifest与 ZIP/Excel。"""
from __future__ import annotations

import ast
import os
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase6_python_sources_compile():
    paths = [
        "backend/app/models/graduation_material.py",
        "backend/alembic/versions/0150_graduation_material_center.py",
        "backend/app/modules/graduation/services/graduation_material_center_service.py",
        "backend/app/modules/graduation/routers/graduation_material_center.py",
        "backend/app/api/v1/mobile_graduation_material_center.py",
        "backend/app/api/v1/route_registration.py",
        "backend/tests/graduation_material_center_mysql_acceptance.py",
    ]
    for path in paths:
        ast.parse(read(path), filename=path)


def test_phase6_migration_is_single_successor_contract():
    migration = read("backend/alembic/versions/0150_graduation_material_center.py")
    models = read("backend/app/models/graduation_material.py")
    model_init = read("backend/app/models/__init__.py")
    assert 'revision = "0150_graduation_material_center"' in migration
    assert 'down_revision = "0149_affairs_material_center"' in migration
    assert '"t_gd_material_rule"' in migration
    assert '"t_gd_material_item"' in migration
    assert 'class GraduationMaterialRule' in models
    assert 'class GraduationMaterialItem' in models
    assert 'from app.models.graduation_material import GraduationMaterialItem, GraduationMaterialRule' in model_init


def test_phase6_old_urls_are_shadowed_by_priority_routers():
    registry = read("backend/app/api/v1/route_registration.py")
    staff_router = read("backend/app/modules/graduation/routers/graduation_material_center.py")
    student_router = read("backend/app/api/v1/mobile_graduation_material_center.py")
    assert registry.index("graduation_material_center.router") < registry.index("graduation_sensitive_router.router")
    assert registry.index("mobile_graduation_material_center.router") < registry.index("mobile.router")
    for path in (
        '/proposals/{proposal_id}', '/proposals/{proposal_id}/review',
        '/finals/{final_id}', '/finals/{final_id}/review',
        '/gd-archives/batch-file', '/gd-archives/{gd_student_id}/file',
    ):
        assert path in staff_router
    assert '@router.post("/proposal"' in student_router
    assert '@router.post("/final"' in student_router


def test_phase6_public_version_and_review_contract_is_authoritative():
    service = read("backend/app/modules/graduation/services/graduation_material_center_service.py")
    for token in (
        "FileAsset", "FileVersion", "FileBinding", "ArchiveManifest", "ArchiveManifestItem",
        "_require_reviewable", "_mark_review_status", "freeze_archive_manifest",
        "build_student_package", "build_batch_package", "publish_template_asset",
        "backfill_legacy", "attachments_json", "version.file_object_id != file_obj.id",
        "hashlib.sha256(data).hexdigest()", 'entries["归档索引.xlsx"]',
    ):
        assert token in service
    assert 'version.status != "APPROVED"' in service
    assert 'version.is_current' in service
    assert 'version.status = "INVALIDATED"' in service
    assert 'binding.status = "SUPERSEDED"' in service
    assert '"materialFileCount": len(payload_items)' in service
    assert '"materialFileCount": len(all_items)' in service


def test_phase6_teacher_review_ui_shows_safe_version_before_action():
    proposal = read("frontend/src/modules/graduation/views/_shared/ProposalReviewCard.vue")
    final = read("frontend/src/modules/graduation/views/FinalSubmissionListView.vue")
    api = read("frontend/src/modules/graduation/api/graduation-material-center.api.js")
    for source in (proposal, final):
        assert "当前安全版本（本次审核锁定）" in source
        assert "SecureFileList" in source
        assert "currentSafeVersions" in source
        assert "reviewReady" in source
        assert "versionId" in source and "SHA-256" in source
        assert "graduationMaterialCenterApi.previewMaterial" in source
        assert "graduationMaterialCenterApi.downloadMaterial" in source
    assert "getFinalDetail" in final
    assert "!this.finalDetail?.reviewReady" in final
    assert "/graduation/material-center/files/" in api
    assert "requestBlob" in api


def test_phase6_generic_graduation_download_remains_blocked():
    contract = read("backend/app/api/v1/file_contract.py")
    staff_router = read("backend/app/modules/graduation/routers/graduation_material_center.py")
    assert '_requires_audited_business_download' in contract
    assert '== "GRADUATION_MATERIAL"' in contract
    assert "resolve_material_download" in staff_router
    assert "GRADUATION_VERSIONED_MATERIAL_DOWNLOAD" in staff_router


def test_phase6_real_mysql_version_review_manifest_zip_excel_template(db_mode, monkeypatch):
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    assert database_url, "real MySQL test database is required"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DB_ENABLED", "true")
    script = Path(__file__).with_name("graduation_material_center_mysql_acceptance.py")
    runpy.run_path(str(script), run_name="__main__")
