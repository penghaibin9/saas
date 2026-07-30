"""阶段 4：真实 MySQL 资产版本、扫描状态和归档清单验收。"""
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import delete, select

TENANT_ID = 990000000000000425


def cleanup():
    from app.db.session import get_sessionmaker
    from app.models.file import (
        ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion,
    )
    db = get_sessionmaker()()
    try:
        manifest_ids = list(db.scalars(select(ArchiveManifest.id).where(
            ArchiveManifest.tenant_id == TENANT_ID)).all())
        if manifest_ids:
            db.execute(delete(ArchiveManifestItem).where(
                ArchiveManifestItem.tenant_id == TENANT_ID,
                ArchiveManifestItem.manifest_id.in_(manifest_ids)))
        db.execute(delete(ArchiveManifest).where(ArchiveManifest.tenant_id == TENANT_ID))
        db.execute(delete(FileBinding).where(FileBinding.tenant_id == TENANT_ID))
        db.execute(delete(FileVersion).where(FileVersion.tenant_id == TENANT_ID))
        db.execute(delete(FileAsset).where(FileAsset.tenant_id == TENANT_ID))
        db.execute(delete(FileObject).where(FileObject.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()


def file_row(*, name: str, digest: str, scan: str, status: str):
    from app.models.file import FileObject
    return FileObject(
        tenant_id=TENANT_ID,
        file_key=f"stage4/{name}", file_name=name, ext="pdf",
        mime_type="application/pdf", size_bytes=128, sha256=digest,
        biz_type="INTERNSHIP", biz_id="425", visibility="BIZ_SCOPED",
        security_level="SENSITIVE", status=status, storage_backend="local",
        storage_zone="ACTIVE" if status == "AVAILABLE" else "QUARANTINE",
        upload_source="USER", scan_required=scan != "NOT_REQUIRED",
        scan_status=scan, available_at=datetime.utcnow() if status == "AVAILABLE" else None,
    )


def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models.file import (
        ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileVersion,
    )
    from app.modules.internship.services import internship_material_center_service as service

    cleanup()
    set_tenant({"tenantId": TENANT_ID, "tenantCode": "internship-stage4"})
    db = get_sessionmaker()()
    try:
        clean = file_row(name="agreement-v1.pdf", digest="a" * 64, scan="CLEAN", status="AVAILABLE")
        pending = file_row(name="agreement-pending.pdf", digest="b" * 64, scan="PENDING", status="QUARANTINED")
        infected = file_row(name="agreement-infected.pdf", digest="c" * 64, scan="INFECTED", status="REJECTED")
        db.add_all([clean, pending, infected]); db.flush()

        assert service._file_ready(clean) is True
        assert service._file_ready(pending) is False
        assert service._file_ready(infected) is False
        assert service._version_state(clean, "APPROVED") == "APPROVED"
        assert service._version_state(pending, "APPROVED") == "SCANNING"
        assert service._version_state(infected, "APPROVED") == "REJECTED"

        asset = FileAsset(
            tenant_id=TENANT_ID, asset_code="INTERNSHIP:425:AGREEMENT:1",
            title="三方协议", category_code="AGREEMENT",
            owner_type="INTERNSHIP_RECORD", owner_id="425",
            lifecycle_status="ACTIVE", sensitivity_level="SENSITIVE",
        )
        db.add(asset); db.flush()
        v1 = FileVersion(
            tenant_id=TENANT_ID, asset_id=asset.id, file_object_id=clean.id,
            version_no=1, source_channel="LEGACY_ADAPTER", status="APPROVED",
            is_current=True, submitted_at=datetime.utcnow(),
        )
        db.add(v1); db.flush()
        asset.current_version_id = v1.id; asset.version_count = 1
        b1 = FileBinding(
            tenant_id=TENANT_ID, file_id=clean.id, asset_id=asset.id, version_id=v1.id,
            module_code="INTERNSHIP", biz_type="INTERNSHIP_AGREEMENT", biz_id="1",
            relation_type="MATERIAL", subject_type="STUDENT", subject_id="42",
            student_id=42, batch_id="7", version_no=1, is_current=True, status="ACTIVE",
        )
        db.add(b1); db.flush()

        clean_v2 = file_row(name="agreement-v2.pdf", digest="d" * 64, scan="CLEAN", status="AVAILABLE")
        db.add(clean_v2); db.flush()
        v1.is_current = False; v1.status = "INVALIDATED"; v1.invalidated_at = datetime.utcnow()
        b1.is_current = False; b1.status = "SUPERSEDED"; b1.invalidated_at = datetime.utcnow()
        v2 = FileVersion(
            tenant_id=TENANT_ID, asset_id=asset.id, file_object_id=clean_v2.id,
            version_no=2, source_channel="USER_RESUBMIT", status="APPROVED",
            is_current=True, submitted_at=datetime.utcnow(),
        )
        db.add(v2); db.flush()
        asset.current_version_id = v2.id; asset.version_count = 2
        b2 = FileBinding(
            tenant_id=TENANT_ID, file_id=clean_v2.id, asset_id=asset.id, version_id=v2.id,
            module_code="INTERNSHIP", biz_type="INTERNSHIP_AGREEMENT", biz_id="1",
            relation_type="MATERIAL", subject_type="STUDENT", subject_id="42",
            student_id=42, batch_id="7", version_no=2, is_current=True, status="ACTIVE",
        )
        db.add(b2); db.flush()

        manifest = ArchiveManifest(
            tenant_id=TENANT_ID, module_code="INTERNSHIP", archive_type="STUDENT_INTERNSHIP",
            target_type="INTERNSHIP_RECORD", target_id="425", revision=1,
            status="FROZEN", rule_version="acceptance-v1",
            manifest_sha256="e" * 64, frozen_at=datetime.utcnow(),
        )
        db.add(manifest); db.flush()
        db.add(ArchiveManifestItem(
            tenant_id=TENANT_ID, manifest_id=manifest.id, material_code="AGREEMENT:1",
            asset_id=asset.id, version_id=v2.id, file_object_id=clean_v2.id,
            file_name_snapshot=clean_v2.file_name, size_snapshot=clean_v2.size_bytes,
            sha256_snapshot=clean_v2.sha256, review_status="APPROVED",
            scan_result="CLEAN", sort_no=1,
        ))
        db.commit()

        current_versions = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == TENANT_ID, FileVersion.asset_id == asset.id,
            FileVersion.is_current.is_(True))).all()
        assert len(current_versions) == 1 and current_versions[0].id == v2.id
        item = db.scalar(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == TENANT_ID,
            ArchiveManifestItem.manifest_id == manifest.id))
        assert item.version_id == v2.id
        assert item.file_object_id == clean_v2.id
        assert item.sha256_snapshot == clean_v2.sha256
        assert item.scan_result == "CLEAN"
        assert item.version_id != v1.id
        print("Stage 4 MySQL material/version/manifest acceptance passed")
    finally:
        db.close()
        cleanup()
        set_tenant(None)


if __name__ == "__main__":
    main()
