from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase4_models_and_migration_are_additive():
    model = read("backend/app/models/file.py")
    migration = read("backend/alembic/versions/0148_internship_material_center.py")
    for name in ("class FileAsset", "class FileVersion", "class ArchiveManifest", "class ArchiveManifestItem"):
        assert name in model
    for table in ("t_file_asset", "t_file_version", "t_archive_manifest", "t_archive_manifest_item"):
        assert table in migration
    assert 'down_revision = "0147_data_exchange_jobs"' in migration
    assert 'op.add_column("t_file_binding"' in migration
    assert "uk_file_binding_version_relation" in migration


def test_material_adapter_uses_real_relations_and_system_snapshots():
    facade = read("backend/app/modules/internship/services/internship_material_center_facade.py")
    core = read("backend/app/modules/internship/services/internship_material_center_service.py")
    assert "投诉记录没有 internship_id" in facade
    assert "InternshipComplaint.student_id == record.student_id" in facade
    assert "InternshipComplaint.batch_id == record.batch_id" in facade
    assert "INTERNSHIP_PROCESS_REPORT_SNAPSHOT_V1" in core
    assert 'source_channel="SYSTEM_GENERATED"' in facade
    assert "sourceBusinessVersion" in core


def test_scanning_and_infected_files_are_blocked_before_review_or_archive():
    core = read("backend/app/modules/internship/services/internship_material_center_service.py")
    facade = read("backend/app/modules/internship/services/internship_material_center_facade.py")
    router = read("backend/app/modules/internship/routers/internship_material_center.py")
    assert 'READY_SCAN = {"CLEAN", "NOT_REQUIRED"}' in core
    assert "材料仍在安全扫描、扫描失败或已检出风险，不能核验通过" in core
    assert "存在扫描中、扫描失败、病毒或无法解析的材料，禁止归档" in facade
    assert "preflight_agreement" in router
    assert "preflight_insurance" in router
    assert "preflight_process_report" in router
    assert "prepare_archive_manifest" in router


def test_safety_router_precedes_legacy_routes():
    registration = read("backend/app/api/v1/route_registration.py")
    guard_import = registration.index("internship_match, internship_material_center")
    guard_include = registration.index("api_router.include_router(internship_material_center.router")
    legacy_loop = registration.index("for r in (", guard_include)
    assert guard_import < guard_include < legacy_loop
    router = read("backend/app/modules/internship/routers/internship_material_center.py")
    for path in (
        '/agreements/{agreement_id}/school-confirm',
        '/insurances/{insurance_id}/verify',
        '/process-reports/{report_id}/review',
        '/archive/{internship_id}/archive',
        '/archive/{internship_id}/package',
        '/archive/{internship_id}/revoke',
    ):
        assert path in router


def test_manifest_freezes_real_versions_and_package_rechecks_bytes():
    core = read("backend/app/modules/internship/services/internship_material_center_service.py")
    facade = read("backend/app/modules/internship/services/internship_material_center_facade.py")
    assert "version_id=int(item[\"versionId\"])" in facade
    assert "file_object_id=int(item[\"fileId\"])" in facade
    assert "manifestSha256" in core
    assert "version.file_object_id != file_row.id" in core
    assert "file_row.sha256 != item.sha256_snapshot" in core
    assert "digest != item.sha256_snapshot" in core
    assert "INTERNSHIP_ARCHIVE_PACKAGE_FILE_VERSION_V1" in core
    assert 'entries["manifest.json"]' in core


def test_existing_archive_freeze_and_revoke_are_preserved():
    archive = read("backend/app/modules/internship/services/internship_archive_service.py")
    core = read("backend/app/modules/internship/services/internship_material_center_service.py")
    router = read("backend/app/modules/internship/routers/internship_material_center.py")
    assert "material_snapshot" in archive
    assert "snapshot_version" in archive
    assert "revoke_archive" in archive
    assert 'snapshot["fileVersionManifest"]' in core
    assert "revoke_manifests" in router
    assert "archive_svc.revoke_archive" in router
