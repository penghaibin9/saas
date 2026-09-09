"""岗位实习归档包的流式生成实现。

冻结 Manifest 是唯一输入；材料按块校验 SHA-256/大小并写入 ZIP64，最终通过路径型
FileObject 写入边界持久化。任何异常都会删除临时文件，不把整包或单个材料读入内存。
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.core.tenant_scoped import tenant_get
from app.models import (
    InternshipArchive, InternshipAuditTrail, InternshipEvidencePackage,
    InternshipRecord, StudentProfile,
)
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject, FileVersion
from app.modules.internship.services import internship_material_center_service as core
from app.services import file_service
from app.services.db_service import _tid, session
from app.services.generated_file_path_service import store_generated_path
from app.services.storage import get_backend
from app.services.streaming_archive_service import add_json, add_path, sha256_path, temporary_zip


MAX_BATCH_ROWS = 20
MAX_BATCH_FILES = 199
MAX_BATCH_BYTES = 90 * 1024 * 1024


def _safe_name(value: str, fallback: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", str(value or fallback).strip()) or fallback


def build_versioned_package(internship_id, user=None) -> dict:
    """从冻结 FileVersion Manifest 生成真实归档包，不整文件读内存。"""
    zip_path: Path | None = None
    try:
        with session() as db:
            from app.modules.internship.services.internship_audit_service import (
                assert_high_risk_write_available,
            )

            assert_high_risk_write_available(db)
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
            if core.manifest_digest(manifest, items) != manifest.manifest_sha256:
                raise AppException("DATA_CONFLICT", "归档 Manifest 哈希已漂移，禁止打包")

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

            student = tenant_get(db, StudentProfile, record.student_id)
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
                "fileCount": len(payload_items),
                "rowCount": 1,
                "status": "READY",
                "packageReady": True,
                "restoreCheckAvailable": True,
                "operationReceipt": {
                    "action": "ARCHIVE_PACKAGE",
                    "objectId": str(record.id),
                    "packageId": str(package.id),
                    "packageVersion": package.package_version,
                    "manifestId": str(manifest.id),
                    "manifestRevision": manifest.revision,
                    "packageSha256": meta["sha256"],
                    "fileCount": len(payload_items),
                    "rowCount": 1,
                    "status": "COMMITTED",
                },
            }
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)


def _verify_single_package_for_restore(package_id, user=None) -> dict:
    """流式校验归档包可恢复性；不把未验真的包写回业务表。"""
    with session() as db:
        from app.modules.internship.services.internship_audit_service import (
            assert_high_risk_write_available,
        )

        assert_high_risk_write_available(db)
        package = db.scalar(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.id == int(package_id),
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == "ARCHIVE",
            InternshipEvidencePackage.status == "READY",
            InternshipEvidencePackage.is_deleted.is_(False),
        ).with_for_update())
        if not package or not package.package_file_id:
            raise AppException("DATA_CONFLICT", "归档包不存在、未就绪或已失效")
        record = core._assert_scope(db, package.target_id, user, "校验实习归档恢复包")
        file_row = db.scalar(select(FileObject).where(
            FileObject.id == int(package.package_file_id),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ))
        if not file_row or not core._file_ready(file_row):
            raise AppException("DATA_CONFLICT", "归档包文件当前不可安全读取")
        source = get_backend().fetch_local(file_row.file_key)
        if not source or not source.exists():
            raise AppException("DATA_CONFLICT", "归档包字节不存在，恢复校验失败")
        package_hash, package_size = sha256_path(source)
        if package_hash != str(package.package_sha256 or file_row.sha256 or ""):
            raise AppException("DATA_CONFLICT", "归档包 SHA-256 与数据库回执不一致")
        if int(package_size) != int(package.package_size_bytes or file_row.size_bytes or -1):
            raise AppException("DATA_CONFLICT", "归档包大小与数据库回执不一致")

        manifest = db.scalar(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(),
            ArchiveManifest.module_code == core.MODULE_CODE,
            ArchiveManifest.target_id == str(record.id),
            ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
            ArchiveManifest.package_file_id == int(package.package_file_id),
            ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc()).with_for_update())
        if not manifest:
            raise AppException("DATA_CONFLICT", "归档包未绑定有效冻结 Manifest")
        manifest_items = db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == _tid(),
            ArchiveManifestItem.manifest_id == manifest.id,
            ArchiveManifestItem.is_deleted.is_(False),
        ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
        if core.manifest_digest(manifest, manifest_items) != manifest.manifest_sha256:
            raise AppException("DATA_CONFLICT", "归档 Manifest 哈希漂移，恢复校验失败")

        with zipfile.ZipFile(source, "r") as archive_zip:
            infos = archive_zip.infolist()
            if len(infos) != len(manifest_items) + 1:
                raise AppException("DATA_CONFLICT", "恢复行数不一致：归档包文件数量已变化")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise AppException("DATA_CONFLICT", "归档包路径重复或缺少 manifest.json")
            manifest_info = archive_zip.getinfo("manifest.json")
            if manifest_info.file_size > 2 * 1024 * 1024:
                raise AppException("DATA_CONFLICT", "归档包 manifest 超过安全上限")
            embedded = json.loads(archive_zip.read(manifest_info).decode("utf-8"))
            embedded_items = embedded.get("items") or []
            if (
                str(embedded.get("manifestId")) != str(manifest.id)
                or int(embedded.get("manifestRevision") or 0) != int(manifest.revision or 0)
                or str(embedded.get("manifestSha256") or "") != str(manifest.manifest_sha256 or "")
                or str(embedded.get("internshipId") or "") != str(record.id)
            ):
                raise AppException("DATA_CONFLICT", "归档包 manifest 身份或哈希不一致")
            if len(embedded_items) != len(manifest_items):
                raise AppException("DATA_CONFLICT", "恢复行数不一致：manifest 条目数已变化")
            db_items = {str(item.version_id): item for item in manifest_items}
            seen_paths: set[str] = set()
            for item in embedded_items:
                version_id = str(item.get("versionId") or "")
                frozen = db_items.get(version_id)
                archive_path = str(item.get("archivePath") or "")
                if not frozen or not archive_path or archive_path in seen_paths:
                    raise AppException("DATA_CONFLICT", "归档包包含未知版本或重复路径")
                if archive_path.startswith(("/", "\\")) or ".." in Path(archive_path).parts:
                    raise AppException("DATA_CONFLICT", "归档包包含不安全路径")
                if archive_path not in names:
                    raise AppException("DATA_CONFLICT", "恢复文件缺失，归档包不完整")
                seen_paths.add(archive_path)
                digest = hashlib.sha256()
                size = 0
                with archive_zip.open(archive_path, "r") as stream:
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                if (
                    digest.hexdigest() != str(frozen.sha256_snapshot or "")
                    or digest.hexdigest() != str(item.get("sha256") or "")
                    or size != int(frozen.size_snapshot or 0)
                    or size != int(item.get("sizeBytes") or 0)
                ):
                    raise AppException("DATA_CONFLICT", "恢复文件大小或 SHA-256 校验失败")

        if int(package.row_count or 0) != 1 or int(package.file_count or 0) != len(manifest_items):
            raise AppException("DATA_CONFLICT", "数据库恢复计数与归档包不一致")
        core._trail(db, record.id, "ARCHIVE_RESTORE_VERIFIED", {
            "packageId": str(package.id),
            "packageVersion": package.package_version,
            "manifestId": str(manifest.id),
            "rowCount": 1,
            "fileCount": len(manifest_items),
            "packageSha256": package_hash,
        }, user)
        db.commit()
        return {
            "packageId": str(package.id),
            "packageVersion": package.package_version,
            "manifestId": str(manifest.id),
            "manifestRevision": manifest.revision,
            "packageSha256": package_hash,
            "verifiedRowCount": 1,
            "verifiedFileCount": len(manifest_items),
            "restoreReady": True,
            "verificationOnly": True,
            "operationReceipt": {
                "action": "ARCHIVE_RESTORE_VERIFY",
                "objectId": str(record.id),
                "packageId": str(package.id),
                "rowCount": 1,
                "fileCount": len(manifest_items),
                "packageSha256": package_hash,
                "status": "VERIFIED",
            },
        }


def _scoped_batch_query(batch_id, user):
    from app.modules.internship.services.internship_scope import (
        apply_internship_record_scope,
    )

    query = select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == int(batch_id),
        InternshipRecord.is_deleted.is_(False),
    )
    return apply_internship_record_scope(query, user)


def build_batch_versioned_package(batch_id, user=None, *, after_id=0,
                                  limit=MAX_BATCH_ROWS) -> dict:
    """从同一批次的冻结 Manifest 流式生成有界分片包。"""
    batch_id = int(batch_id)
    after_id = max(int(after_id or 0), 0)
    limit = int(limit or MAX_BATCH_ROWS)
    if limit < 1 or limit > MAX_BATCH_ROWS:
        raise AppException(
            "VALIDATION_ERROR", f"批次归档包每片必须为 1-{MAX_BATCH_ROWS} 名学生",
        )

    zip_path: Path | None = None
    try:
        with session() as db:
            from app.modules.internship.services.internship_audit_service import (
                assert_high_risk_write_available,
            )

            assert_high_risk_write_available(db)
            scoped = _scoped_batch_query(batch_id, user).order_by(None)
            scoped_ids = scoped.with_only_columns(
                InternshipRecord.id, maintain_column_froms=True,
            ).subquery()
            scoped_total = int(db.scalar(
                select(func.count()).select_from(scoped_ids)
            ) or 0)
            if not scoped_total:
                raise not_found("当前数据范围内没有该批次的实习学生")
            archived_total = int(db.scalar(
                select(func.count()).select_from(InternshipArchive).join(
                    scoped_ids, scoped_ids.c.id == InternshipArchive.internship_id,
                ).where(
                    InternshipArchive.tenant_id == _tid(),
                    InternshipArchive.status == "ARCHIVED",
                    InternshipArchive.is_deleted.is_(False),
                )
            ) or 0)
            if archived_total != scoped_total:
                raise AppException(
                    "DATA_CONFLICT", "批次包仅在当前数据范围内全部学生完成归档后生成",
                    details={
                        "scopedTotal": scoped_total,
                        "archivedTotal": archived_total,
                        "remaining": scoped_total - archived_total,
                    },
                )

            page = db.scalars(
                scoped.where(InternshipRecord.id > after_id)
                .order_by(InternshipRecord.id).limit(limit + 1)
            ).all()
            has_more = len(page) > limit
            records = page[:limit]
            if not records:
                raise AppException("VALIDATION_ERROR", "该批次分片游标之后没有可打包学生")

            latest = int(db.scalar(select(func.max(
                InternshipEvidencePackage.package_version,
            )).where(
                InternshipEvidencePackage.tenant_id == _tid(),
                InternshipEvidencePackage.package_type == "ARCHIVE_BATCH",
                InternshipEvidencePackage.target_id == batch_id,
            )) or 0)
            package = InternshipEvidencePackage(
                tenant_id=_tid(), package_type="ARCHIVE_BATCH", batch_id=batch_id,
                target_id=batch_id, package_version=latest + 1, status="FAILED",
                generated_by_name=core._op_name(user), generated_at=datetime.utcnow(),
                row_count=len(records), file_count=0,
            )
            db.add(package)
            try:
                db.flush()
            except IntegrityError as exc:
                raise AppException("DATA_CONFLICT", "批次归档包正在生成，请稍后重试") from exc

            zip_path, archive_zip = temporary_zip(prefix="internship-archive-batch-")
            package_records: list[dict] = []
            processed_records: list[InternshipRecord] = []
            total_files = 0
            total_bytes = 0
            used_paths: set[str] = set()
            backend = get_backend()
            try:
                for record in records:
                    manifest = db.scalar(select(ArchiveManifest).where(
                        ArchiveManifest.tenant_id == _tid(),
                        ArchiveManifest.module_code == core.MODULE_CODE,
                        ArchiveManifest.target_id == str(record.id),
                        ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
                        ArchiveManifest.is_deleted.is_(False),
                    ).order_by(ArchiveManifest.revision.desc()).with_for_update())
                    if not manifest:
                        raise AppException(
                            "DATA_CONFLICT", f"实习记录 {record.id} 缺少冻结 Manifest",
                        )
                    items = db.scalars(select(ArchiveManifestItem).where(
                        ArchiveManifestItem.tenant_id == _tid(),
                        ArchiveManifestItem.manifest_id == manifest.id,
                        ArchiveManifestItem.is_deleted.is_(False),
                    ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
                    if not items or core.manifest_digest(manifest, items) != manifest.manifest_sha256:
                        raise AppException(
                            "DATA_CONFLICT", f"实习记录 {record.id} 的 Manifest 缺失或哈希漂移",
                        )
                    if len(items) > MAX_BATCH_FILES:
                        raise AppException(
                            "VALIDATION_ERROR", f"实习记录 {record.id} 单生文件数超过批次包安全上限",
                        )
                    if package_records and total_files + len(items) > MAX_BATCH_FILES:
                        has_more = True
                        break

                    student = db.get(StudentProfile, record.student_id)
                    student_name = _safe_name(getattr(student, "real_name", ""), "学生")
                    item_payloads: list[dict] = []
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
                        if (
                            not version or not file_row
                            or version.file_object_id != file_row.id
                            or not core._file_ready(file_row)
                            or version.status not in core.READY_VERSION_STATUS
                            or file_row.sha256 != item.sha256_snapshot
                        ):
                            raise AppException(
                                "DATA_CONFLICT", f"实习记录 {record.id} 的文件版本安全状态已变化",
                            )
                        source = backend.fetch_local(file_row.file_key)
                        if not source or not source.exists():
                            raise AppException("DATA_CONFLICT", "批次归档材料字节不存在")
                        safe_file = _safe_name(item.file_name_snapshot, f"file-{file_row.id}")
                        safe_code = _safe_name(item.material_code, "MATERIAL").replace(":", "_")
                        archive_path = (
                            f"students/{record.id}_{student_name}/materials/"
                            f"{int(item.sort_no or 0):03d}_{safe_code}_{safe_file}"
                        )
                        if (
                            archive_path.startswith(("/", "\\"))
                            or ".." in Path(archive_path).parts
                            or archive_path in used_paths
                        ):
                            raise AppException("DATA_CONFLICT", "批次归档包文件路径不安全或冲突")
                        used_paths.add(archive_path)
                        digest, size = add_path(
                            archive_zip, archive_path, source,
                            expected_sha256=item.sha256_snapshot,
                            expected_size=int(item.size_snapshot or 0),
                        )
                        total_bytes += size
                        if total_bytes > MAX_BATCH_BYTES:
                            raise AppException(
                                "VALIDATION_ERROR", "批次归档分片超过 90MB 安全上限，请缩小分片人数",
                            )
                        item_payloads.append({
                            "materialCode": item.material_code,
                            "assetId": str(item.asset_id),
                            "versionId": str(item.version_id),
                            "fileObjectId": str(item.file_object_id),
                            "archivePath": archive_path,
                            "sizeBytes": size,
                            "sha256": digest,
                        })
                    total_files += len(item_payloads)
                    processed_records.append(record)
                    package_records.append({
                        "internshipId": str(record.id),
                        "studentId": str(record.student_id),
                        "studentName": student_name,
                        "manifestId": str(manifest.id),
                        "manifestRevision": int(manifest.revision or 0),
                        "manifestSha256": manifest.manifest_sha256,
                        "items": item_payloads,
                    })

                records = processed_records
                package.row_count = len(records)
                package_manifest = {
                    "schemaVersion": "INTERNSHIP_ARCHIVE_BATCH_FILE_VERSION_V1",
                    "tenantId": str(_tid()),
                    "batchId": str(batch_id),
                    "packageVersion": package.package_version,
                    "generatedAt": datetime.utcnow().isoformat() + "Z",
                    "generatedBy": core._op_name(user),
                    "scopeRowCount": scoped_total,
                    "segmentStartAfterId": after_id,
                    "segmentEndId": int(records[-1].id),
                    "rowCount": len(records),
                    "fileCount": total_files,
                    "hasMore": has_more,
                    "nextAfterId": int(records[-1].id) if has_more else None,
                    "records": package_records,
                }
                add_json(archive_zip, "manifest.json", package_manifest)
            finally:
                archive_zip.close()

            meta = store_generated_path(
                zip_path,
                f"实习批次归档_{batch_id}_{records[0].id}-{records[-1].id}_v{package.package_version}.zip",
                biz_type="ARCHIVE_BATCH_PACKAGE", biz_id=f"ARCHIVE_BATCH:{batch_id}",
                mime_type="application/zip", user=user, visibility="BIZ_SCOPED",
                security_level="SENSITIVE", db=db,
            )
            package_manifest.update({
                "packageId": str(package.id),
                "packageFileId": str(meta["fileId"]),
                "packageSha256": meta["sha256"],
                "packageSizeBytes": meta["sizeBytes"],
            })
            package.package_file_id = meta["fileId"]
            package.package_sha256 = meta["sha256"]
            package.package_size_bytes = meta["sizeBytes"]
            package.manifest_json = package_manifest
            package.included_items = [
                {"internshipId": row["internshipId"], "manifestId": row["manifestId"]}
                for row in package_records
            ]
            package.missing_items = []
            package.rule_version = "MULTI_FROZEN_FILE_VERSION_MANIFEST_V1"
            package.metric_version = "file-version-batch-streaming-v1"
            package.status = "READY"
            package.file_count = total_files
            db.add(InternshipAuditTrail(
                tenant_id=_tid(), target_id=batch_id, target_type="ARCHIVE_BATCH",
                action="VERSIONED_BATCH_PACKAGE", operator_name=core._op_name(user),
                detail_json={
                    "packageId": str(package.id), "packageVersion": package.package_version,
                    "rowCount": len(records), "fileCount": total_files,
                    "sha256": meta["sha256"], "afterId": after_id,
                    "nextAfterId": package_manifest["nextAfterId"],
                }, occurred_at=datetime.utcnow(),
            ))
            db.commit()
            return {
                "fileId": str(meta["fileId"]), "fileName": meta["fileName"],
                "sizeBytes": meta["sizeBytes"], "sha256": meta["sha256"],
                "packageId": str(package.id), "packageVersion": package.package_version,
                "batchId": str(batch_id), "rowCount": len(records),
                "fileCount": total_files, "status": "READY", "packageReady": True,
                "hasMore": has_more, "nextAfterId": package_manifest["nextAfterId"],
                "restoreCheckAvailable": True,
                "operationReceipt": {
                    "action": "ARCHIVE_BATCH_PACKAGE", "objectId": str(batch_id),
                    "packageId": str(package.id), "packageVersion": package.package_version,
                    "rowCount": len(records), "fileCount": total_files,
                    "packageSha256": meta["sha256"], "status": "COMMITTED",
                },
            }
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)


def _verify_batch_package_for_restore(package_id, user=None) -> dict:
    with session() as db:
        from app.modules.internship.services.internship_audit_service import (
            assert_high_risk_write_available,
        )

        assert_high_risk_write_available(db)
        package = db.scalar(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.id == int(package_id),
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == "ARCHIVE_BATCH",
            InternshipEvidencePackage.status == "READY",
            InternshipEvidencePackage.is_deleted.is_(False),
        ).with_for_update())
        if not package or not package.package_file_id:
            raise AppException("DATA_CONFLICT", "批次归档包不存在、未就绪或已失效")
        file_row = db.scalar(select(FileObject).where(
            FileObject.id == int(package.package_file_id),
            FileObject.tenant_id == _tid(), FileObject.is_deleted.is_(False),
        ))
        if not file_row or not core._file_ready(file_row):
            raise AppException("DATA_CONFLICT", "批次归档包文件当前不可安全读取")
        source = get_backend().fetch_local(file_row.file_key)
        if not source or not source.exists():
            raise AppException("DATA_CONFLICT", "批次归档包字节不存在")
        package_hash, package_size = sha256_path(source)
        if (
            package_hash != str(package.package_sha256 or file_row.sha256 or "")
            or package_size != int(package.package_size_bytes or file_row.size_bytes or -1)
        ):
            raise AppException("DATA_CONFLICT", "批次归档包 SHA-256 或大小与回执不一致")

        with zipfile.ZipFile(source, "r") as archive_zip:
            infos = archive_zip.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise AppException("DATA_CONFLICT", "批次归档包路径重复或缺少 manifest.json")
            manifest_info = archive_zip.getinfo("manifest.json")
            if manifest_info.file_size > 8 * 1024 * 1024:
                raise AppException("DATA_CONFLICT", "批次归档包 manifest 超过安全上限")
            embedded = json.loads(archive_zip.read(manifest_info).decode("utf-8"))
            embedded_records = embedded.get("records") or []
            if (
                embedded.get("schemaVersion") != "INTERNSHIP_ARCHIVE_BATCH_FILE_VERSION_V1"
                or str(embedded.get("batchId") or "") != str(package.target_id)
                or len(embedded_records) != int(package.row_count or 0)
                or int(embedded.get("fileCount") or -1) != int(package.file_count or 0)
            ):
                raise AppException("DATA_CONFLICT", "批次归档 manifest 身份或计数不一致")

            verified_files = 0
            seen_paths: set[str] = set()
            for embedded_record in embedded_records:
                record = core._assert_scope(
                    db, embedded_record.get("internshipId"), user, "校验批次归档恢复包",
                )
                if int(record.batch_id or 0) != int(package.target_id):
                    raise AppException("DATA_CONFLICT", "批次归档包包含跨批次学生")
                archived = db.scalar(select(InternshipArchive.id).where(
                    InternshipArchive.tenant_id == _tid(),
                    InternshipArchive.internship_id == record.id,
                    InternshipArchive.status == "ARCHIVED",
                    InternshipArchive.is_deleted.is_(False),
                ))
                if not archived:
                    raise AppException("DATA_CONFLICT", "批次归档包包含已撤销归档学生")
                manifest = db.scalar(select(ArchiveManifest).where(
                    ArchiveManifest.id == int(embedded_record.get("manifestId")),
                    ArchiveManifest.tenant_id == _tid(),
                    ArchiveManifest.target_id == str(record.id),
                    ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
                    ArchiveManifest.is_deleted.is_(False),
                ))
                if not manifest:
                    raise AppException("DATA_CONFLICT", "批次归档包引用的 Manifest 已失效")
                items = db.scalars(select(ArchiveManifestItem).where(
                    ArchiveManifestItem.tenant_id == _tid(),
                    ArchiveManifestItem.manifest_id == manifest.id,
                    ArchiveManifestItem.is_deleted.is_(False),
                ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
                if (
                    core.manifest_digest(manifest, items) != manifest.manifest_sha256
                    or str(embedded_record.get("manifestSha256") or "") != str(manifest.manifest_sha256)
                    or int(embedded_record.get("manifestRevision") or 0) != int(manifest.revision or 0)
                ):
                    raise AppException("DATA_CONFLICT", "批次归档 Manifest 哈希或版本漂移")
                frozen_by_version = {str(item.version_id): item for item in items}
                embedded_items = embedded_record.get("items") or []
                if len(embedded_items) != len(items):
                    raise AppException("DATA_CONFLICT", "批次归档恢复文件数不一致")
                for embedded_item in embedded_items:
                    frozen = frozen_by_version.get(str(embedded_item.get("versionId") or ""))
                    archive_path = str(embedded_item.get("archivePath") or "")
                    if (
                        not frozen or not archive_path or archive_path in seen_paths
                        or archive_path not in names or archive_path.startswith(("/", "\\"))
                        or ".." in Path(archive_path).parts
                    ):
                        raise AppException("DATA_CONFLICT", "批次归档恢复路径或版本不一致")
                    seen_paths.add(archive_path)
                    digest = hashlib.sha256()
                    size = 0
                    with archive_zip.open(archive_path, "r") as stream:
                        while True:
                            chunk = stream.read(1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                            size += len(chunk)
                    if (
                        digest.hexdigest() != str(frozen.sha256_snapshot or "")
                        or digest.hexdigest() != str(embedded_item.get("sha256") or "")
                        or size != int(frozen.size_snapshot or 0)
                        or size != int(embedded_item.get("sizeBytes") or 0)
                    ):
                        raise AppException("DATA_CONFLICT", "批次归档恢复文件大小或哈希失败")
                    verified_files += 1
            if len(infos) != verified_files + 1 or verified_files != int(package.file_count or 0):
                raise AppException("DATA_CONFLICT", "批次归档 ZIP 条目数与数据库计数不一致")

        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=package.target_id, target_type="ARCHIVE_BATCH",
            action="ARCHIVE_BATCH_RESTORE_VERIFIED", operator_name=core._op_name(user),
            detail_json={
                "packageId": str(package.id), "packageVersion": package.package_version,
                "rowCount": package.row_count, "fileCount": verified_files,
                "packageSha256": package_hash,
            }, occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return {
            "packageId": str(package.id), "packageVersion": package.package_version,
            "packageSha256": package_hash, "verifiedRowCount": package.row_count,
            "verifiedFileCount": verified_files, "restoreReady": True,
            "verificationOnly": True,
            "operationReceipt": {
                "action": "ARCHIVE_BATCH_RESTORE_VERIFY",
                "objectId": str(package.target_id), "packageId": str(package.id),
                "rowCount": package.row_count, "fileCount": verified_files,
                "packageSha256": package_hash, "status": "VERIFIED",
            },
        }


def verify_package_for_restore(package_id, user=None) -> dict:
    with session() as db:
        package_type = db.scalar(select(InternshipEvidencePackage.package_type).where(
            InternshipEvidencePackage.id == int(package_id),
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.is_deleted.is_(False),
        ))
    if package_type == "ARCHIVE_BATCH":
        return _verify_batch_package_for_restore(package_id, user=user)
    return _verify_single_package_for_restore(package_id, user=user)


def resolve_batch_package_download(package_id, user=None):
    with session() as db:
        package = db.scalar(select(InternshipEvidencePackage).where(
            InternshipEvidencePackage.id == int(package_id),
            InternshipEvidencePackage.tenant_id == _tid(),
            InternshipEvidencePackage.package_type == "ARCHIVE_BATCH",
            InternshipEvidencePackage.status == "READY",
            InternshipEvidencePackage.is_deleted.is_(False),
        ))
        if not package or not package.package_file_id:
            raise not_found("批次归档包不存在或不可下载")
        records = (package.manifest_json or {}).get("records") or []
        if not records or len(records) != int(package.row_count or 0):
            raise not_found("批次归档包不存在或不可下载")
        for row in records:
            core._assert_scope(db, row.get("internshipId"), user, "下载批次归档包")
        resolved = file_service.resolve_download(package.package_file_id, user=user)
        if not resolved:
            raise not_found("批次归档包不存在或不可下载")
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=package.target_id, target_type="ARCHIVE_BATCH",
            action="PACKAGE_DOWNLOAD", operator_name=core._op_name(user),
            detail_json={
                "packageId": str(package.id), "packageVersion": package.package_version,
                "sha256": package.package_sha256,
            }, occurred_at=datetime.utcnow(),
        ))
        db.commit()
        return resolved
