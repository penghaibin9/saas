"""Standalone fixed-business file authorization; uploader identity never overrides it."""
from __future__ import annotations

from app.services.message_identity import resolve_message_user_id
from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission
from app.models import InternshipArchive, InternshipEvidencePackage
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileObject, FileVersion
from app.services.file_access_service import register_file_resolver

ARCHIVE_FILE_TYPES = {"ARCHIVE_PACKAGE", "ARCHIVE_BATCH_PACKAGE"}


def _owner_allows(file_obj, user: dict) -> bool:
    owner = str(file_obj.owner_user_id or file_obj.created_by or "").strip()
    if not owner:
        return False
    actor = resolve_message_user_id(user or {})
    values = {str(actor) if actor else "", str((user or {}).get("userId") or "").replace("db-", "")}
    return owner in {item for item in values if item}


def _frozen_members_allow(db, package, payload, user, tenant_id):
    from app.modules.internship.services import internship_material_center_service as core
    from app.modules.internship.services.internship_scope import apply_internship_record_scope
    from app.models import InternshipRecord
    batch = package.package_type == "ARCHIVE_BATCH"
    records = payload.get("records") if batch else [payload]
    if not isinstance(records, list) or not records or len(records) != int(package.row_count or 0):
        return False
    if (batch and (len(records) > 20 or int(package.target_id) != int(package.batch_id or 0)
                   or str(payload.get("batchId")) != str(package.target_id)
                   or int(payload.get("rowCount") or 0) != len(records)
                   or int(payload.get("fileCount") or 0) != int(package.file_count or 0))):
        return False
    if not batch and int(package.row_count or 0) != 1:
        return False
    seen_records, count = set(), 0
    for entry in records:
        record = core._assert_scope(db, entry.get("internshipId"), user, "下载归档材料")
        scoped = apply_internship_record_scope(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == tenant_id, InternshipRecord.id == record.id,
            InternshipRecord.is_deleted.is_(False)), user)
        if not db.scalar(scoped):
            return False
        if (record.id in seen_records or int(record.batch_id or 0) != int(package.batch_id or 0)
                or str(entry.get("studentId")) != str(record.student_id)
                or (not batch and record.id != package.target_id)):
            return False
        seen_records.add(record.id)
        archived = db.scalar(select(InternshipArchive).where(
            InternshipArchive.tenant_id == tenant_id,
            InternshipArchive.internship_id == record.id,
            InternshipArchive.student_id == record.student_id,
            InternshipArchive.status == "ARCHIVED",
            InternshipArchive.is_deleted.is_(False),
        ))
        manifest = db.scalar(select(ArchiveManifest).where(
            ArchiveManifest.id == int(entry.get("manifestId") or 0),
            ArchiveManifest.tenant_id == tenant_id,
            ArchiveManifest.module_code == core.MODULE_CODE,
            ArchiveManifest.archive_type == core.ARCHIVE_TYPE,
            ArchiveManifest.target_type == core.TARGET_TYPE,
            ArchiveManifest.target_id == str(record.id),
            ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
            ArchiveManifest.is_deleted.is_(False),
        ))
        if (not archived or not manifest or int(entry.get("manifestRevision") or 0) != manifest.revision
                or entry.get("manifestSha256") != manifest.manifest_sha256):
            return False
        frozen = list(db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == tenant_id,
            ArchiveManifestItem.manifest_id == manifest.id,
            ArchiveManifestItem.is_deleted.is_(False),
        ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all())
        entries = entry.get("items")
        if (not frozen or not isinstance(entries, list) or len(entries) != len(frozen)
                or core.manifest_digest(manifest, frozen) != manifest.manifest_sha256):
            return False
        expected = {(str(x.version_id), str(x.asset_id), str(x.file_object_id), x.sha256_snapshot,
                     int(x.size_snapshot or 0), x.material_code) for x in frozen}
        actual = {(str(x.get("versionId")), str(x.get("assetId")), str(x.get("fileObjectId")),
                   x.get("sha256"), int(x.get("sizeBytes") or 0), x.get("materialCode")) for x in entries}
        if len(actual) != len(entries) or actual != expected:
            return False
        versions = {v.id: (v, f) for v, f in db.execute(select(FileVersion, FileObject).join(
            FileObject, FileObject.id == FileVersion.file_object_id,
        ).where(
            FileVersion.tenant_id == tenant_id, FileObject.tenant_id == tenant_id,
            FileVersion.id.in_([x.version_id for x in frozen]),
            FileVersion.is_deleted.is_(False), FileObject.is_deleted.is_(False),
        )).all()}
        for item in frozen:
            pair = versions.get(item.version_id)
            if not pair:
                return False
            version, source = pair
            if (version.asset_id != item.asset_id or version.file_object_id != item.file_object_id
                    or version.status not in core.READY_VERSION_STATUS or not core._file_ready(source)
                    or source.sha256 != item.sha256_snapshot
                    or int(source.size_bytes or 0) != int(item.size_snapshot or 0)):
                return False
        count += len(entries)
    if count != int(package.file_count or 0):
        return False
    if batch:
        return package.included_items == [
            {"internshipId": x["internshipId"], "manifestId": x["manifestId"]} for x in records]
    return package.included_items == payload.get("items")


@register_file_resolver("ARCHIVE_PACKAGE", "ARCHIVE_BATCH_PACKAGE")
def authorize_archive_package(db, file_obj, bindings, user, action):
    """Fixed frozen members authorize packages before any uploader fallback."""
    if db is None or action not in {"meta", "download", "preview"} or not has_permission(user, "internship.archive.package"):
        return False
    tenant_id = int(current_tenant_id() or 0)
    packages = list(db.scalars(select(InternshipEvidencePackage).where(
        InternshipEvidencePackage.tenant_id == tenant_id,
        InternshipEvidencePackage.package_file_id == str(file_obj.id),
        InternshipEvidencePackage.package_type.in_(("ARCHIVE", "ARCHIVE_BATCH")),
        InternshipEvidencePackage.is_deleted.is_(False),
    ).limit(2)).all())
    if len(packages) != 1:
        return False
    package = packages[0]
    batch = package.package_type == "ARCHIVE_BATCH"
    biz_type = "ARCHIVE_BATCH_PACKAGE" if batch else "ARCHIVE_PACKAGE"
    biz_id = f"{package.package_type}:{package.target_id}"
    if (package.status != "READY" or package.invalidated_at or package.missing_items
            or file_obj.biz_type != biz_type or str(file_obj.biz_id) != biz_id
            or file_obj.sha256 != package.package_sha256
            or int(file_obj.size_bytes or 0) != int(package.package_size_bytes or 0)
            or not any(b.tenant_id == tenant_id and b.file_id == file_obj.id and not b.is_deleted
                       and b.status == "ACTIVE" and b.is_current and b.biz_type == biz_type
                       and str(b.biz_id) == biz_id for b in bindings)):
        return False
    payload = package.manifest_json
    schema = "INTERNSHIP_ARCHIVE_BATCH_FILE_VERSION_V1" if batch else "INTERNSHIP_ARCHIVE_PACKAGE_FILE_VERSION_V2"
    if (not isinstance(payload, dict) or payload.get("schemaVersion") != schema
            or str(payload.get("tenantId")) != str(tenant_id)
            or str(payload.get("packageFileId")) != str(file_obj.id)
            or payload.get("packageSha256") != package.package_sha256
            or int(payload.get("packageSizeBytes") or 0) != int(package.package_size_bytes or 0)
            or (batch and (str(payload.get("packageId")) != str(package.id)
                           or int(payload.get("packageVersion") or 0) != package.package_version))):
        return False
    # Bind scope metadata to the actual immutable ZIP manifest. Editing stored
    # records/included_items together must not splice a different member list.
    import json
    import zipfile
    from app.services.storage import get_backend
    path = get_backend().fetch_local(file_obj.file_key)
    if path is None or not path.is_file():
        return False
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) != int(package.file_count or 0) + 1:
            return False
        info = archive.getinfo("manifest.json")
        if info.file_size > (8 if batch else 2) * 1024 * 1024:
            return False
        embedded = json.loads(archive.read(info).decode("utf-8"))
    envelope = {"packageId", "packageFileId", "packageSha256", "packageSizeBytes"}
    if embedded != {k: v for k, v in payload.items() if k not in envelope}:
        return False
    return _frozen_members_allow(db, package, payload, user, tenant_id)


def require_archive_package_file(db, package, user):
    from app.services.file_access_service import _load, authorize_file_object
    file_obj, bindings = _load(db, int(current_tenant_id() or 0), int(package.package_file_id or 0))
    if (not file_obj or file_obj.biz_type not in ARCHIVE_FILE_TYPES
            or not authorize_file_object(file_obj, bindings, user or {}, "download", db=db)):
        raise not_found("归档包不存在或不可下载")
    return file_obj


def resolve_authorized_archive_download(db, package, user):
    """Same authority for dedicated package routes; stream-check bytes too."""
    from app.services.storage import get_backend
    from app.services.streaming_archive_service import sha256_path
    file_obj = require_archive_package_file(db, package, user)
    path = get_backend().fetch_local(file_obj.file_key)
    digest, size = sha256_path(path)
    if digest != package.package_sha256 or size != int(package.package_size_bytes or 0):
        raise AppException("FILE_INTEGRITY_ERROR", "归档包完整性校验失败，请联系学校管理员", http_status=409)
    return path, file_obj.file_name
