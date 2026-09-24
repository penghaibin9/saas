"""Domain-neutral frozen package builder.

Source-boundary invariant: this module may query only File Center manifest,
version and object projections. It must never import live business models.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileBinding, FileObject, FileVersion
from app.modules.platform_integrity.contracts import (
    FrozenPackageResult,
    PackageArtifactRef,
    frozen_manifest_artifact_ref,
)
from app.modules.platform_integrity.deterministic_package import (
    ArchiveEntry,
    STANDARD_PROFILE_V1,
    safe_segment,
    write_standard_v1,
)
from app.modules.platform_integrity.manifest_digest import (
    PLATFORM_BUSINESS_SNAPSHOT,
    PLATFORM_MANIFEST_DIGEST_V1,
    canonical_manifest_payload,
    is_platform_frozen_manifest,
    ordered_items,
    platform_manifest_digest,
)
from app.services.db_service import _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES
from app.services.generated_file_path_service import store_generated_path
from app.services.storage import get_backend

PACKAGE_BIZ_TYPE = "FROZEN_EVIDENCE_PACKAGE"
MAX_PACKAGE_ITEMS = 1000
PACKAGEABLE_MANIFEST_STATUSES = frozenset({"FROZEN", "PACKAGED"})


def frozen_package_artifact_biz_id(manifest: ArchiveManifest, profile_code: str) -> str:
    raw = f"m{manifest.id}:r{manifest.revision}:{manifest.manifest_sha256}:{profile_code}"
    if len(raw) <= 64:
        return raw
    return f"m{manifest.id}:r{manifest.revision}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


def is_package_artifact_ready(file_obj: FileObject | None) -> bool:
    return bool(
        file_obj
        and not bool(file_obj.is_deleted)
        and is_downloadable_status(file_obj.status)
        and str(file_obj.scan_status or "").upper() in READY_SCAN_STATES
    )


def _artifact_ref(
    file_obj: FileObject,
    manifest: ArchiveManifest,
    tenant_id: int,
    profile_code: str,
) -> PackageArtifactRef:
    return frozen_manifest_artifact_ref(
        tenant_id=tenant_id,
        manifest=manifest,
        file_object=file_obj,
        profile_code=profile_code,
        resolver_code=PACKAGE_BIZ_TYPE,
    )


def _validate_source(path: Path, item: ArchiveManifestItem, file_obj: FileObject) -> None:
    if not path.is_file():
        raise AppException("PACKAGED_FILE_MISSING", f"冻结材料文件不存在：{item.material_code}", http_status=409)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    expected_size = int(item.size_snapshot or 0)
    expected_sha = str(item.sha256_snapshot or "").lower()
    if size != expected_size or digest.hexdigest() != expected_sha:
        raise AppException("FROZEN_MANIFEST_ITEM_DRIFT", f"冻结材料字节与清单不一致：{item.material_code}", http_status=409)
    if int(file_obj.size_bytes or 0) != expected_size or str(file_obj.sha256 or "").lower() != expected_sha:
        raise AppException("FROZEN_MANIFEST_ITEM_DRIFT", f"冻结材料投影与清单不一致：{item.material_code}", http_status=409)


def _validate_artifact(path: Path, file_obj: FileObject) -> None:
    if not path.is_file():
        raise AppException("PACKAGED_FILE_MISSING", "冻结证据包物理文件不存在", http_status=409)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    if size != int(file_obj.size_bytes or 0) or digest.hexdigest() != str(file_obj.sha256 or "").lower():
        raise AppException("PACKAGE_ARTIFACT_MISMATCH", "冻结证据包字节与 FileObject 投影不一致", http_status=409)


def _entry_path(item: ArchiveManifestItem) -> str:
    filename = safe_segment(item.file_name_snapshot, fallback=f"file-{item.file_object_id}")
    if str(item.material_code).upper() == PLATFORM_BUSINESS_SNAPSHOT:
        return "metadata/platform_business_snapshot.json"
    code = safe_segment(item.material_code, fallback="material")
    return f"evidence/{int(item.sort_no or 0):04d}_{code}/{filename}"


def _existing_artifact(db, *, tenant_id: int, biz_id: str) -> FileObject | None:
    return db.scalars(select(FileObject).where(
        FileObject.tenant_id == tenant_id,
        FileObject.biz_type == PACKAGE_BIZ_TYPE,
        FileObject.biz_id == biz_id,
        FileObject.is_deleted.is_(False),
    ).order_by(FileObject.id.desc()).limit(1)).first()


def _build_frozen_package(
    *,
    manifest_id: int,
    profile_code: str,
    expected_revision: int | None = None,
    expected_manifest_sha256: str | None = None,
) -> FrozenPackageResult:
    profile = str(profile_code or "").strip().upper()
    if profile != STANDARD_PROFILE_V1:
        raise AppException("PACKAGE_PROFILE_UNSUPPORTED", "仅支持 STANDARD_V1 冻结包规范", http_status=422)
    tenant_id = _tid()
    with session() as db:
        manifest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == tenant_id,
            ArchiveManifest.id == int(manifest_id),
            ArchiveManifest.is_deleted.is_(False),
        ).with_for_update()).first()
        if not manifest:
            raise not_found("冻结清单不存在")
        if str(manifest.status or "").upper() not in PACKAGEABLE_MANIFEST_STATUSES:
            raise AppException("FROZEN_MANIFEST_STATE_INVALID", "当前清单状态不允许生成冻结证据包", http_status=409)
        if expected_revision is not None and int(manifest.revision or 1) != int(expected_revision):
            raise AppException("FILE_JOB_SOURCE_CHANGED", "冻结包任务引用的清单版本已变化", http_status=409)
        if expected_manifest_sha256 is not None and (
            str(manifest.manifest_sha256 or "").lower() != str(expected_manifest_sha256).lower()
        ):
            raise AppException("FILE_JOB_SOURCE_CHANGED", "冻结包任务引用的清单摘要已变化", http_status=409)
        items = list(db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == tenant_id,
            ArchiveManifestItem.manifest_id == int(manifest.id),
            ArchiveManifestItem.is_deleted.is_(False),
        ).limit(MAX_PACKAGE_ITEMS + 1)).all())
        if len(items) > MAX_PACKAGE_ITEMS:
            raise AppException(
                "PACKAGE_ITEM_LIMIT_EXCEEDED",
                f"冻结清单材料数超过安全上限 {MAX_PACKAGE_ITEMS}",
                http_status=409,
            )
        snapshot_items = [
            item for item in items
            if str(item.material_code or "").upper() == PLATFORM_BUSINESS_SNAPSHOT
        ]
        if not snapshot_items:
            raise AppException("LEGACY_MANIFEST_UNSUPPORTED", "历史清单未包含平台业务快照，保持原有打包语义", http_status=409)
        if len(snapshot_items) != 1:
            raise AppException("FROZEN_SNAPSHOT_CARDINALITY_INVALID", "冻结清单必须且只能包含一个平台业务快照", http_status=409)
        if not is_platform_frozen_manifest(items):
            raise AppException("LEGACY_MANIFEST_UNSUPPORTED", "历史清单未包含平台业务快照，保持原有打包语义", http_status=409)
        digest = platform_manifest_digest(manifest, items)
        if digest != str(manifest.manifest_sha256 or "").lower():
            raise AppException("FROZEN_MANIFEST_ITEM_DRIFT", "冻结清单摘要校验失败", http_status=409)

        biz_id = frozen_package_artifact_biz_id(manifest, profile)
        existing = _existing_artifact(db, tenant_id=tenant_id, biz_id=biz_id)
        backend = get_backend()
        if existing:
            if not is_package_artifact_ready(existing):
                raise AppException("PACKAGE_ARTIFACT_UNAVAILABLE", "冻结证据包已失效或尚未通过安全检查", http_status=409)
            path = backend.fetch_local(str(existing.object_key or existing.file_key))
            if not path:
                raise AppException("PACKAGED_FILE_MISSING", "冻结证据包物理文件不存在", http_status=409)
            _validate_artifact(path, existing)
            return FrozenPackageResult(
                manifest_id=int(manifest.id),
                revision=int(manifest.revision or 1),
                manifest_sha256=digest,
                digest_schema_version=PLATFORM_MANIFEST_DIGEST_V1,
                artifact=_artifact_ref(existing, manifest, tenant_id, profile),
                reused=True,
            )

        version_ids = {int(item.version_id) for item in items}
        object_ids = {int(item.file_object_id) for item in items}
        versions = {int(row.id): row for row in db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == tenant_id,
            FileVersion.id.in_(version_ids),
            FileVersion.is_deleted.is_(False),
        )).all()}
        objects = {int(row.id): row for row in db.scalars(select(FileObject).where(
            FileObject.tenant_id == tenant_id,
            FileObject.id.in_(object_ids),
            FileObject.is_deleted.is_(False),
        )).all()}
        entries: list[ArchiveEntry] = []
        for item in ordered_items(items):
            version = versions.get(int(item.version_id))
            file_obj = objects.get(int(item.file_object_id))
            if not version or not file_obj or int(version.file_object_id) != int(item.file_object_id):
                raise AppException("PACKAGE_SOURCE_VERSION_MISMATCH", f"冻结材料版本链断裂：{item.material_code}", http_status=409)
            source = backend.fetch_local(str(file_obj.object_key or file_obj.file_key))
            if source is None:
                raise AppException("PACKAGED_FILE_MISSING", f"冻结材料文件不存在：{item.material_code}", http_status=409)
            _validate_source(source, item, file_obj)
            entries.append(ArchiveEntry(
                path=_entry_path(item),
                source_path=source,
                sha256=str(item.sha256_snapshot or "").lower(),
                size_bytes=int(item.size_snapshot or 0),
            ))

        package_manifest = canonical_manifest_payload(manifest, items)
        package_manifest.update({
            "packageProfile": STANDARD_PROFILE_V1,
            "manifestSha256": digest,
        })
        temp_path: Path | None = None
        stored_key: str | None = None
        committed = False
        try:
            with tempfile.NamedTemporaryFile(prefix="plat-a-frozen-", suffix=".zip", delete=False) as handle:
                temp_path = Path(handle.name)
            try:
                expected_size, expected_sha = write_standard_v1(
                    temp_path,
                    manifest_payload=package_manifest,
                    entries=entries,
                )
            except ValueError as exc:
                raise AppException("PACKAGE_ENTRY_PATH_CONFLICT", "冻结证据包条目路径冲突", http_status=409) from exc
            meta = store_generated_path(
                temp_path,
                f"frozen-manifest-{manifest.id}-r{int(manifest.revision or 1)}.zip",
                PACKAGE_BIZ_TYPE,
                "application/zip",
                biz_id=biz_id,
                visibility="BIZ_SCOPED",
                security_level="PERSONAL",
                db=db,
            )
            stored_key = str(meta.get("objectKey") or meta.get("fileKey") or "") or None
            artifact = db.scalars(select(FileObject).where(
                FileObject.tenant_id == tenant_id,
                FileObject.id == int(meta["fileId"]),
                FileObject.is_deleted.is_(False),
            )).one()
            if int(artifact.size_bytes or 0) != expected_size or str(artifact.sha256 or "").lower() != expected_sha:
                raise AppException("PACKAGE_ARTIFACT_MISMATCH", "冻结证据包登记结果与生成字节不一致", http_status=500)
            snapshot_item = snapshot_items[0]
            source_binding = db.scalars(select(FileBinding).where(
                FileBinding.tenant_id == tenant_id,
                FileBinding.file_id == int(snapshot_item.file_object_id),
                FileBinding.is_deleted.is_(False),
            ).order_by(FileBinding.id).limit(1)).first()
            artifact_binding = db.scalars(select(FileBinding).where(
                FileBinding.tenant_id == tenant_id,
                FileBinding.file_id == int(artifact.id),
                FileBinding.is_deleted.is_(False),
            ).order_by(FileBinding.id).limit(1)).first()
            if source_binding and artifact_binding:
                artifact_binding.relation_type = "FROZEN_PACKAGE"
                artifact_binding.subject_type = source_binding.subject_type
                artifact_binding.subject_id = source_binding.subject_id
                artifact_binding.batch_id = source_binding.batch_id
                artifact_binding.module_code = source_binding.module_code
                artifact_binding.student_id = source_binding.student_id
                artifact_binding.college_id = source_binding.college_id
                artifact_binding.class_id = source_binding.class_id
                artifact_binding.data_scope_snapshot_json = dict(source_binding.data_scope_snapshot_json or {})
            db.commit()
            committed = True
            return FrozenPackageResult(
                manifest_id=int(manifest.id),
                revision=int(manifest.revision or 1),
                manifest_sha256=digest,
                digest_schema_version=PLATFORM_MANIFEST_DIGEST_V1,
                artifact=_artifact_ref(artifact, manifest, tenant_id, profile),
                reused=False,
            )
        except Exception:
            db.rollback()
            if stored_key and not committed:
                try:
                    backend.delete(stored_key)
                except Exception:
                    pass
            raise
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def build_frozen_package(*, manifest_id: int, profile_code: str) -> FrozenPackageResult:
    """Build or return the immutable File Center artifact for one frozen manifest."""
    return _build_frozen_package(manifest_id=manifest_id, profile_code=profile_code)


def build_frozen_package_for_job(
    *,
    manifest_id: int,
    profile_code: str,
    expected_revision: int,
    expected_manifest_sha256: str,
) -> FrozenPackageResult:
    """Build only when the row-locked manifest still matches the queued source identity."""
    return _build_frozen_package(
        manifest_id=manifest_id,
        profile_code=profile_code,
        expected_revision=expected_revision,
        expected_manifest_sha256=expected_manifest_sha256,
    )


__all__ = [
    "PACKAGE_BIZ_TYPE",
    "PACKAGEABLE_MANIFEST_STATUSES",
    "build_frozen_package",
    "build_frozen_package_for_job",
    "frozen_package_artifact_biz_id",
    "is_package_artifact_ready",
]
