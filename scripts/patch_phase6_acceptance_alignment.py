from __future__ import annotations

import subprocess
from pathlib import Path

BRANCH = "audit/file-capability-inventory"
ROOT = Path(__file__).resolve().parents[1]
subprocess.run(["git", "fetch", "origin", BRANCH], check=True)
subprocess.run(["git", "checkout", "-B", "stage6-acceptance-align", f"origin/{BRANCH}"], check=True)


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


acceptance = "backend/tests/graduation_material_center_mysql_acceptance.py"
contract = "backend/tests/test_graduation_material_center_phase6.py"
export_service = "backend/app/modules/graduation/services/graduation_material_export_service.py"

replace(
    acceptance,
    "from app.core.context import set_current_tenant, set_current_user\n",
    "from app.core.context import set_current_user, set_tenant\n",
)
replace(
    acceptance,
    "from app.services.storage import get_backend\n",
    "from app.services.data_exchange_job_service import create_download_ticket, consume_download_ticket\nfrom app.services.storage import get_backend\n",
)
replace(
    acceptance,
    "    set_current_tenant(TENANT_ID)\n",
    '    set_tenant({"tenantId": str(TENANT_ID)})\n',
)
replace(
    acceptance,
    '            title="阶段六公共文件中心毕业设计",\n',
    '            title="=1+1 阶段六公共文件中心毕业设计",\n',
)
replace(
    acceptance,
    '''    design = catalog.submit_material(student_id, "DESIGN_WORK", clean_design_id, 0, student_user)
    source = catalog.submit_material(student_id, "SOURCE_CODE", clean_source_id, 0, student_user)
    assert design["version"] == 1 and source["version"] == 1
    set_current_user(teacher_user)
''',
    '''    design = catalog.submit_material(student_id, "DESIGN_WORK", clean_design_id, 0, student_user)
    source = catalog.submit_material(student_id, "SOURCE_CODE", clean_source_id, 0, student_user)
    assert design["version"] == 1 and source["version"] == 1
    # 总览必须从当前 FileVersion/FileObject 实时计算扫描异常，而不是固定返回 0。
    db = get_sessionmaker()()
    try:
        design_version = db.get(FileVersion, int(design["fileVersionId"]))
        design_file = db.get(FileObject, int(design_version.file_object_id))
        design_file.status = "QUARANTINED"
        design_file.scan_status = "PENDING"
        design_file.storage_zone = "QUARANTINE"
        db.commit()
    finally:
        db.close()
    set_current_user(admin_user)
    abnormal_overview = catalog.material_overview(admin_user, batch_id=batch_id, page=1, page_size=20)
    assert abnormal_overview["summary"]["scanAbnormalStudents"] >= 1
    db = get_sessionmaker()()
    try:
        design_version = db.get(FileVersion, int(design["fileVersionId"]))
        design_file = db.get(FileObject, int(design_version.file_object_id))
        design_file.status = "AVAILABLE"
        design_file.scan_status = "CLEAN"
        design_file.storage_zone = "ACTIVE"
        db.commit()
    finally:
        db.close()
    set_current_user(teacher_user)
''',
)
replace(
    acceptance,
    '''    set_current_user(admin_user)
    backfill_1 = catalog.backfill_legacy_attachments(
        admin_user,
        batch_id=batch_id,
        page_size=1,
        dry_run=False,
        checkpoint_key="phase6-backfill",
    )
    backfill_2 = catalog.backfill_legacy_attachments(
        admin_user,
        batch_id=batch_id,
        page_size=20,
        dry_run=False,
        checkpoint_key="phase6-backfill",
    )
    assert backfill_1["processed"] <= 1
    assert backfill_2["checkpoint"]["status"] in {"COMPLETED", "PARTIAL_FAILED"}
    repeat = catalog.backfill_legacy_attachments(
        admin_user,
        batch_id=batch_id,
        page_size=20,
        dry_run=False,
        checkpoint_key="phase6-backfill-repeat",
    )
    assert repeat["createdBindings"] >= 0
''',
    '''    set_current_user(admin_user)
    dry_run = catalog.backfill_legacy(
        admin_user, page_size=20, cursor_model="PROPOSAL", cursor_id=0, dry_run=True,
    )
    assert dry_run["dryRun"] is True and dry_run["converted"] >= 1
    backfill_1 = catalog.backfill_legacy(
        admin_user, page_size=1, cursor_model="PROPOSAL", cursor_id=0, dry_run=False,
    )
    backfill_2 = catalog.backfill_legacy(
        admin_user, page_size=20, cursor_model="PROPOSAL",
        cursor_id=int(backfill_1["nextCursorId"] or 0), dry_run=False,
    )
    assert backfill_1["scanned"] <= 1
    assert backfill_2["status"] in {"COMPLETED", "PARTIAL_FAILED", "RUNNING"}
    repeat = catalog.backfill_legacy(
        admin_user, page_size=20, cursor_model="PROPOSAL", cursor_id=0, dry_run=False,
    )
    assert any(item["status"] in {"SKIPPED", "CONVERTED"} for item in repeat["differences"])
''',
)
replace(
    acceptance,
    '''    policy_v1 = catalog.publish_template_version(
        template_id,
        template_file_v1_id,
        admin_user,
        batch_id=batch_id,
        template_code="GD_PROPOSAL_REPORT",
        variable_schema={"variables": [{"name": "studentName", "type": "string"}]},
    )
    policy_v2 = catalog.publish_template_version(
        template_id,
        template_file_v2_id,
        admin_user,
        batch_id=batch_id,
        template_code="GD_PROPOSAL_REPORT",
        variable_schema={"variables": [{"name": "studentName", "type": "string"}]},
    )
''',
    '''    policy_payload = {
        "batchId": batch_id,
        "templateCode": "GD_PROPOSAL_REPORT",
        "variableSchema": {"variables": [{"name": "studentName", "type": "string"}]},
    }
    policy_v1 = catalog.publish_template_policy(template_id, template_file_v1_id, policy_payload, admin_user)
    policy_v2 = catalog.publish_template_policy(template_id, template_file_v2_id, policy_payload, admin_user)
''',
)
replace(
    acceptance,
    '        assert int(policy.current_version_id) == int(policy_v2["fileVersionId"])\n',
    '        assert int(policy.current_version_id) == int(policy_v2["versionId"])\n        policy_id = int(policy.id)\n        policy_expected_version = int(policy.version or 0)\n',
)
replace(
    acceptance,
    '''    finally:
        db.close()

    set_current_user(admin_user)
    structured_snapshots.prepare_all(student_id, admin_user)
''',
    '''    finally:
        db.close()
    enabled_policy = catalog.update_template_policy_status(
        policy_id, True, policy_expected_version, admin_user,
    )
    assert enabled_policy["enabled"] is True and enabled_policy["status"] == "ENABLED"

    set_current_user(admin_user)
    structured_snapshots.prepare_all(student_id, admin_user)
''',
)
replace(
    acceptance,
    '''    export_job = export_service.create_export_job(
        teacher_user,
        scope_type="STUDENT",
        scope_id=student_id,
        export_format="ZIP_XLSX",
        batch_id=batch_id,
    )
    completed = export_service.run_export_job(int(export_job["jobId"]), teacher_user)
''',
    '''    export_job = export_service.create_export_job(
        batch_id=batch_id, scope_type="STUDENT", scope_value=str(student_id), user=teacher_user,
    )
    export_job_id = int(export_job["id"])
    completed = export_service.run_export_job(export_job_id, teacher_user)
''',
)
replace(
    acceptance,
    '''    assert completed["result"]["fileCount"] == manifest_v1["itemCount"]
    zip_file_id = int(completed["result"]["zipFileId"])
    xlsx_file_id = int(completed["result"]["xlsxFileId"])
''',
    '''    assert completed["result"]["materialFileCount"] == manifest_v1["itemCount"]
    zip_file_id = int(completed["result"]["zipFileObjectId"])
    xlsx_file_id = int(completed["result"]["xlsxFileObjectId"])
''',
)
replace(
    acceptance,
    '    assert zip_manifest["fileCount"] == manifest_v1["itemCount"]\n',
    '    assert zip_manifest["materialFileCount"] == manifest_v1["itemCount"]\n',
)
replace(
    acceptance,
    '''    _, xlsx_bytes = _read_file(xlsx_file_id)
    workbook = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
''',
    '''    xlsx_row, xlsx_bytes = _read_file(xlsx_file_id)
    assert hashlib.sha256(xlsx_bytes).hexdigest() == completed["result"]["xlsxSha256"]
    assert xlsx_row.sha256 == completed["result"]["xlsxSha256"]
    workbook = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
''',
)
replace(
    acceptance,
    '    assert any("\'=\" in str(value) or "阶段六" in str(value) for row in rows[1:] for value in row)\n',
    '    assert any(str(value).startswith("\'=") for row in rows[1:] for value in row)\n',
)
replace(
    acceptance,
    '        job_row = db.get(ExportJob, int(export_job["jobId"]))\n',
    '        job_row = db.get(ExportJob, export_job_id)\n',
)
replace(
    acceptance,
    '''    ticket = tickets.issue_export_ticket(int(export_job["jobId"]), teacher_user)
    resolved = tickets.consume_export_ticket(ticket["ticket"], teacher_user)
    assert int(resolved["fileId"]) == zip_file_id
    revoked = export_service.revoke_manifest(int(manifest_v1["manifestId"]), "阶段六撤销重归档验收", teacher_user)
    assert revoked["status"] == "REVOKED"
    _expect_not_found(lambda: tickets.consume_export_ticket(ticket["ticket"], teacher_user))
''',
    '''    ticket = create_download_ticket(
        str(export_job_id), expected_version=int(completed["version"]), user=teacher_user,
    )
    downloaded_path, downloaded_name = consume_download_ticket(
        str(export_job_id), ticket["ticket"], user=teacher_user,
    )
    assert downloaded_path.exists() and downloaded_name.endswith(".zip")
    current_job = export_service.get_export_job(export_job_id, teacher_user)
    revoke_ticket = create_download_ticket(
        str(export_job_id), expected_version=int(current_job["version"]), user=teacher_user,
    )
    revoked = export_service.revoke_manifest(student_id, "阶段六撤销重归档验收", teacher_user)
    assert revoked["status"] == "REVOKED"
    _expect_not_found(lambda: consume_download_ticket(
        str(export_job_id), revoke_ticket["ticket"], user=teacher_user,
    ))
''',
)
replace(
    acceptance,
    '        assert db.get(ExportJob, int(export_job["jobId"])).status == "REVOKED"\n',
    '        assert db.get(ExportJob, export_job_id).status == "REVOKED"\n',
)
replace(
    acceptance,
    '        "exportJob": export_job["jobId"],\n',
    '        "exportJob": str(export_job_id),\n',
)

replace(
    export_service,
    'EXPORT_TTL_HOURS = 24\n',
    '''EXPORT_TTL_HOURS = 24
XLSX_HEADERS = [
    "批次", "学院", "专业", "班级", "学号", "姓名", "指导教师", "题目",
    "材料代码", "材料名称", "文件名", "文件版本", "文件大小", "SHA-256",
    "扫描状态", "审核状态", "上传时间", "归档 revision",
]
''',
)
replace(
    export_service,
    '''    headers = ["批次", "学院", "专业", "班级", "学号", "姓名", "指导教师", "题目",
               "材料代码", "材料名称", "文件名", "文件版本", "文件大小", "SHA-256",
               "扫描状态", "审核状态", "上传时间", "归档 revision"]
    sheet.append(headers)
''',
    '    sheet.append(XLSX_HEADERS)\n',
)

replace(
    contract,
    '''        "len(rule_codes) == 18", "scanAbnormalStudents", "v1.status == \"INVALIDATED\"",
        "ExportJob", "manifest.json", "档案清单.xlsx", "materialFileCount",
        "result[\"zipSha256\"]", "result[\"xlsxSha256\"]", "startswith(\"'=\")",
        "revoke_manifest", "create_download_ticket", "second_manifest", "template_v2",
        "cross_tenant_file_id", "infected_file_id", "pending_file_id", "dry_run=True",
''',
    '''        "assert rule[\"itemCount\"] == 18", "scanAbnormalStudents", "row.status == \"INVALIDATED\"",
        "ExportJob", "manifest.json", "档案清单.xlsx", "materialFileCount",
        "completed[\"result\"][\"zipSha256\"]", "completed[\"result\"][\"xlsxSha256\"]", "startswith(\"'=\")",
        "revoke_manifest", "create_download_ticket", "manifest_v2", "policy_v2",
        "cross_tenant_file_id", "infected_file_id", "pending_file_id", "dry_run=True",
''',
)

print("Stage 6 acceptance aligned with production services")
