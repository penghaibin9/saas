"""Closeout architecture gates for the graduation material domain.

These tests intentionally reject the former phase-6 coexistence assumptions.
Behavioral MySQL coverage lives here and in the dedicated acceptance script.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import event, func, select, text


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_default_seed_has_exactly_eighteen_material_types_but_runtime_uses_rules():
    from app.modules.graduation.materials.definitions import DEFAULT_MATERIAL_DEFINITIONS

    assert len(DEFAULT_MATERIAL_DEFINITIONS) == 18
    assert len({row["materialCode"] for row in DEFAULT_MATERIAL_DEFINITIONS}) == 18
    command = read("backend/app/modules/graduation/materials/command_service.py")
    manifest = read("backend/app/modules/graduation/materials/manifest_service.py")
    assert "rule_item(" in command
    assert "active_rule(" in manifest and "rule_items(" in manifest
    assert "DEFAULT_SPEC_BY_CODE" not in command
    assert "DEFAULT_SPEC_BY_CODE" not in manifest


def test_query_service_is_write_free_and_get_routers_have_no_sql():
    query = read("backend/app/modules/graduation/materials/query_service.py")
    tree = ast.parse(query)
    banned_calls = {"add", "add_all", "delete", "flush", "commit", "rollback", "execute_update"}
    db_calls = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "db"
    }
    assert not db_calls.intersection(banned_calls)
    for path in (
        "backend/app/modules/graduation/routers/graduation_material_center.py",
        "backend/app/api/v1/mobile_graduation_material_center.py",
    ):
        source = read(path)
        assert "sqlalchemy" not in source
        assert "from app.models" not in source
        assert "services.db_service" not in source
        assert "db.commit" not in source


def test_legacy_services_are_only_thin_compatibility_facades():
    for name in (
        "graduation_material_catalog_service.py",
        "graduation_material_center_service.py",
        "graduation_material_delivery_service.py",
    ):
        source = read(f"backend/app/modules/graduation/services/{name}")
        assert "sqlalchemy" not in source
        assert "from app.models" not in source
        assert "services.db_service" not in source
        assert "db.commit" not in source
        for constructor in ("FileAsset(", "FileVersion(", "FileBinding(", "ArchiveManifest("):
            assert constructor not in source


def test_only_command_service_creates_graduation_assets_versions_and_bindings():
    materials = ROOT / "backend/app/modules/graduation/materials"
    constructors = {}
    for path in materials.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        constructors[path.name] = {token for token in ("FileAsset(", "FileVersion(", "FileBinding(") if token in source}
    assert constructors["command_service.py"] == {"FileAsset(", "FileVersion(", "FileBinding("}
    assert all(not tokens for name, tokens in constructors.items() if name != "command_service.py")


def test_only_manifest_service_creates_v2_manifest_evidence():
    materials = ROOT / "backend/app/modules/graduation/materials"
    writers = [path.name for path in materials.glob("*.py") if "ArchiveManifest(" in path.read_text(encoding="utf-8")]
    item_writers = [path.name for path in materials.glob("*.py") if "ArchiveManifestItem(" in path.read_text(encoding="utf-8")]
    assert writers == ["manifest_service.py"]
    assert item_writers == ["manifest_service.py"]
    source = read("backend/app/modules/graduation/materials/manifest_service.py")
    assert "重新归档前必须先撤销" in source
    assert 'version.status = "ARCHIVED"' in source
    revoke = source[source.index("def revoke_manifest"):source.index("def mark_packaged_in_session")]
    assert 'version.status = "APPROVED"' not in revoke


def test_single_snapshot_and_source_hash_metadata_contract():
    legacy = read("backend/app/modules/graduation/services/graduation_structured_snapshot_service.py")
    snapshot = read("backend/app/modules/graduation/materials/snapshot_service.py")
    command = read("backend/app/modules/graduation/materials/command_service.py")
    assert "reportlab" not in legacy
    assert "snapshot_service import prepare_all" in legacy
    for marker in ("sourceDataHash", "snapshotSchemaVersion", "generatorVersion"):
        assert marker in command
    assert "source_hash" in snapshot and 'registered["status"] == "UNCHANGED"' in snapshot


def test_access_tickets_are_short_lived_rechecked_and_single_use():
    source = read("backend/app/modules/graduation/materials/access_service.py")
    assert "PREVIEW_TTL_SECONDS = 180" in source
    assert "DOWNLOAD_TTL_SECONDS = 60" in source
    assert "cache_set_json_if_absent" in source
    assert "require_file_access" in source and "assert_student_access" in source
    assert "resolve_material(int(file_id), user" in source
    staff = read("backend/app/modules/graduation/routers/graduation_material_center.py")
    mobile = read("backend/app/api/v1/mobile_graduation_material_center.py")
    for router in (staff, mobile):
        assert "ticket: str = Query(...)" in router
        assert "consume_ticket" in router
        assert "consume_package_ticket" in router


def test_migration_is_explicit_resumable_and_never_guesses_by_sequence():
    source = read("backend/app/modules/graduation/materials/migration_service.py")
    for marker in ("dry_run", "page_size", "cursor_id", "retry", "begin_nested",
                   "output_format", "differenceReport", "mappingConfidence", "manualReview"):
        assert marker in source
    assert "ALREADY_BOUND" in read("backend/app/modules/graduation/materials/command_service.py")
    assert "禁止按附件序号猜测" in source
    assert "_01" not in source and "_02" not in source


def test_production_material_center_route_and_ui_contract():
    routes = read("frontend/src/modules/graduation/routes.js")
    workspace = read("frontend/src/modules/graduation/config/graduationWorkspaces.js")
    page = read("frontend/src/modules/graduation/views/GraduationMaterialCenterView.vue")
    assert "path: 'material-center'" in routes
    assert "path: 'materials', redirect" in routes
    assert "/admin/graduation/material-center" in workspace
    for label in ("全部材料", "学生完整性", "待审核", "安全异常"):
        assert label in page
    for field in ("指导教师", "阶段 / 材料", "文件", "版本", "上传人 / 时间", "大小", "扫描", "审核", "归档"):
        assert field in page
    assert "AppConfirmDialog" in page and "FileVersionTimeline" in page
    assert "window.prompt" not in page and "window.confirm" not in page
    assert "createExport" not in page and "freezeManifest" not in page and "templateCatalog" not in page
    assert "graduationDesign.material.manage" not in page
    assert "graduationDesign.riskArchive.manage" not in page


def test_four_client_optimistic_version_contract_is_explicit():
    sources = [
        read("frontend/src/modules/graduation/views/_shared/ProposalReviewCard.vue"),
        read("frontend/src/modules/graduation/views/FinalSubmissionListView.vue"),
        read("student-portal/src/views/graduation/GraduationWorkbenchView.vue"),
        read("miniapp/src/pages/student/graduation/index.vue"),
        read("miniapp/src/pages/teacher/graduation-guide/index.vue"),
        read("miniapp/src/services/teacherApi.js"),
    ]
    assert all("expectedVersion" in source for source in (sources[0], sources[1], sources[2], sources[3], sources[5]))
    assert "materialVersion" in sources[4] and "fileVersionId" in sources[4]
    assert "fileVersionId" in sources[0] and "fileVersionId" in sources[1] and "fileVersionId" in sources[5]
    schema = read("backend/app/modules/graduation/schemas/graduation.py")
    assert "expectedVersion: int = Field(..." in schema
    assert "fileVersionId: int = Field(..." in schema


def test_real_mysql_gets_are_zero_write_and_within_query_budget(db_mode):
    from app.core.context import get_tenant, set_current_user, set_tenant
    from app.db.session import get_engine
    from app.models import GraduationBatch
    from app.modules.graduation.materials import query_service
    from app.services.db_service import _tid, session

    set_tenant({"tenantId": "1000000000000000001", "tenantCode": "demo"})
    assert get_engine().dialect.name == "mysql"
    assert get_tenant()
    user = {"userId": "1", "realName": "测试管理员", "currentRoleCode": "SCHOOL_ADMIN",
            "userType": "ADMIN", "permissions": ["*"]}
    set_current_user(user)
    with session() as db:
        batch_id = db.scalar(select(GraduationBatch.id).where(
            GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False),
        ).order_by(GraduationBatch.id).limit(1))
    if not batch_id:
        pytest.skip("测试租户没有毕业设计批次")
    tables = ("t_gd_material_rule", "t_gd_material_item", "t_gd_student_material", "t_file_asset",
              "t_file_version", "t_file_binding", "t_archive_manifest", "t_archive_manifest_item", "t_export_job")

    def fingerprint():
        with session() as db:
            return {name: tuple(db.execute(text(
                f"SELECT COUNT(*), COALESCE(MAX(version),0), COALESCE(MAX(updated_at),'1970-01-01') "
                f"FROM {name} WHERE tenant_id=:tenant"
            ), {"tenant": _tid()}).one()) for name in tables}

    statements = []
    engine = get_engine()

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    before = fingerprint()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        budgets = []
        for call, budget in (
            (lambda: query_service.files(user, batch_id=int(batch_id), page=1, page_size=20), 6),
            (lambda: query_service.students(user, batch_id=int(batch_id), page=1, page_size=20), 6),
            (lambda: query_service.summary(user, batch_id=int(batch_id)), 4),
        ):
            statements.clear(); call(); budgets.append((len(statements), budget))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert fingerprint() == before
    assert all(actual <= budget for actual, budget in budgets)
