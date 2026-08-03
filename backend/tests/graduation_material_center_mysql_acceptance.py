"""Standalone real-MySQL acceptance for the consolidated material domain."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
import zipfile
from datetime import datetime

from sqlalchemy import delete, func, select, text

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_engine
from app.models import GraduationArchiveRecord, GraduationBatch, GraduationStudent
from app.models.data_exchange import ExportJob
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion
from app.models.graduation_material import GraduationMaterialItem, GraduationMaterialRule, GraduationStudentMaterial
from app.modules.graduation.materials import access_service, command_service, export_service, manifest_service, query_service
from app.modules.graduation.materials.snapshot_service import render_fields_pdf
from app.services import file_service
from app.services.db_service import session
from app.services.storage import get_backend


def _tenant_id() -> int:
    configured = os.getenv("GRADUATION_ACCEPTANCE_TENANT_ID")
    if str(configured or "").isdigit():
        return int(configured)
    with get_engine().connect() as conn:
        value = conn.execute(text(
            "SELECT tenant_id FROM t_gd_material_rule WHERE is_deleted=0 ORDER BY tenant_id DESC LIMIT 1"
        )).scalar()
    if not value:
        raise AssertionError("真实 MySQL 中没有可用于毕业设计验收的租户")
    return int(value)


def _make_file(label: str, user: dict, marker: str) -> dict:
    payload = render_fields_pdf("毕业设计材料域验收", [("版本", label), ("验收标识", marker)])
    return file_service.store_bytes(
        payload, f"acceptance-{marker}-{label}.pdf", "GRADUATION_MATERIAL_UPLOAD",
        "application/pdf", biz_id=marker, user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE",
    )


def _cleanup(ids: dict, file_keys: list[str]) -> None:
    backend = get_backend()
    with session() as db:
        manifest_ids = set(ids.get("manifest_ids", []))
        file_ids = set(ids.get("file_ids", []))
        asset_ids = set(ids.get("asset_ids", []))
        job_ids = set(ids.get("job_ids", []))
        if manifest_ids:
            db.execute(delete(ArchiveManifestItem).where(ArchiveManifestItem.id > 0, ArchiveManifestItem.manifest_id.in_(manifest_ids)))
        if job_ids:
            db.execute(delete(ExportJob).where(ExportJob.id.in_(job_ids)))
        if manifest_ids:
            db.execute(delete(ArchiveManifest).where(ArchiveManifest.id.in_(manifest_ids)))
        if ids.get("student_id"):
            db.execute(delete(GraduationArchiveRecord).where(GraduationArchiveRecord.gd_student_id == ids["student_id"]))
            db.execute(delete(GraduationStudentMaterial).where(GraduationStudentMaterial.gd_student_id == ids["student_id"]))
        if asset_ids:
            db.execute(delete(FileBinding).where(FileBinding.asset_id.in_(asset_ids)))
            db.execute(delete(FileVersion).where(FileVersion.asset_id.in_(asset_ids)))
            db.execute(delete(FileAsset).where(FileAsset.id.in_(asset_ids)))
        if file_ids:
            db.execute(delete(FileBinding).where(FileBinding.file_id.in_(file_ids)))
            db.execute(delete(FileObject).where(FileObject.id.in_(file_ids)))
        if ids.get("student_id"):
            db.execute(delete(GraduationStudent).where(GraduationStudent.id == ids["student_id"]))
        if ids.get("rule_id"):
            db.execute(delete(GraduationMaterialItem).where(GraduationMaterialItem.rule_id == ids["rule_id"]))
            db.execute(delete(GraduationMaterialRule).where(GraduationMaterialRule.id == ids["rule_id"]))
        if ids.get("batch_id"):
            db.execute(delete(GraduationBatch).where(GraduationBatch.id == ids["batch_id"]))
        db.commit()
    for key in set(file_keys):
        try:
            backend.delete(key)
        except Exception:
            pass


def main() -> None:
    engine = get_engine()
    assert engine.dialect.name == "mysql", "验收禁止 SQLite 替代"
    tenant_id = _tenant_id()
    marker = uuid.uuid4().hex[:10]
    user = {"userId": "1", "realName": "材料域验收管理员", "currentRoleCode": "SCHOOL_ADMIN",
            "userType": "ADMIN", "permissions": ["*"]}
    set_tenant({"tenantId": str(tenant_id)})
    set_current_user(user)
    ids: dict = {"file_ids": [], "file_keys": [], "asset_ids": [], "manifest_ids": [], "job_ids": []}
    try:
        with session() as db:
            batch = GraduationBatch(
                tenant_id=tenant_id, batch_name=f"材料域验收-{marker}", batch_no=f"MAT-{marker}",
                academic_year="2026-2027", grade_year="2027届", status="RUNNING", planned_count=1,
            )
            db.add(batch); db.flush(); ids["batch_id"] = int(batch.id)
            rule = GraduationMaterialRule(
                tenant_id=tenant_id, batch_id=int(batch.id), rule_code=f"ACCEPT_{marker}",
                rule_name="材料域真实 MySQL 验收规则", rule_version=1, status="ENABLED", enabled=True,
                default_owner_role="ADMIN", effective_at=datetime.utcnow(),
            )
            db.add(rule); db.flush(); ids["rule_id"] = int(rule.id)
            db.add(GraduationMaterialItem(
                tenant_id=tenant_id, rule_id=int(rule.id), biz_stage="FINAL_APPROVED",
                material_code="THESIS_FINAL", material_name="论文定稿", owner_role="ADMIN", required=True,
                allowed_ext_json=["pdf"], max_files=1, max_size_bytes=10 * 1024 * 1024,
                review_required=True, archive_required=True, sensitivity_level="SENSITIVE", sort_no=1, enabled=True,
            ))
            student = GraduationStudent(
                tenant_id=tenant_id, batch_id=int(batch.id), student_no=f"A{marker}",
                name="材料域验收学生", class_id="ACC", class_name="验收班",
                college_id="ACC", major_id="ACC", advisor_name="验收导师", topic_title="材料域生产级收口",
                stage="FINAL_CHECK", record_status="ACTIVE",
            )
            db.add(student); db.flush(); ids["student_id"] = int(student.id)
            db.add(GraduationArchiveRecord(
                tenant_id=tenant_id, gd_student_id=int(student.id), checklist_json=[], missing_items=[],
                status="SUBMITTED", generated_at=datetime.utcnow(), submitted_at=datetime.utcnow(),
            ))
            db.commit()

        command_service.initialize_student_materials(ids["student_id"], user)
        first_file = _make_file("v1", user, marker)
        ids["file_ids"].append(int(first_file["fileId"])); ids["file_keys"].append(first_file["fileKey"])
        submitted = command_service.submit_material(
            user, "THESIS_FINAL", int(first_file["fileId"]),
            gd_student_id=ids["student_id"], expected_version=0,
        )
        reviewed = command_service.review_material(
            int(submitted["materialId"]), int(submitted["fileVersionId"]), "APPROVE", "真实验收通过", user,
            expected_version=int(submitted["version"]),
        )
        assert reviewed["reviewStatus"] == "APPROVED"
        first = manifest_service.file_archive(ids["student_id"], f"ACC-{marker}", user)
        repeat = manifest_service.file_archive(ids["student_id"], f"ACC-{marker}", user)
        assert first["manifestId"] == repeat["manifestId"] and first["revision"] == 1
        ids["manifest_ids"].append(int(first["manifestId"]))
        with session() as db:
            assert int(db.scalar(select(func.count()).select_from(ArchiveManifest).where(
                ArchiveManifest.tenant_id == tenant_id, ArchiveManifest.target_id == str(ids["student_id"]),
                ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
            )) or 0) == 1
            version1 = db.get(FileVersion, int(submitted["fileVersionId"])); ids["asset_ids"].append(int(version1.asset_id))
            assert version1.status == "ARCHIVED"

        job = export_service.create_student_export_job(ids["student_id"], user)
        ids["job_ids"].append(int(job["id"]))
        completed = export_service.run_export_job(int(job["id"]), user)
        assert completed["status"] == "SUCCEEDED"
        with session() as db:
            job_row = db.get(ExportJob, int(job["id"]))
            zip_file = db.get(FileObject, int(job_row.file_object_id))
            xlsx_id = int(job_row.result_json["xlsxFileObjectId"])
            xlsx_file = db.get(FileObject, xlsx_id)
            ids["file_ids"].extend([int(zip_file.id), int(xlsx_file.id)])
            ids["file_keys"].extend([zip_file.file_key, xlsx_file.file_key])
            path = get_backend().fetch_local(zip_file.file_key)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == zip_file.sha256
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                assert "manifest.json" in names and "档案清单.xlsx" in names
                package_manifest = json.loads(archive.read("manifest.json"))
                assert package_manifest["materialFileCount"] == 1
                material_entry = next(name for name in names if "/materials/" in name)
                assert hashlib.sha256(archive.read(material_entry)).hexdigest() == first["items"][0]["sha256"]

        revoked = manifest_service.revoke_manifest(ids["student_id"], "真实验收撤销后重开", user)
        assert revoked["status"] == "REVOKED"
        with session() as db:
            reopened_version = int(db.scalar(select(GraduationStudentMaterial.version).where(
                GraduationStudentMaterial.tenant_id == tenant_id,
                GraduationStudentMaterial.gd_student_id == ids["student_id"],
                GraduationStudentMaterial.material_code == "THESIS_FINAL",
                GraduationStudentMaterial.is_deleted.is_(False),
            )))
        second_file = _make_file("v2", user, marker)
        ids["file_ids"].append(int(second_file["fileId"])); ids["file_keys"].append(second_file["fileKey"])
        second = command_service.submit_material(
            user, "THESIS_FINAL", int(second_file["fileId"]), gd_student_id=ids["student_id"],
            expected_version=reopened_version,
        )
        command_service.review_material(
            int(second["materialId"]), int(second["fileVersionId"]), "APPROVE", "新版本验收通过", user,
            expected_version=int(second["version"]),
        )
        second_manifest = manifest_service.file_archive(ids["student_id"], f"ACC2-{marker}", user)
        ids["manifest_ids"].append(int(second_manifest["manifestId"]))
        assert second_manifest["revision"] == 2
        with session() as db:
            old = db.get(FileVersion, int(submitted["fileVersionId"]))
            assert old.status == "ARCHIVED" and old.is_current is False
            assert db.get(FileObject, int(first_file["fileId"])).sha256 == first["items"][0]["sha256"]
        latest = query_service.latest_manifest(ids["student_id"], user)
        assert latest["revision"] == 2 and latest["manifestId"] == second_manifest["manifestId"]
        print(json.dumps({
            "mysql": True, "tenantId": str(tenant_id), "singleV2Manifest": True,
            "idempotentFreeze": True, "zipXlsxManifestConsistent": True,
            "archivedVersionImmutable": True, "reopenedRevision": 2,
        }, ensure_ascii=False))
    finally:
        _cleanup(ids, ids.get("file_keys", []))


if __name__ == "__main__":
    main()
