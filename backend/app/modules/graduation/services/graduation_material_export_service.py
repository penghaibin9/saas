"""阶段 6：毕业设计真实 Manifest、流式 ZIP/XLSX 与 ExportJob 生命周期。"""
from __future__ import annotations

import hashlib
import json
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from sqlalchemy import func, or_, select

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.models import GraduationArchiveRecord, GraduationBatch, GraduationProposal, GraduationFinal, GraduationStudent
from app.models.data_exchange import ExportJob
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileBinding, FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.modules.graduation.services import graduation_material_catalog_service as catalog
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access
from app.services.db_service import _iso, _tid, session
from app.services.file_content_security import sanitize_filename
from app.services.file_scan_constants import SCAN_NOT_REQUIRED
from app.services.message_identity import resolve_message_user_id
from app.services.storage import get_backend

MODULE_CODE = "GRADUATION"
ARCHIVE_TYPE = "GRADUATION_FILE_VERSION"
TARGET_TYPE = "GRADUATION_STUDENT"
EXPORT_TTL_HOURS = 24


def _actor_id(user: dict | None) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _actor_name(user: dict | None) -> str:
    actor = user or {}
    return str(actor.get("realName") or actor.get("name") or actor.get("loginName") or "系统")[:100]


def _safe_excel(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    # Excel 公式注入防护：用户可控文本以 = + - @ 开头时强制文本化。
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value


def _sha256_path(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256(); size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk); digest.update(chunk)
    return digest.hexdigest(), size


def _persist_generated_path(db, source: Path, filename: str, *, biz_type: str,
                            biz_id: str, user: dict, security_level: str = "HIGHLY_SENSITIVE") -> FileObject:
    safe_name = sanitize_filename(filename)
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "bin"
    key = f"exports/{_tid()}/{datetime.utcnow():%Y%m%d}/{uuid.uuid4().hex}.{ext}"
    backend = get_backend()
    staged = backend.staging_path(key)
    staged.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != staged.resolve():
        with source.open("rb") as src, staged.open("wb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
    sha256, size = _sha256_path(staged)
    try:
        backend.persist(key, staged)
    except Exception:
        staged.unlink(missing_ok=True)
        raise
    mime = {
        "zip": "application/zip",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
    }.get(ext, "application/octet-stream")
    now = datetime.utcnow()
    row = FileObject(
        tenant_id=_tid(), file_key=key, file_name=safe_name, ext=ext, mime_type=mime,
        size_bytes=size, sha256=sha256, biz_type=biz_type, biz_id=str(biz_id),
        owner_user_id=_actor_id(user), visibility="BIZ_SCOPED", security_level=security_level,
        status="AVAILABLE", storage_backend=str(settings.FILE_STORAGE_BACKEND or "local").lower(),
        storage_zone="EXPORT", upload_source="SYSTEM", scan_required=False,
        scan_status=SCAN_NOT_REQUIRED, scan_attempts=0, scanned_at=now, available_at=now,
        created_by=_actor_id(user),
    )
    db.add(row); db.flush()
    return row


def _student(student_id: int, user: dict, *, lock: bool = False) -> GraduationStudent:
    with session() as db:
        stmt = select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(student_id),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        )
        if lock: stmt = stmt.with_for_update()
        row = db.scalars(stmt).first()
        if not row: raise not_found("毕业设计学生不存在")
        assert_student_access(db, row, "archive.manifest")
        return row


def _prepare_student_materials(student_id: int, user: dict) -> None:
    """在冻结事务之前完成旧记录同步和结构化 PDF 快照，避免跨会话可见性问题。"""
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(student_id),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student: raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "archive.prepare")
        proposal = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == int(student.id),
            GraduationProposal.status == "APPROVED", GraduationProposal.is_deleted.is_(False),
        ).order_by(GraduationProposal.id.desc())).first()
        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == int(student.id),
            GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc())).first()
        proposal_id = int(proposal.id) if proposal else None
        final_id = int(final.id) if final else None
    if proposal_id: catalog.sync_record("PROPOSAL", proposal_id, user)
    if final_id: catalog.sync_record("FINAL", final_id, user)
    with session() as db:
        student = db.get(GraduationStudent, int(student_id))
        catalog.ensure_structured_snapshots(db, student, user)
        db.commit()


def _manifest_view(db, manifest: ArchiveManifest) -> dict:
    items = db.scalars(select(ArchiveManifestItem).where(
        ArchiveManifestItem.tenant_id == _tid(),
        ArchiveManifestItem.manifest_id == int(manifest.id),
        ArchiveManifestItem.is_deleted.is_(False),
    ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
    return {
        "manifestId": str(manifest.id), "revision": int(manifest.revision or 1),
        "status": manifest.status, "ruleVersion": manifest.rule_version or "",
        "manifestSha256": manifest.manifest_sha256 or "",
        "packageFileId": str(manifest.package_file_id or ""),
        "frozenAt": _iso(manifest.frozen_at), "revokedAt": _iso(manifest.revoked_at),
        "revokeReason": manifest.revoke_reason or "", "itemCount": len(items),
        "items": [{
            "materialCode": item.material_code, "assetId": str(item.asset_id),
            "fileVersionId": str(item.version_id), "versionId": str(item.version_id),
            "fileObjectId": str(item.file_object_id), "fileName": item.file_name_snapshot,
            "sizeBytes": item.size_snapshot, "sha256": item.sha256_snapshot,
            "scanResult": item.scan_result, "reviewStatus": item.review_status,
            "uploader": item.uploader_snapshot or "", "submittedAt": _iso(item.submitted_at_snapshot),
            "sortNo": int(item.sort_no or 0),
        } for item in items],
    }


def freeze_manifest(gd_student_id: int, archive_batch_no: str, user: dict) -> dict:
    _prepare_student_materials(int(gd_student_id), user)
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student: raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "archive.file")
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == int(student.id),
            GraduationArchiveRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if not archive: raise not_found("毕业设计归档记录不存在")
        if archive.status not in {"SUBMITTED", "FILED"}:
            raise AppException("DATA_CONFLICT", "仅已提交归档记录可冻结真实 Manifest")
        catalog._ensure_student_rows(db, student, user)
        materials = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).order_by(GraduationStudentMaterial.biz_stage, GraduationStudentMaterial.id).with_for_update()).all()
        required_codes = {
            code for code, spec in catalog.SPEC_BY_CODE.items()
            if spec["required"] and spec["archiveRequired"]
        }
        selected: list[tuple[GraduationStudentMaterial, FileVersion, FileObject]] = []
        missing: list[str] = []
        for material in materials:
            spec = catalog.SPEC_BY_CODE.get(material.material_code)
            archive_required = bool((spec or {}).get("archiveRequired", material.archive_status != "NOT_ARCHIVED"))
            required = material.material_code in required_codes
            if not archive_required and not material.current_version_id:
                continue
            if not material.current_version_id:
                if required: missing.append(material.material_name)
                continue
            version = db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id),
                FileVersion.asset_id == int(material.asset_id), FileVersion.is_current.is_(True),
                FileVersion.is_deleted.is_(False),
            ).with_for_update()).first()
            file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
            if not version or not file_obj:
                if required: missing.append(material.material_name)
                continue
            if version.status != "APPROVED" or material.review_status not in {"APPROVED", "NOT_REQUIRED"}:
                if required: missing.append(f"{material.material_name}（未审核通过）")
                continue
            try:
                legacy_ready = __import__(
                    "app.modules.graduation.services.graduation_material_center_service",
                    fromlist=["_require_file_ready"],
                )
                legacy_ready._require_file_ready(file_obj)
            except AppException:
                if required: missing.append(f"{material.material_name}（安全状态异常）")
                continue
            selected.append((material, version, file_obj))
        if missing:
            raise AppException("DATA_CONFLICT", "归档材料未齐全：" + "、".join(sorted(set(missing))))
        if not selected:
            raise AppException("DATA_CONFLICT", "毕业设计归档没有可冻结的真实文件版本")
        active = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
            ArchiveManifest.target_id == str(student.id),
            ArchiveManifest.status.in_(("PREPARED", "FROZEN", "PACKAGED")),
            ArchiveManifest.is_deleted.is_(False),
        ).with_for_update()).all()
        for old in active: old.status = "SUPERSEDED"
        revision = int(db.scalar(select(func.max(ArchiveManifest.revision)).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
            ArchiveManifest.target_id == str(student.id),
        )) or 0) + 1
        payload_items = [{
            "materialCode": material.material_code, "assetId": int(material.asset_id),
            "fileVersionId": int(version.id), "fileObjectId": int(file_obj.id),
            "fileNameSnapshot": file_obj.file_name, "sizeSnapshot": int(file_obj.size_bytes or 0),
            "sha256Snapshot": file_obj.sha256, "scanResult": str(file_obj.scan_status or "").upper(),
            "reviewStatus": material.review_status,
            "uploaderSnapshot": version.uploader_name_snapshot or "",
            "submittedAt": _iso(version.submitted_at),
        } for material, version, file_obj in selected]
        payload = {
            "schemaVersion": "GRADUATION_MATERIAL_MANIFEST_V2",
            "tenantId": str(_tid()), "batchId": str(student.batch_id),
            "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
            "studentNo": student.student_no or "", "studentName": student.name,
            "topicId": str(student.topic_id or ""), "topicTitle": student.topic_title or "",
            "advisorName": student.advisor_name or "", "archiveBatchNo": archive_batch_no,
            "revision": revision, "generatedBy": _actor_name(user), "items": payload_items,
        }
        digest = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        rule_version = max((int(row.rule_version or 1) for row in materials), default=1)
        manifest = ArchiveManifest(
            tenant_id=_tid(), module_code=MODULE_CODE, archive_type=ARCHIVE_TYPE,
            target_type=TARGET_TYPE, target_id=str(student.id), revision=revision,
            status="FROZEN", rule_version=f"GD_MATERIAL_STANDARD:v{rule_version}",
            manifest_sha256=digest, created_by_name=_actor_name(user),
            frozen_at=datetime.utcnow(), created_by=_actor_id(user),
        )
        db.add(manifest); db.flush()
        for sort_no, (material, version, file_obj) in enumerate(selected, start=1):
            db.add(ArchiveManifestItem(
                tenant_id=_tid(), manifest_id=int(manifest.id), material_code=material.material_code,
                asset_id=int(material.asset_id), version_id=int(version.id),
                file_object_id=int(file_obj.id), file_name_snapshot=file_obj.file_name,
                size_snapshot=int(file_obj.size_bytes or 0), sha256_snapshot=file_obj.sha256,
                review_status=material.review_status, scan_result=str(file_obj.scan_status or "").upper(),
                uploader_snapshot=version.uploader_name_snapshot,
                submitted_at_snapshot=version.submitted_at, sort_no=sort_no,
                created_by=_actor_id(user),
            ))
            material.archive_status = "FROZEN"
            material.archived_revision = revision
            version.status = "ARCHIVED"
        archive.status = "FILED"
        archive.verified_by = _actor_name(user)
        archive.filed_at = datetime.utcnow()
        archive.archive_batch_no = str(archive_batch_no or archive.archive_batch_no or "")[:100]
        archive.manifest_hash = digest
        archive.version = int(archive.version or 0) + 1
        student.stage = "ARCHIVED"
        student.version = int(student.version or 0) + 1
        db.flush(); row = _manifest_view(db, manifest); db.commit()
        return row


def latest_manifest(gd_student_id: int, user: dict) -> dict:
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student: raise not_found("毕业设计归档清单不存在")
        assert_student_access(db, student, "archive.manifest.view")
        row = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
            ArchiveManifest.target_id == str(student.id), ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc())).first()
        if not row: raise not_found("毕业设计归档清单不存在")
        return _manifest_view(db, row)


def _scope_students(db, scope_type: str, scope_value: str, batch_id: int, user: dict) -> list[GraduationStudent]:
    scope_type = str(scope_type or "BATCH").upper()
    allowed = set(accessible_student_ids(db, _tid(), batch_id=int(batch_id)))
    stmt = select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.id.in_(allowed or {-1}), GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    )
    if scope_type == "STUDENT":
        if not str(scope_value).isdigit(): raise not_found("归档范围不存在")
        stmt = stmt.where(GraduationStudent.id == int(scope_value))
    elif scope_type == "CLASS": stmt = stmt.where(GraduationStudent.class_id == str(scope_value))
    elif scope_type == "MAJOR": stmt = stmt.where(GraduationStudent.major_id == str(scope_value))
    elif scope_type == "COLLEGE": stmt = stmt.where(GraduationStudent.college_id == str(scope_value))
    elif scope_type != "BATCH": raise AppException("VALIDATION_ERROR", "归档范围类型不支持")
    rows = list(db.scalars(stmt.order_by(GraduationStudent.college_id, GraduationStudent.class_id,
                                         GraduationStudent.student_no, GraduationStudent.id)).all())
    if not rows: raise not_found("归档范围不存在")
    return rows


def create_export_job(*, batch_id: int, scope_type: str, scope_value: str, user: dict) -> dict:
    with session() as db:
        students = _scope_students(db, scope_type, scope_value, int(batch_id), user)
        ref = uuid.uuid4().hex
        row = ExportJob(
            tenant_id=_tid(), module_code=MODULE_CODE, export_type="GRADUATION_ARCHIVE_ZIP_XLSX",
            purpose=f"毕业设计{scope_type.upper()}归档包与档案清单",
            adapter_type="GRADUATION_ARCHIVE", adapter_ref=ref,
            filter_snapshot_json={
                "batchId": str(batch_id), "scopeType": scope_type.upper(),
                "scopeValue": str(scope_value or ""), "studentIds": [str(item.id) for item in students],
            },
            data_scope_snapshot_json={
                "actor": _actor_name(user), "allowedStudentIds": [str(item.id) for item in students],
            },
            status="CREATED", progress=0, row_count=0,
            expires_at=datetime.utcnow() + timedelta(hours=EXPORT_TTL_HOURS),
            operator_id=_actor_id(user), created_by=_actor_id(user),
            result_json={"retryable": True},
        )
        db.add(row); db.commit(); db.refresh(row)
        return {"id": str(row.id), "status": row.status, "version": int(row.version or 0),
                "studentCount": len(students), "expiresAt": _iso(row.expires_at)}


def _job(db, job_id: int, user: dict, *, lock: bool = False) -> ExportJob:
    stmt = select(ExportJob).where(
        ExportJob.tenant_id == _tid(), ExportJob.id == int(job_id),
        ExportJob.module_code == MODULE_CODE, ExportJob.adapter_type == "GRADUATION_ARCHIVE",
        ExportJob.is_deleted.is_(False),
    )
    actor = _actor_id(user)
    if actor: stmt = stmt.where(ExportJob.operator_id == actor)
    if lock: stmt = stmt.with_for_update()
    row = db.scalars(stmt).first()
    if not row: raise not_found("毕业设计归档任务不存在")
    return row


def _export_job_view(row: ExportJob) -> dict:
    return {
        "id": str(row.id), "status": row.status, "progress": int(row.progress or 0),
        "rowCount": int(row.row_count or 0), "fileObjectId": str(row.file_object_id or ""),
        "expiresAt": _iso(row.expires_at), "revokedAt": _iso(row.revoked_at),
        "revokeReason": row.revoke_reason or "", "result": row.result_json or {},
        "errorMessage": row.error_message or "", "version": int(row.version or 0),
        "createdAt": _iso(row.created_at), "updatedAt": _iso(row.updated_at),
    }


def get_export_job(job_id: int, user: dict) -> dict:
    with session() as db: return _export_job_view(_job(db, job_id, user))


def _latest_manifests(db, students: list[GraduationStudent]) -> list[tuple[GraduationStudent, ArchiveManifest]]:
    result = []
    for student in students:
        manifest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
            ArchiveManifest.target_id == str(student.id),
            ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
            ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc())).first()
        if not manifest: raise AppException("DATA_CONFLICT", f"学生 {student.student_no or student.name} 尚未生成有效 Manifest")
        result.append((student, manifest))
    return result


def _write_index_xlsx(path: Path, rows: list[dict]) -> None:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("毕业设计档案清单")
    headers = ["批次", "学院", "专业", "班级", "学号", "姓名", "指导教师", "题目",
               "材料代码", "材料名称", "文件名", "文件版本", "文件大小", "SHA-256",
               "扫描状态", "审核状态", "上传时间", "归档 revision"]
    sheet.append(headers)
    for row in rows:
        sheet.append([_safe_excel(row.get(key, "")) for key in (
            "batch", "college", "major", "class", "studentNo", "studentName", "advisor", "topic",
            "materialCode", "materialName", "fileName", "fileVersion", "fileSize", "sha256",
            "scanStatus", "reviewStatus", "submittedAt", "revision",
        )])
    workbook.save(path)


def run_export_job(job_id: int, user: dict) -> dict:
    with session() as db:
        row = _job(db, job_id, user, lock=True)
        if row.status == "SUCCEEDED": return _export_job_view(row)
        if row.revoked_at or row.status in {"REVOKED", "EXPIRED"}: raise not_found("毕业设计归档任务不存在")
        if row.status not in {"CREATED", "FAILED"}: raise AppException("DATA_CONFLICT", "归档任务正在执行")
        snapshot = dict(row.filter_snapshot_json or {})
        row.status = "PROCESSING"; row.progress = 5; row.error_message = None
        row.version = int(row.version or 0) + 1; db.commit()
    try:
        with session() as db:
            students = _scope_students(db, snapshot.get("scopeType"), snapshot.get("scopeValue"),
                                       int(snapshot.get("batchId")), user)
            pairs = _latest_manifests(db, students)
            manifest_ids = {int(manifest.id) for _, manifest in pairs}
            items = db.scalars(select(ArchiveManifestItem).where(
                ArchiveManifestItem.tenant_id == _tid(),
                ArchiveManifestItem.manifest_id.in_(manifest_ids),
                ArchiveManifestItem.is_deleted.is_(False),
            ).order_by(ArchiveManifestItem.manifest_id, ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
            file_ids = {int(item.file_object_id) for item in items}
            files = {int(file.id): file for file in db.scalars(select(FileObject).where(
                FileObject.tenant_id == _tid(), FileObject.id.in_(file_ids or {-1}),
                FileObject.is_deleted.is_(False), FileObject.status == "AVAILABLE",
            )).all()}
            manifests = {int(manifest.id): (student, manifest) for student, manifest in pairs}
            batch = db.get(GraduationBatch, int(snapshot.get("batchId")))
            backend = get_backend()
            xlsx_key = f"exports/{_tid()}/{uuid.uuid4().hex}.xlsx"
            zip_key = f"exports/{_tid()}/{uuid.uuid4().hex}.zip"
            xlsx_path = backend.staging_path(xlsx_key); xlsx_path.parent.mkdir(parents=True, exist_ok=True)
            zip_path = backend.staging_path(zip_key); zip_path.parent.mkdir(parents=True, exist_ok=True)
            index_rows: list[dict] = []
            package_items: list[dict] = []
            used_paths: set[str] = set()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                for item in items:
                    student, manifest = manifests[int(item.manifest_id)]
                    file_obj = files.get(int(item.file_object_id))
                    if not file_obj: raise AppException("DATA_CONFLICT", "Manifest 引用文件不存在或已失效")
                    source = backend.fetch_local(file_obj.file_key)
                    if not source or not source.exists(): raise AppException("DATA_CONFLICT", "Manifest 引用文件字节不存在")
                    actual_sha, actual_size = _sha256_path(source)
                    if actual_sha != item.sha256_snapshot or actual_size != int(item.size_snapshot or 0):
                        raise AppException("DATA_CONFLICT", "Manifest 文件哈希或大小已变化")
                    student_dir = sanitize_filename(f"{student.student_no or student.id}_{student.name}")
                    base_name = sanitize_filename(item.file_name_snapshot)
                    archive_path = f"students/{student_dir}/materials/{item.sort_no:03d}_{item.material_code}_{base_name}"
                    counter = 2
                    original_path = archive_path
                    while archive_path in used_paths:
                        stem, dot, suffix = original_path.rpartition(".")
                        archive_path = f"{stem}_{counter}.{suffix}" if dot else f"{original_path}_{counter}"
                        counter += 1
                    if archive_path.startswith(("/", "\\")) or ".." in Path(archive_path).parts:
                        raise AppException("DATA_CONFLICT", "归档文件路径不安全")
                    used_paths.add(archive_path); archive.write(source, archive_path)
                    material_name = catalog.SPEC_BY_CODE.get(item.material_code, {}).get("materialName", item.material_code)
                    index_rows.append({
                        "batch": batch.batch_name if batch else snapshot.get("batchId"),
                        "college": student.college_id or "", "major": student.major_id or "",
                        "class": student.class_name or student.class_id or "", "studentNo": student.student_no or "",
                        "studentName": student.name, "advisor": student.advisor_name or "", "topic": student.topic_title or "",
                        "materialCode": item.material_code, "materialName": material_name,
                        "fileName": item.file_name_snapshot, "fileVersion": str(item.version_id),
                        "fileSize": int(item.size_snapshot or 0), "sha256": item.sha256_snapshot,
                        "scanStatus": item.scan_result, "reviewStatus": item.review_status or "",
                        "submittedAt": _iso(item.submitted_at_snapshot), "revision": int(manifest.revision),
                    })
                    package_items.append({
                        "gdStudentId": str(student.id), "studentNo": student.student_no or "",
                        "manifestId": str(manifest.id), "revision": int(manifest.revision),
                        "materialCode": item.material_code, "fileVersionId": str(item.version_id),
                        "fileObjectId": str(item.file_object_id), "archivePath": archive_path,
                        "sizeBytes": int(item.size_snapshot or 0), "sha256": item.sha256_snapshot,
                    })
                _write_index_xlsx(xlsx_path, index_rows)
                archive.write(xlsx_path, "档案清单.xlsx")
                manifest_json = {
                    "schemaVersion": "GRADUATION_EXPORT_PACKAGE_V2",
                    "tenantId": str(_tid()), "batchId": str(snapshot.get("batchId")),
                    "scopeType": snapshot.get("scopeType"), "scopeValue": snapshot.get("scopeValue"),
                    "generatedAt": datetime.utcnow().isoformat() + "Z", "generatedBy": _actor_name(user),
                    "studentCount": len(students), "manifestCount": len(pairs),
                    "materialFileCount": len(package_items), "items": package_items,
                }
                archive.writestr("manifest.json", json.dumps(manifest_json, ensure_ascii=False, indent=2, sort_keys=True))
            # ZIP 完成后再次核对条目数：材料 + XLSX + manifest.json。
            with zipfile.ZipFile(zip_path, "r") as check:
                material_entries = [name for name in check.namelist() if "/materials/" in name]
                if len(material_entries) != len(package_items):
                    raise AppException("DATA_CONFLICT", "ZIP 文件数与 Manifest 不一致")
            xlsx_file = _persist_generated_path(
                db, xlsx_path, f"毕业设计档案清单_{datetime.now():%Y%m%d_%H%M}.xlsx",
                biz_type="GRADUATION_ARCHIVE_INDEX", biz_id=str(snapshot.get("batchId")), user=user,
            )
            zip_file = _persist_generated_path(
                db, zip_path, f"毕业设计归档包_{datetime.now():%Y%m%d_%H%M}.zip",
                biz_type="GRADUATION_ARCHIVE_PACKAGE", biz_id=str(snapshot.get("batchId")), user=user,
            )
            row = _job(db, job_id, user, lock=True)
            row.status = "SUCCEEDED"; row.progress = 100; row.row_count = len(index_rows)
            row.file_object_id = int(zip_file.id); row.finished_at = datetime.utcnow()
            row.result_json = {
                "zipFileObjectId": str(zip_file.id), "zipFileName": zip_file.file_name,
                "zipSha256": zip_file.sha256, "zipSizeBytes": int(zip_file.size_bytes or 0),
                "xlsxFileObjectId": str(xlsx_file.id), "xlsxFileName": xlsx_file.file_name,
                "xlsxSha256": xlsx_file.sha256, "studentCount": len(students),
                "manifestIds": [str(manifest.id) for _, manifest in pairs],
                "materialFileCount": len(package_items), "retryable": False,
            }
            row.version = int(row.version or 0) + 1
            for _, manifest in pairs:
                manifest.status = "PACKAGED"; manifest.package_file_id = int(zip_file.id)
            db.commit(); return _export_job_view(row)
    except Exception as exc:
        with session() as db:
            row = _job(db, job_id, user, lock=True)
            row.status = "FAILED"; row.error_message = str(exc)[:4000]; row.progress = 0
            row.result_json = {**(row.result_json or {}), "retryable": True}
            row.version = int(row.version or 0) + 1; db.commit()
        raise


def revoke_manifest(gd_student_id: int, reason: str, user: dict) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5: raise AppException("VALIDATION_ERROR", "撤销原因必填且不少于5字")
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
            GraduationStudent.is_deleted.is_(False),
        )).first()
        if not student: raise not_found("毕业设计归档清单不存在")
        assert_student_access(db, student, "archive.revoke")
        manifest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == TARGET_TYPE,
            ArchiveManifest.target_id == str(student.id),
            ArchiveManifest.status.in_(("FROZEN", "PACKAGED")), ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc()).with_for_update()).first()
        if not manifest: raise not_found("毕业设计归档清单不存在")
        manifest.status = "REVOKED"; manifest.revoked_at = datetime.utcnow()
        manifest.revoked_by = _actor_name(user); manifest.revoke_reason = reason[:500]
        materials = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.archived_revision == int(manifest.revision),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).all()
        for material in materials:
            material.archive_status = "ELIGIBLE" if material.review_status == "APPROVED" else "NOT_ARCHIVED"
            material.version = int(material.version or 0) + 1
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == int(student.id),
            GraduationArchiveRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if archive:
            archive.status = "SUBMITTED"; archive.reject_reason = reason[:500]
            archive.version = int(archive.version or 0) + 1
        jobs = db.scalars(select(ExportJob).where(
            ExportJob.tenant_id == _tid(), ExportJob.module_code == MODULE_CODE,
            ExportJob.adapter_type == "GRADUATION_ARCHIVE", ExportJob.status == "SUCCEEDED",
            ExportJob.is_deleted.is_(False),
        ).with_for_update()).all()
        revoked_jobs: list[str] = []
        for job in jobs:
            manifest_ids = {str(value) for value in (job.result_json or {}).get("manifestIds", [])}
            if str(manifest.id) not in manifest_ids: continue
            job.status = "REVOKED"; job.revoked_at = datetime.utcnow(); job.revoke_reason = reason[:500]
            job.version = int(job.version or 0) + 1; revoked_jobs.append(str(job.id))
            for file_id in (job.file_object_id, (job.result_json or {}).get("xlsxFileObjectId")):
                if str(file_id or "").isdigit():
                    file_obj = db.get(FileObject, int(file_id))
                    if file_obj: file_obj.status = "INVALIDATED"
        db.commit()
        return {"manifestId": str(manifest.id), "status": manifest.status,
                "revokedJobs": revoked_jobs, "reason": reason}
