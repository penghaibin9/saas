"""阶段 6固定门禁：编译、业务架构、旧 URL、权限、真实 MySQL与四端合同。"""
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
        "backend/alembic/versions/0150_graduation_material_center.py",
        "backend/alembic/versions/0151_graduation_manifest_evidence.py",
        "backend/app/models/graduation_material.py",
        "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
        "backend/app/modules/graduation/services/graduation_material_center_service.py",
        "backend/app/modules/graduation/services/graduation_material_export_service.py",
        "backend/app/modules/graduation/services/graduation_material_ticket_service.py",
        "backend/app/modules/graduation/routers/graduation_material_center.py",
        "backend/app/api/v1/mobile_graduation_material_center.py",
        "backend/app/services/file_access_resolvers.py",
        "backend/tests/graduation_material_center_mysql_acceptance.py",
    ]
    for path in paths:
        ast.parse(read(path), filename=path)


def test_phase6_migration_and_models_are_complete_mysql_contracts():
    migration = read("backend/alembic/versions/0150_graduation_material_center.py")
    evidence = read("backend/alembic/versions/0151_graduation_manifest_evidence.py")
    models = read("backend/app/models/graduation_material.py")
    model_init = read("backend/app/models/__init__.py")
    assert 'revision = "0150_graduation_material_center"' in migration
    assert 'down_revision = "0149_affairs_material_center"' in migration
    assert 'revision = "0151_graduation_manifest_evidence"' in evidence
    assert 'down_revision = "0150_graduation_material_center"' in evidence
    assert "requires MySQL" in migration and "requires MySQL" in evidence
    for table in (
        "t_gd_material_rule",
        "t_gd_material_item",
        "t_gd_student_material",
        "t_gd_material_backfill_checkpoint",
        "t_gd_template_asset_policy",
    ):
        assert table in migration
    assert "uk_gd_student_material_code" in migration
    assert "ix_gd_student_material_status" in migration
    assert "class GraduationStudentMaterial" in models
    assert "class GraduationMaterialBackfillCheckpoint" in models
    assert "class GraduationTemplateAssetPolicy" in models
    assert "GraduationStudentMaterial" in model_init
    assert "GraduationMaterialBackfillCheckpoint" in model_init
    assert "GraduationTemplateAssetPolicy" in model_init
    assert "uploader_snapshot" in evidence
    assert "submitted_at_snapshot" in evidence
    assert "不在 Alembic 事务中执行历史附件回填" in migration


def test_phase6_material_catalog_covers_all_required_business_types():
    service = read("backend/app/modules/graduation/services/graduation_material_catalog_service.py")
    required_codes = {
        "TOPIC_ATTACHMENT", "TASKBOOK", "PROPOSAL_REPORT", "PROPOSAL_DEFENSE",
        "GUIDANCE_RECORD", "MIDTERM_REPORT", "THESIS_DRAFT", "THESIS_FINAL",
        "DESIGN_WORK", "SOURCE_CODE", "WORK_DESCRIPTION", "PLAGIARISM_REPORT",
        "REVIEW_ATTACHMENT", "DEFENSE_RECORD", "DEFENSE_SIGNED_SHEET",
        "GRADE_MATERIAL", "TEMPLATE_REFERENCE", "FINAL_ARCHIVE_PACKAGE",
    }
    for code in required_codes:
        assert f'"materialCode": "{code}"' in service
    for field in (
        "allowedExtensions", "maxSizeBytes", "reviewRequired", "archiveRequired",
        "sensitivityLevel", "ownerRole", "required",
    ):
        assert field in service
    assert 'old.status = "INVALIDATED"' in service
    assert 'old.status = "SUPERSEDED"' in service
    assert "FileVersion.is_current.is_(True)" in service
    assert "expected_version" in service
    assert "fileVersionId" in service
    assert "_require_file_ready" in service
    assert "GraduationStudentMaterial" in service


def test_phase6_dedicated_resolver_blocks_generic_file_admin_bypass():
    resolver = read("backend/app/services/file_access_resolvers.py")
    generic_registration = resolver.split("@register_file_resolver(\n    \"INTERNSHIP\"", 1)[1].split(")\ndef scoped_binding_resolver", 1)[0]
    assert '"GRADUATION_MATERIAL"' not in generic_registration
    assert '@register_file_resolver("GRADUATION_MATERIAL")' in resolver
    graduation_block = resolver.split('@register_file_resolver("GRADUATION_MATERIAL")', 1)[1].split('@register_file_resolver("GRADUATION_TEMPLATE")', 1)[0]
    assert "assert_student_access" in graduation_block
    assert "resolve_current_gd_student" in graduation_block
    assert "systemAdmin.file.manage" in graduation_block
    assert "_is_file_admin" not in graduation_block
    assert '@register_file_resolver("GRADUATION_ARCHIVE_PACKAGE", "GRADUATION_ARCHIVE_INDEX")' in resolver


def test_phase6_old_urls_are_shadowed_and_authoritative_routes_exist():
    registry = read("backend/app/api/v1/route_registration.py")
    staff_router = read("backend/app/modules/graduation/routers/graduation_material_center.py")
    student_router = read("backend/app/api/v1/mobile_graduation_material_center.py")
    assert registry.index("graduation_material_center.router") < registry.index("graduation_sensitive_router.router")
    assert registry.index("mobile_graduation_material_center.router") < registry.index("mobile.router")
    for path in (
        '/proposals/{proposal_id}', '/proposals/{proposal_id}/review',
        '/finals/{final_id}', '/finals/{final_id}/review',
        '/gd-archives/batch-file', '/gd-archives/{gd_student_id}/file',
        '/material-center/overview', '/material-center/students/{gd_student_id}/library',
        '/material-center/materials/{material_code}/submit',
        '/material-center/materials/{material_id}/review',
        '/material-center/exports', '/material-center/templates',
    ):
        assert path in staff_router
    assert '@router.post("/proposal"' in student_router
    assert '@router.post("/final"' in student_router
    assert "catalog.sync_record" in staff_router
    assert "freeze_manifest" in staff_router
    assert "create_export_job" in staff_router
    assert "create_download_ticket" in staff_router
    assert "LARGE_PC_ONLY_CODES" in student_router
    assert "PC_REQUIRED" in student_router


def test_phase6_public_version_review_and_ticket_contract_is_authoritative():
    legacy = read("backend/app/modules/graduation/services/graduation_material_center_service.py")
    catalog = read("backend/app/modules/graduation/services/graduation_material_catalog_service.py")
    ticket = read("backend/app/modules/graduation/services/graduation_material_ticket_service.py")
    for token in (
        "FileAsset", "FileVersion", "FileBinding", "_require_reviewable",
        "_mark_review_status", "attachments_json", "version.file_object_id != file_obj.id",
    ):
        assert token in legacy
    assert 'version.status = "INVALIDATED"' in legacy
    assert 'binding.status = "SUPERSEDED"' in legacy
    assert "last_reviewed_version_id" in catalog
    assert "expected_file_version_id" in catalog
    assert "legacy_center._require_file_ready(file_obj)" in catalog
    assert "require_file_access" in ticket
    assert "consume_ticket" in ticket
    assert "毕业设计材料不存在" in ticket
    assert "TICKET_TTL_SECONDS" in ticket


def test_phase6_manifest_export_is_version_driven_streamed_and_revocable():
    service = read("backend/app/modules/graduation/services/graduation_material_export_service.py")
    model = read("backend/app/models/file.py")
    for marker in (
        "ArchiveManifest(", "ArchiveManifestItem(", "fileVersionId", "sha256_snapshot",
        "uploader_snapshot", "submitted_at_snapshot", "Workbook(write_only=True)",
        "allowZip64=True", "sanitize_filename", "ExportJob(",
        "manifest.json", "档案清单.xlsx", "ZIP 文件数与 Manifest 不一致",
        'job.status = "REVOKED"', 'file_obj.status = "INVALIDATED"',
    ):
        assert marker in service
    assert "uploader_snapshot" in model
    assert "submitted_at_snapshot" in model
    assert "archive.write(source, archive_path)" in service
    assert "actual_sha != item.sha256_snapshot" in service
    assert "source.read()" not in service
    assert "base64" not in service.lower()
    assert "value.startswith((\"=\", \"+\", \"-\", \"@\"))" in service


def test_phase6_backfill_is_paged_dry_run_idempotent_and_reports_differences():
    service = read("backend/app/modules/graduation/services/graduation_material_catalog_service.py")
    for marker in (
        "GraduationMaterialBackfillCheckpoint", "cursor_model", "cursor_id",
        "page_size", "dry_run", "ALREADY_BOUND", "FILE_NOT_FOUND",
        "EMPTY_ATTACHMENTS", "differences", "PARTIAL_FAILED",
    ):
        assert marker in service
    assert "limit(page_size)" in service
    assert "FileVersion.file_object_id == int(file_obj.id)" in service


def test_phase6_teacher_review_ui_shows_safe_version_before_action():
    proposal = read("frontend/src/modules/graduation/views/_shared/ProposalReviewCard.vue")
    final = read("frontend/src/modules/graduation/views/FinalSubmissionListView.vue")
    api = read("frontend/src/modules/graduation/api/graduation-material-center.api.js")
    page = read("frontend/src/modules/graduation/views/GraduationMaterialCenterView.vue")
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
    assert "SecureFileList" in page
    assert "FileVersionTimeline" in page
    assert "allowedActions" in page or "canPreview" in page
    assert "fileSdk.previewFrom" in api
    assert "fileSdk.downloadFrom" in api
    for source in (proposal, final, api, page):
        assert "localStorage.getItem('access_token')" not in source
        assert "Authorization: Bearer" not in source
        assert "window.URL.createObjectURL" not in source


def test_phase6_student_pc_material_library_is_server_authoritative():
    api = read("student-portal/src/services/portalApi.js")
    page = read("student-portal/src/views/graduation/GraduationMaterialsView.vue")
    sdk = read("student-portal/src/services/fileSdk.js")
    routes = read("student-portal/src/router/index.js")
    layout = read("student-portal/src/layouts/PortalLayout.vue")
    assert "graduationMaterialLibrary" in api
    assert "submitGraduationMaterial" in api
    assert "issueGraduationMaterialTicket" in api
    assert "退回原因" in page and "历史版本" in page
    assert "downloadFrom" in sdk
    assert "graduation/materials" in routes
    assert "graduation-material-library" in layout
    assert "GRADUATION_MATERIAL" in api


def test_phase6_generic_graduation_download_remains_blocked():
    contract = read("backend/app/api/v1/file_contract.py")
    staff_router = read("backend/app/modules/graduation/routers/graduation_material_center.py")
    assert "_requires_audited_business_download" in contract
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
