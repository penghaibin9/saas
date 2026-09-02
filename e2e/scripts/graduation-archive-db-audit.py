import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pymysql

PRODUCT_EXACT_HEAD = "47264037bf014276e795d3655d7f178830756729"
REQUIRED_CODES = {
    "TASKBOOK", "PROPOSAL_REPORT", "GUIDANCE_RECORD", "MIDTERM_REPORT",
    "THESIS_FINAL", "PLAGIARISM_REPORT", "REVIEW_ATTACHMENT", "DEFENSE_RECORD", "GRADE_MATERIAL",
}


def cv(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root", password="e2e_root",
    database="student_lifecycle_e2e", charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
with conn.cursor() as cur:
    cur.execute(
        "SELECT a.*, s.student_no, s.name AS student_name, s.stage AS student_stage, s.batch_id "
        "FROM t_gd_archive_record a JOIN t_gd_student s ON s.id=a.gd_student_id AND s.tenant_id=a.tenant_id "
        "WHERE a.status='FILED' ORDER BY a.id DESC LIMIT 1"
    )
    archive = cur.fetchone()
    assert archive, "GD-018 Browser First did not persist a FILED archive record"

    cur.execute(
        "SELECT * FROM t_archive_manifest WHERE tenant_id=%s AND module_code='GRADUATION' "
        "AND archive_type='GRADUATION_FILE_VERSION' AND target_type='GRADUATION_STUDENT' AND target_id=%s "
        "AND status IN ('FROZEN','PACKAGED') ORDER BY revision DESC,id DESC LIMIT 1",
        (archive["tenant_id"], str(archive["gd_student_id"])),
    )
    manifest = cur.fetchone()
    assert manifest, archive

    cur.execute(
        "SELECT i.*, v.status AS version_status, v.is_current, v.file_object_id AS version_file_object_id, "
        "o.sha256 AS object_sha256, o.size_bytes AS object_size_bytes, o.status AS object_status, o.scan_status "
        "FROM t_archive_manifest_item i "
        "JOIN t_file_version v ON v.id=i.version_id AND v.tenant_id=i.tenant_id "
        "JOIN t_file_object o ON o.id=i.file_object_id AND o.tenant_id=i.tenant_id "
        "WHERE i.tenant_id=%s AND i.manifest_id=%s ORDER BY i.sort_no,i.id",
        (archive["tenant_id"], manifest["id"]),
    )
    items = list(cur.fetchall())

    cur.execute(
        "SELECT material_code,current_version_id,business_status,review_status,archive_status,archived_revision "
        "FROM t_gd_student_material WHERE tenant_id=%s AND gd_student_id=%s AND is_deleted=0 ORDER BY material_code",
        (archive["tenant_id"], archive["gd_student_id"]),
    )
    materials = list(cur.fetchall())

    cur.execute(
        "SELECT id,action,operator,role_name,detail,occurred_at,request_id,request_path,role_code,permission_code "
        "FROM t_gd_audit_trail WHERE tenant_id=%s AND biz_id=%s ORDER BY id",
        (archive["tenant_id"], str(archive["id"])),
    )
    audits = list(cur.fetchall())
conn.close()

for row in [archive, manifest, *items, *materials, *audits]:
    for key, value in list(row.items()):
        row[key] = cv(value)

evidence = {
    "productExactHead": PRODUCT_EXACT_HEAD,
    "archive": archive,
    "manifest": manifest,
    "manifestItems": items,
    "materials": materials,
    "audits": audits,
}
out = Path("test-results/graduation-archive-db-audit.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(evidence, ensure_ascii=False, indent=2))

assert archive["status"] == "FILED", archive
assert archive["student_stage"] == "ARCHIVED", archive
assert archive.get("archive_batch_no"), archive
assert archive.get("manifest_hash") and len(str(archive["manifest_hash"])) == 64, archive
assert manifest["status"] in {"FROZEN", "PACKAGED"}, manifest
assert int(manifest["revision"]) >= 1, manifest
assert manifest.get("frozen_at"), manifest
assert manifest.get("manifest_sha256") == archive.get("manifest_hash"), (archive, manifest)

codes = {row["material_code"] for row in items}
assert REQUIRED_CODES.issubset(codes), (REQUIRED_CODES - codes, codes)
assert len(items) >= len(REQUIRED_CODES), items
for row in items:
    assert row["version_id"] and row["file_object_id"], row
    assert str(row["version_file_object_id"]) == str(row["file_object_id"]), row
    assert row["sha256_snapshot"] and len(str(row["sha256_snapshot"])) == 64, row
    assert row["sha256_snapshot"] == row["object_sha256"], row
    assert int(row.get("size_snapshot") or 0) == int(row.get("object_size_bytes") or 0), row
    assert row["version_status"] == "ARCHIVED", row
    assert str(row.get("object_status") or "").upper() in {"AVAILABLE", "ARCHIVED"}, row
    assert str(row.get("scan_result") or "").upper() in {"CLEAN", "PASSED", "NOT_REQUIRED"}, row

material_by_code = {row["material_code"]: row for row in materials}
for code in REQUIRED_CODES:
    row = material_by_code.get(code)
    assert row, (code, materials)
    assert str(row.get("archive_status") or "").upper() in {"FROZEN", "ARCHIVED"}, row
    frozen = next(item for item in items if item["material_code"] == code)
    assert str(row.get("current_version_id") or "") == str(frozen["version_id"]), (row, frozen)

assert audits, archive
filing_audits = [row for row in audits if row.get("action") == "核验归档"]
assert filing_audits, {"message": "missing canonical V2 filing audit", "audits": audits}
for row in filing_audits:
    assert row.get("operator") and row.get("role_name") and row.get("occurred_at"), row
    assert row.get("request_id") and row.get("request_path") and row.get("role_code"), row
    assert "archiveBatchNo=" in str(row.get("detail") or ""), row
    assert "manifest=" in str(row.get("detail") or ""), row
