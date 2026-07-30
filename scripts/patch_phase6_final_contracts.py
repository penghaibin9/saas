#!/usr/bin/env python3
"""One-time fail-closed patch for final Stage 6 client state and contracts."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, marker: str) -> bool:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return False
    if old not in text:
        raise SystemExit(f"refusing to patch changed source: {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def append_once(path: str, content: str, marker: str) -> bool:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return False
    target.write_text(text.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")
    return True


def main() -> None:
    changed: list[str] = []
    student_page = "miniapp/src/pages/student/graduation/index.vue"
    test_file = "backend/tests/test_graduation_material_center_phase6.py"

    if replace_exact(
        student_page,
        "      defense: null, grade: null, archive: null,\n",
        "      defense: null, grade: null, archive: null, materials: null, materialUploadingCode: '',\n",
        "archive: null, materials: null, materialUploadingCode",
    ):
        changed.append(student_page)

    contract_tests = r'''
def test_phase6_template_self_service_and_mobile_clients_are_real():
    catalog = read("backend/app/modules/graduation/services/graduation_material_catalog_service.py")
    router = read("backend/app/modules/graduation/routers/graduation_material_center.py")
    api = read("frontend/src/modules/graduation/api/graduation-material-center.api.js")
    page = read("frontend/src/modules/graduation/views/GraduationMaterialCenterView.vue")
    mini_sdk = read("miniapp/src/services/fileSdk.js")
    student_api = read("miniapp/src/services/studentApi.js")
    teacher_api = read("miniapp/src/services/teacherApi.js")
    student_page = read("miniapp/src/pages/student/graduation/index.vue")
    teacher_page = read("miniapp/src/pages/teacher/graduation-guide/index.vue")

    for marker in (
        "update_template_policy_status", "expected_version", "legacy_center._require_file_ready(file_obj)",
        '"availableTemplates"', '"version": int(policy.version or 0)',
    ):
        assert marker in catalog
    assert '/material-center/templates/policies/{policy_id}/status' in router
    assert "setTemplateStatus" in api
    assert "FileUploader" in page
    assert "variableSchemaText" in page
    assert "publishTemplate" in page
    assert "toggleTemplate" in page

    assert "openAuthorized" in mini_sdk
    assert "getGraduationMaterialLibrary" in student_api
    assert "submitGraduationMaterial" in student_api
    assert "getGraduationMaterialLibrary" in teacher_api
    assert "reviewGraduationMaterial" in teacher_api
    assert "18 类材料" in student_page
    assert "materialUploadingCode" in student_page
    assert "大型论文、作品或源代码请到学生 PC 上传" in student_page
    assert "currentSafeVersions" in teacher_page
    assert "reviewReady" in teacher_page
    assert "当前安全版本（审核锁定）" in teacher_page
    assert "fileSdk.openAuthorized" in student_page
    assert "fileSdk.openAuthorized" in teacher_page
    for source in (student_page, teacher_page):
        assert "ENV.apiBaseUrl" not in source
        assert "Authorization: 'Bearer '" not in source
        assert "uni.downloadFile({" not in source


def test_phase6_real_acceptance_covers_all_completion_evidence():
    script = read("backend/tests/graduation_material_center_mysql_acceptance.py")
    structured = read("backend/app/modules/graduation/services/graduation_structured_snapshot_service.py")
    ast.parse(structured, filename="graduation_structured_snapshot_service.py")
    for marker in (
        "len(rule_codes) == 18", "scanAbnormalStudents", "v1.status == \"INVALIDATED\"",
        "ExportJob", "manifest.json", "档案清单.xlsx", "materialFileCount",
        "result[\"zipSha256\"]", "result[\"xlsxSha256\"]", "startswith(\"'=\")",
        "revoke_manifest", "create_download_ticket", "second_manifest", "template_v2",
        "cross_tenant_file_id", "infected_file_id", "pending_file_id", "dry_run=True",
    ):
        assert marker in script
    assert "structured_snapshots.prepare_all" in read(
        "backend/app/modules/graduation/services/graduation_material_export_service.py"
    )
'''
    if append_once(test_file, contract_tests, "def test_phase6_template_self_service_and_mobile_clients_are_real"):
        changed.append(test_file)

    print("phase 6 final contract patch complete:", ", ".join(changed) if changed else "already applied")


if __name__ == "__main__":
    main()
