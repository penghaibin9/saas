"""岗位实习归档包的流式生成实现。

冻结 Manifest 是唯一输入；材料按块校验 SHA-256/大小并写入 ZIP64，最终通过路径型
FileObject 写入边界持久化。任何异常都会删除临时文件，不把整包或单个材料读入内存。
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.models import InternshipArchive, InternshipEvidencePackage, StudentProfile
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject, FileVersion
from app.modules.internship.services import internship_material_center_service as core
from app.services.db_service import _tid, session
from app.services.generated_file_path_service import store_generated_path
from app.services.storage import get_backend
from app.services.streaming_archive_service import add_json, add_path, temporary_zip


def _safe_name(value: str, fallback: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", str(value or fallback).strip()) or fallback


def build_versioned_package(internship_id, user=None) -> dict:
    """从冻结 FileVersion Manifest 生成真实归档包，不整文件读内存。"""
    zip_path: Path | None = None
    try:
        with session() as db:
            record = core._assert_scope(db, internship_id, user, "生成真实版本实习归档包")
            archive_record = db.scalar(select(InternshipArchive).where(
                InternshipArchive.tenant_id == _tid(),
                InternshipArchive.internship_id == record.id,
                InternshipArchive.status == "ARCHIVED",
                InternshipArchive.is_deleted.is_(False),
            ).with_for_update())
            if not archive_record:
                raise AppException("DATA_CONFLICT", "仅已归档学生可生成归档包")

            manifest = db.scalar(select(ArchiveManifest).where(
                ArchiveManifest.tenant_id == _tid(),
                ArchiveManifest.module_code == core.MODULE_CODE,
                ArchiveManifest.target_id == str(record.id),
                ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
                ArchiveManifest.is_deleted.is_(False),
            ).order_by(ArchiveManifest.revision.desc()).with_for_update())
            if not manifest:
                raise AppException("DATA_CONFLICT", "缺少已冻结的 file_version 归档清单")

            items = db.scalars(select(ArchiveManifestItem).where(
                ArchiveManifestItem.tenant_id == _tid(),
                ArchiveManifestItem.manifest_id == manifest.id,
                ArchiveManifestItem.is_deleted.is_(False),
            ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
            if not items:
                raise AppException("DATA_CONFLICT", "归档清单没有真实文件版本")

            latest = int(db.scalar(select(func.max(InternshipEvidencePackage.package_version)).where(
                InternshipEvidencePackage.tenant_id == _tid(),
                InternshipEvidencePackage.package_type == "ARCHIVE",
                InternshipEvidencePackage.target_id == record.id,
            )) or 0)
            package = InternshipEvidencePackage(
                tenant_id=_tid(), package_type="ARCHIVE", batch_id=record.batch_id,
                target_id=record.id, package_version=latest + 1, status="FAILED",
                generated_by_name=core._op_name(user), generated_at=datetime.utcnow(), row_count=1,
            )
            db.add(package)
            try:
                db.flush()
            except IntegrityError as exc:
                raise AppException("DATA_CONFLICT", "归档包正在生成，请稍后重试") from exc

            zip_path, archive_zip = temporary_zip(prefix="internship-archive-")
            payload_items: list[dict] = []
            used_paths: set[str] = set()
            backend = get_backend()
            try:
                for item in items:
                    version = db.scalar(select(FileVersion).where(
                        FileVersion.id == item.version_id,
                        FileVersion.tenant_id == _tid(),
                        FileVersion.is_deleted.is_(False),
                    ))
                    file_row = db.scalar(select(FileObject).where(
                        FileObject.id == item.file_object_id,
                        FileObject.tenant_id == _tid(),
                        FileObject.is_deleted.is_(False),
                    ))
                    if not version or not file_row or version.file_object_id != file_row.id:
                        raise AppException("DATA_CONFLICT", "归档清单引用的文件版本已损坏")
                    if not (core._file_ready(file_row) and version.status in core.READY_VERSION_STATUS):
                        raise AppException("DATA_CONFLICT", "归档材料安全状态已变化，禁止打包")
                    if file_row.sha256 != item.sha256_snapshot:
                        raise AppException("DATA_CONFLICT", "归档材料哈希与冻结清单不一致")
                    source = backend.fetch_local(file_row.file_key)
                    if not source or not source.exists():
                        raise AppException("DATA_CONFLICT", "归档材料字节不存在，禁止生成不完整归档包")

                    safe_file = _safe_name(item.file_name_snapshot, f"file-{file_row.id}")
                    safe_code = _safe_name(item.material_code, "MATERIAL").replace(":", "_")
                    archive_path = f"materials/{int(item.sort_no or 0):03d}_{safe_code}_{safe_file}"
                    if archive_path.startswith(("/", "\\")) or ".." in Path(archive_path).parts:
                        raise AppException("DATA_CONFLICT", "归档文件路径不安全")
                    if archive_path in used_paths:
                        raise AppException("DATA_CONFLICT", "归档包内文件路径冲突")
                    used_paths.add(archive_path)
                    digest, size = add_path(
                        archive_zip,
                        archive_path,
                        source,
                        expected_sha256=item.sha256_snapshot,
                        expected_size=int(item.size_snapshot or 0),
                    )
                    payload_items.append({
                        "materialCode": item.material_code,
                        "assetId": str(item.asset_id),
                        "versionId": str(item.version_id),
                        "fileObjectId": str(item.file_object_id),
                        "fileName": safe_file,
                        "archivePath": archive_path,
                        "sizeBytes": size,
                        "sha256": digest,
                        "reviewStatus": item.review_status,
                        "scanResult": item.scan_result,
                    })

                package_manifest = {
                    "schemaVersion": "INTERNSHIP_ARCHIVE_PACKAGE_FILE_VERSION_V2",
                    "manifestId": str(manifest.id),
                    "manifestRevision": int(manifest.revision or 0),
                    "manifestSha256": manifest.manifest_sha256,
                    "tenantId": str(_tid()),
                    "internshipId": str(record.id),
                    "studentId": str(record.student_id),
                    "batchId": str(record.batch_id or ""),
                    "generatedAt": datetime.utcnow().isoformat() + "Z",
                    "generatedBy": core._op_name(user),
                    "items": payload_items,
                }
                add_json(archive_zip, "manifest.json", package_manifest)
            finally:
                archive_zip.close()

            student = db.get(StudentProfile, record.student_id)
            safe_student = _safe_name(getattr(student, "real_name", ""), "学生")
            meta = store_generated_path(
                zip_path,
                f"实习归档_{safe_student}_manifest{manifest.revision}_v{package.package_version}.zip",
                biz_type="ARCHIVE_PACKAGE",
                biz_id=f"ARCHIVE:{record.id}",
                mime_type="application/zip",
                user=user,
                visibility="BIZ_SCOPED",
                security_level="SENSITIVE",
                db=db,
            )
            package_manifest.update({
                "packageFileId": str(meta["fileId"]),
                "packageSha256": meta["sha256"],
                "packageSizeBytes": meta["sizeBytes"],
            })
            package.package_file_id = meta["fileId"]
            package.package_sha256 = meta["sha256"]
            package.package_size_bytes = meta["sizeBytes"]
            package.manifest_json = package_manifest
            package.included_items = payload_items
            package.missing_items = []
            package.rule_version = manifest.rule_version
            package.metric_version = "file-version-manifest-v2-streaming"
            package.status = "READY"
            package.file_count = len(payload_items)
            manifest.package_file_id = int(meta["fileId"])
            manifest.status = "PACKAGED"
            archive_record.package_file_id = str(meta["fileId"])
            core._trail(db, record.id, "VERSIONED_PACKAGE", {
                "manifestId": str(manifest.id),
                "packageId": str(package.id),
                "packageVersion": package.package_version,
                "fileId": str(meta["fileId"]),
                "sha256": meta["sha256"],
                "fileVersionCount": len(payload_items),
                "streaming": True,
            }, user)
            db.commit()
            return {
                "fileId": str(meta["fileId"]),
                "fileName": meta["fileName"],
                "sizeBytes": meta["sizeBytes"],
                "sha256": meta["sha256"],
                "packageId": str(package.id),
                "packageVersion": package.package_version,
                "manifestId": str(manifest.id),
                "manifestRevision": manifest.revision,
                "status": "READY",
                "packageReady": True,
            }
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)
