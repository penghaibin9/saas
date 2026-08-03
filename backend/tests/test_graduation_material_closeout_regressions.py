from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _student() -> dict:
    return {
        "userId": "9001",
        "tenantId": "1000000000000000001",
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
        "studentNo": "S9001",
        "permissions": ["*"],
        "modules": ["graduation"],
        "moduleCodes": ["graduation"],
    }


def _admin() -> dict:
    return {
        "userId": "1",
        "tenantId": "1000000000000000001",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "permissions": ["*"],
    }


def test_student_mobile_review_is_real_403_and_handler_never_runs(monkeypatch):
    from app.api.v1 import mobile_graduation_material_center as mobile
    from app.core.security import get_current_user
    from app.main import app as production_app

    called = {"value": False}

    def forbidden_handler(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("student request reached material review command")

    monkeypatch.setattr(mobile.commands, "review_material", forbidden_handler)
    production_app.dependency_overrides[get_current_user] = _student
    try:
        with TestClient(production_app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/mobile/graduation/material-center/materials/1/review",
                json={"action": "APPROVE", "fileVersionId": 2, "expectedVersion": 3},
            )
    finally:
        production_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    assert called["value"] is False


def test_sensitive_detail_routes_return_secure_version_contract(monkeypatch):
    from app.core.security import get_current_user
    from app.modules.graduation.routers import graduation_material_sensitive_router as sensitive

    contract = {
        "currentSafeVersions": [{"versionId": "22"}],
        "reviewReady": True,
        "migrationRequired": False,
        "materialVersion": 3,
        "fileVersionId": "22",
    }
    monkeypatch.setattr(sensitive, "_record_student", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sensitive.material_queries, "proposal_detail", lambda *_args, **_kwargs: dict(contract))
    monkeypatch.setattr(sensitive.material_queries, "final_detail", lambda *_args, **_kwargs: dict(contract))
    app = FastAPI()
    app.include_router(sensitive.router)
    app.dependency_overrides[get_current_user] = _admin
    with TestClient(app) as client:
        for path in ("/graduation/proposals/7?batchId=1", "/graduation/finals/8?batchId=1"):
            payload = client.get(path).json()["data"]
            assert set(contract).issubset(payload)
            assert payload["reviewReady"] is True


def test_review_permission_map_is_exact_and_students_fail_closed(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.graduation.materials import command_service as command

    assert command.review_permission_code("PROPOSAL_REPORT") == "graduationDesign.proposal.review"
    assert command.review_permission_code("THESIS_FINAL") == "graduationDesign.final.review"
    assert command.review_permission_code("REVIEW_ATTACHMENT") == "graduationDesign.review.submit"
    assert command.review_permission_code("DEFENSE_SIGNED_SHEET") == "graduationDesign.defense.scoreConfirm"
    monkeypatch.setattr(command, "enforce_permission", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("student must be rejected before permission execution")
    ))
    try:
        command._enforce_review_permission(_student(), "PROPOSAL_REPORT")
    except AppException as exc:
        assert exc.http_status == 403
    else:
        raise AssertionError("student review permission was not rejected")


def test_single_main_document_contract_on_student_surfaces():
    portal = source("student-portal/src/views/graduation/GraduationWorkbenchView.vue")
    mini = source("miniapp/src/pages/student/graduation/index.vue")
    record = source("backend/app/modules/graduation/materials/record_service.py")
    assert "最多 10 个附件" not in portal
    assert 'type="file" accept=".pdf,.doc,.docx,.zip" multiple' not in portal
    assert "attachments[kind].splice(0, attachments[kind].length, uploaded)" in portal
    assert "this[arr].splice(0, this[arr].length" in mini
    assert "兼容提交一次仅接收一个主文档" in record


def test_generated_snapshots_never_replace_human_current_versions():
    command = source("backend/app/modules/graduation/materials/command_service.py")
    snapshot = source("backend/app/modules/graduation/materials/snapshot_service.py")
    assert 'current_version.source_channel or "").upper() != "SYSTEM_GENERATED"' in command
    assert '"status": "PRESERVED_UPLOAD"' in command
    assert '"preservedUploads": []' in snapshot
    assert 'current["sourceChannel"] != "SYSTEM_GENERATED"' in snapshot


def test_rule_switch_is_two_step_and_catalog_migrates_before_enable():
    rule = source("backend/app/modules/graduation/materials/rule_service.py")
    router = source("backend/app/modules/graduation/routers/graduation_material_center.py")
    assert "MATERIAL_RULE_REPAIR_REQUIRED" in rule
    assert "confirm_catalog_repair" in rule
    assert "_migrate_catalog_to_candidate" in rule
    assert "MATERIAL_RULE_REMOVAL_CONFLICT" in rule
    assert "/material-center/rules/{rule_id}/impact" in router
    assert "confirmCatalogRepair" in router


def test_archive_summary_ignores_non_archive_materials():
    query = source("backend/app/modules/graduation/materials/query_service.py")
    for status in ('review_status == "PENDING"', 'review_status == "RETURNED"', "scan_abnormal_count"):
        section = query[query.index("def _student_aggregate"):query.index("def _summary")]
        assert "archive_required.is_(True)" in section
        assert status in section


def test_export_uses_each_manifest_frozen_rule_revision():
    export = source("backend/app/modules/graduation/materials/export_service.py")
    assert "def _frozen_rule_names" in export
    assert 'manifest.rule_version' in export
    assert "names_by_manifest[int(manifest.id)]" in export
    assert "active_rule(" not in export


def test_atomic_permissions_replace_material_manager_or_gate():
    router = source("backend/app/modules/graduation/routers/graduation_material_center.py")
    permissions = source("backend/app/core/graduation_permissions.py")
    assert "_require_material_manager" not in router
    assert "_require_material_reviewer" not in router
    assert 'require_permission("graduationDesign.archive.export")' in router
    assert 'require_permission("graduationDesign.template.manage")' in router
    assert "GRADUATION_DYNAMIC_PERMISSION_ENDPOINTS" in permissions


def test_version_writers_revalidate_locked_security_facts():
    command = source("backend/app/modules/graduation/materials/command_service.py")
    assert "def _assert_locked_file_ready" in command
    assert "is_downloadable_status(file_obj.status)" in command
    assert "scan not in READY_SCAN_STATES" in command
    assert "FILE_HASH_MISSING" in command
    append_calls = command.count("_append_version(") - 1  # exclude the function definition
    locked_checks = command.count("_assert_locked_file_ready(item, file_obj, user)")
    assert append_calls >= 3
    assert locked_checks == append_calls
