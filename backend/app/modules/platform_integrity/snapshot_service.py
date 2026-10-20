"""Domain-neutral immutable business snapshot writer.

Domain adapters prepare the payload. This module only owns File Center objects,
assets and versions, so it never reaches back into live domain tables.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models.file import FileAsset, FileBinding, FileObject, FileVersion
from app.modules.platform_integrity.contracts import SnapshotAssetRef
from app.modules.platform_integrity.manifest_digest import (
    PLATFORM_BUSINESS_SNAPSHOT,
    canonical_json_bytes,
)
from app.services.db_service import _tid
from app.services.file_service import store_bytes


def _asset_code(module_code: str, target_type: str, target_id: str, revision: int) -> str:
    raw = f"PLATFORM_SNAPSHOT:{module_code}:{target_type}:{target_id}:r{revision}"
    if len(raw) <= 180:
        return raw
    suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"PLATFORM_SNAPSHOT:{module_code[:60]}:{suffix}"


def _biz_id(module_code: str, target_id: str, revision: int) -> str:
    raw = f"{module_code}:{target_id}:r{revision}"
    if len(raw) <= 64:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _reference(file_asset: FileAsset, version: FileVersion, file_obj: FileObject) -> SnapshotAssetRef:
    return SnapshotAssetRef(
        asset_id=int(file_asset.id),
        version_id=int(version.id),
        file_object_id=int(file_obj.id),
        file_name=str(file_obj.file_name),
        size_bytes=int(file_obj.size_bytes or 0),
        sha256=str(file_obj.sha256 or ""),
    )


def create_business_snapshot(
    db,
    *,
    module_code: str,
    target_type: str,
    target_id: str,
    revision: int,
    payload: dict,
    user: dict | None = None,
    sensitivity_level: str = "PERSONAL",
    subject_type: str = "BUSINESS_OBJECT",
    subject_id: str | None = None,
    batch_id: str | None = None,
    student_id: int | None = None,
    college_id: int | None = None,
    class_id: int | None = None,
) -> SnapshotAssetRef:
    tenant_id = _tid()
    body = canonical_json_bytes(payload) + b"\n"
    expected_sha = hashlib.sha256(body).hexdigest()
    asset_code = _asset_code(module_code, target_type, str(target_id), int(revision))
    existing_asset = db.scalars(select(FileAsset).where(
        FileAsset.tenant_id == tenant_id,
        FileAsset.asset_code == asset_code,
        FileAsset.is_deleted.is_(False),
    ).with_for_update()).first()
    if existing_asset:
        version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == tenant_id,
            FileVersion.id == int(existing_asset.current_version_id or 0),
            FileVersion.asset_id == int(existing_asset.id),
            FileVersion.is_deleted.is_(False),
        )).first()
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == tenant_id,
            FileObject.id == int(version.file_object_id if version else 0),
            FileObject.is_deleted.is_(False),
        )).first()
        if not version or not file_obj or str(file_obj.sha256 or "").lower() != expected_sha:
            raise AppException(
                "FROZEN_SNAPSHOT_CONFLICT",
                "同一归档修订已存在不同的业务快照，拒绝覆盖",
                http_status=409,
            )
        return _reference(existing_asset, version, file_obj)

    asset = FileAsset(
        tenant_id=tenant_id,
        asset_code=asset_code,
        title=f"{module_code} {target_type} {target_id} 冻结业务快照",
        category_code=PLATFORM_BUSINESS_SNAPSHOT,
        owner_type=str(target_type or "BUSINESS_OBJECT")[:30],
        owner_id=str(target_id)[:64],
        lifecycle_status="LOCKED",
        version_count=0,
        sensitivity_level=str(sensitivity_level or "PERSONAL")[:30],
    )
    db.add(asset)
    db.flush()
    biz_id = _biz_id(module_code, str(target_id), int(revision))
    meta = store_bytes(
        body,
        # File Center intentionally does not admit JSON as an upload extension.
        # Persist the canonical JSON bytes as an internal text object; package
        # assembly gives the immutable entry its public `.json` name.
        f"platform-business-snapshot-r{int(revision)}.txt",
        PLATFORM_BUSINESS_SNAPSHOT,
        "text/plain",
        biz_id=biz_id,
        user=user or {},
        visibility="BIZ_SCOPED",
        security_level=str(sensitivity_level or "PERSONAL"),
        db=db,
    )
    file_obj = db.scalars(select(FileObject).where(
        FileObject.tenant_id == tenant_id,
        FileObject.id == int(meta["fileId"]),
        FileObject.is_deleted.is_(False),
    )).one()
    version = FileVersion(
        tenant_id=tenant_id,
        asset_id=int(asset.id),
        file_object_id=int(file_obj.id),
        version_no=1,
        source_channel="PLATFORM_FROZEN_SNAPSHOT",
        uploader_user_id=str((user or {}).get("userId") or "") or None,
        uploader_name_snapshot=str((user or {}).get("realName") or (user or {}).get("name") or "系统")[:100],
        status="ARCHIVED",
        is_current=True,
        submitted_at=datetime.utcnow(),
    )
    db.add(version)
    db.flush()
    asset.current_version_id = int(version.id)
    asset.version_count = 1

    bindings = list(db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == tenant_id,
        FileBinding.file_id == int(file_obj.id),
        FileBinding.is_deleted.is_(False),
    )).all())
    for binding in bindings:
        binding.relation_type = "FROZEN_SNAPSHOT"
        binding.subject_type = str(subject_type or "BUSINESS_OBJECT").upper()[:30]
        binding.subject_id = str(subject_id)[:64] if subject_id not in (None, "") else None
        binding.batch_id = str(batch_id)[:64] if batch_id not in (None, "") else None
        binding.asset_id = int(asset.id)
        binding.version_id = int(version.id)
        binding.module_code = str(module_code)[:64]
        binding.student_id = int(student_id) if student_id else None
        binding.college_id = int(college_id) if college_id else None
        binding.class_id = int(class_id) if class_id else None
        binding.data_scope_snapshot_json = {
            "tenantId": str(tenant_id),
            "studentId": str(student_id or ""),
            "collegeId": str(college_id or ""),
            "classId": str(class_id or ""),
            "batchId": str(batch_id or ""),
        }
    return _reference(asset, version, file_obj)


__all__ = ["create_business_snapshot"]
