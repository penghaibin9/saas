"""阶段 5：真实 MySQL 学工补交、重交、公共版本、强敏感和持久化 Manifest 验收。"""
from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import delete, select

TENANT_ID = 990000000000000525
STUDENT_NO = "AFF-P5-0001"


def _cleanup() -> None:
    from app.db.session import get_sessionmaker
    from app.models import AffairsAttachment, ArchivePackage, StudentProfile
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission
    from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion

    db = get_sessionmaker()()
    try:
        manifest_ids = list(db.scalars(select(ArchiveManifest.id).where(
            ArchiveManifest.tenant_id == TENANT_ID,
        )).all())
        if manifest_ids:
            db.execute(delete(ArchiveManifestItem).where(
                ArchiveManifestItem.tenant_id == TENANT_ID,
                ArchiveManifestItem.manifest_id.in_(manifest_ids),
            ))
        for model in (
            ArchiveManifest,
            AffairsMaterialSubmission,
            AffairsMaterialRequirement,
            AffairsAttachment,
            ArchivePackage,
            FileBinding,
            FileVersion,
            FileAsset,
            FileObject,
            StudentProfile,
        ):
            db.execute(delete(model).where(model.tenant_id == TENANT_ID))
        db.commit()
    finally:
        db.close()


def _file(*, name: str, sha: str, scan: str = "CLEAN", status: str = "AVAILABLE"):
    from app.models.file import FileObject

    return FileObject(
        tenant_id=TENANT_ID,
        file_key=f"phase5/{name}",
        file_name=name,
        ext=name.rsplit(".", 1)[-1],
        mime_type="application/pdf",
        size_bytes=256,
        sha256=sha,
        biz_type="ATTACHMENT",
        biz_id="",
        visibility="PRIVATE",
        security_level="SENSITIVE",
        status=status,
        storage_backend="local",
        storage_zone="ACTIVE" if status == "AVAILABLE" else "QUARANTINE",
        upload_source="USER",
        owner_user_id=9101,
        scan_required=scan != "NOT_REQUIRED",
        scan_status=scan,
        available_at=datetime.utcnow() if status == "AVAILABLE" else None,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    from app.core.context import set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AffairsAttachment, ArchivePackage, StudentProfile
    from app.models.affairs_operations import AffairsMaterialRequirement, AffairsMaterialSubmission
    from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileVersion
    from app.modules.student_affairs.services import affairs_material_center_service as center
    from app.services.file_access_resolvers import material_requirement_resolver

    _cleanup()
    set_tenant({"tenantId": TENANT_ID, "tenantCode": "affairs-stage5"})
    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=TENANT_ID,
            student_no=STUDENT_NO,
            real_name="阶段五学生",
            current_stage="IN_SCHOOL",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()

        assert center.classify_sensitivity("AID", "FAMILY_PROOF", "家庭经济情况证明") == (
            "HIGHLY_SENSITIVE", "AID_RESTRICTED",
        )
        assert center.classify_sensitivity("MENTAL", "PSY_REPORT", "心理咨询材料") == (
            "HIGHLY_SENSITIVE", "PSY_STUDENT",
        )

        requirement = AffairsMaterialRequirement(
            tenant_id=TENANT_ID,
            student_id=int(student.id),
            biz_type="AID",
            biz_id=525,
            item_code="FAMILY_PROOF",
            item_name="家庭经济情况证明",
            requirement_reason="补充真实家庭经济证明材料",
            status="MISSING",
            return_round=1,
            review_owner_id=9201,
            sensitivity_level="HIGHLY_SENSITIVE",
            material_scope="AID_RESTRICTED",
        )
        db.add(requirement)
        db.flush()

        pending = _file(name="pending.pdf", sha="b" * 64, scan="PENDING", status="QUARANTINED")
        infected = _file(name="infected.pdf", sha="c" * 64, scan="INFECTED", status="REJECTED")
        db.add_all([pending, infected])
        db.flush()
        for unsafe in (pending, infected):
            try:
                center._require_file_ready(unsafe)
            except AppException as exc:
                assert exc.code == "DATA_CONFLICT"
            else:
                raise AssertionError("unsafe file unexpectedly passed phase 5 gate")

        student_user = {
            "userId": "9101",
            "userType": "STUDENT",
            "currentRoleCode": "STUDENT",
            "studentId": str(student.id),
            "studentNo": STUDENT_NO,
            "realName": student.real_name,
        }

        clean_v1 = _file(name="family-proof-v1.pdf", sha="a" * 64)
        db.add(clean_v1)
        db.flush()
        asset, version_v1, binding_v1 = center._adopt_file(
            db,
            requirement,
            clean_v1,
            source_channel="STUDENT_SUBMISSION",
            submit_comment="第一次补交",
            user=student_user,
        )
        attachment_v1 = AffairsAttachment(
            tenant_id=TENANT_ID,
            biz_type="MATERIAL_SUPPLEMENT",
            biz_id=int(requirement.id),
            file_id=int(clean_v1.id),
            file_name=clean_v1.file_name,
            asset_id=int(asset.id),
            file_version_id=int(version_v1.id),
            binding_id=int(binding_v1.id),
            sensitivity_level="HIGHLY_SENSITIVE",
            source_channel="MATERIAL_SUBMISSION",
        )
        db.add(attachment_v1)
        db.flush()
        submission_v1 = AffairsMaterialSubmission(
            tenant_id=TENANT_ID,
            requirement_id=int(requirement.id),
            student_id=int(student.id),
            version_no=1,
            affairs_attachment_id=int(attachment_v1.id),
            file_id=int(clean_v1.id),
            file_name=clean_v1.file_name,
            status="RETURNED",
            submitted_by="9101",
            submitted_at=datetime.utcnow(),
            reviewed_by="9201",
            reviewed_at=datetime.utcnow(),
            review_note="材料内容不完整，请重新补交",
            asset_id=int(asset.id),
            file_version_id=int(version_v1.id),
            binding_id=int(binding_v1.id),
            sensitivity_level="HIGHLY_SENSITIVE",
        )
        db.add(submission_v1)
        db.flush()
        requirement.current_submission_id = int(submission_v1.id)
        requirement.status = "RETURNED"
        version_v1.status = "REJECTED"
        binding_v1.status = "REJECTED"

        clean_v2 = _file(name="family-proof-v2.pdf", sha="d" * 64)
        db.add(clean_v2)
        db.flush()
        asset_v2, version_v2, binding_v2 = center._adopt_file(
            db,
            requirement,
            clean_v2,
            source_channel="STUDENT_SUBMISSION",
            submit_comment="退回后重新补交",
            user=student_user,
        )
        assert int(asset_v2.id) == int(asset.id)
        assert int(version_v2.version_no) == 2
        assert version_v1.is_current is False and version_v1.status == "INVALIDATED"
        assert binding_v1.is_current is False and binding_v1.status == "SUPERSEDED"

        attachment_v2 = AffairsAttachment(
            tenant_id=TENANT_ID,
            biz_type="MATERIAL_SUPPLEMENT",
            biz_id=int(requirement.id),
            file_id=int(clean_v2.id),
            file_name=clean_v2.file_name,
            asset_id=int(asset.id),
            file_version_id=int(version_v2.id),
            binding_id=int(binding_v2.id),
            sensitivity_level="HIGHLY_SENSITIVE",
            source_channel="MATERIAL_SUBMISSION",
        )
        db.add(attachment_v2)
        db.flush()
        submission_v2 = AffairsMaterialSubmission(
            tenant_id=TENANT_ID,
            requirement_id=int(requirement.id),
            student_id=int(student.id),
            version_no=2,
            affairs_attachment_id=int(attachment_v2.id),
            file_id=int(clean_v2.id),
            file_name=clean_v2.file_name,
            status="ACCEPTED",
            submitted_by="9101",
            submitted_at=datetime.utcnow(),
            reviewed_by="9201",
            reviewed_at=datetime.utcnow(),
            review_note="材料验收通过",
            supersedes_id=int(submission_v1.id),
            asset_id=int(asset.id),
            file_version_id=int(version_v2.id),
            binding_id=int(binding_v2.id),
            sensitivity_level="HIGHLY_SENSITIVE",
        )
        db.add(submission_v2)
        db.flush()
        requirement.current_submission_id = int(submission_v2.id)
        requirement.status = "ACCEPTED"
        requirement.accepted_at = datetime.utcnow()
        version_v2.status = "APPROVED"

        package_file = _file(name="student-record.xlsx", sha="e" * 64, scan="NOT_REQUIRED")
        package_file.mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        package_file.ext = "xlsx"
        db.add(package_file)
        db.flush()
        package_asset = FileAsset(
            tenant_id=TENANT_ID,
            asset_code=f"AFFAIRS_ARCHIVE_PACKAGE:{TENANT_ID}:1",
            title="阶段五学生学工档案包",
            category_code="AFFAIRS_ARCHIVE_PACKAGE",
            owner_type="ARCHIVE_PACKAGE",
            owner_id="1",
            lifecycle_status="ACTIVE",
            version_count=1,
            sensitivity_level="SENSITIVE",
        )
        db.add(package_asset)
        db.flush()
        package_version = FileVersion(
            tenant_id=TENANT_ID,
            asset_id=int(package_asset.id),
            file_object_id=int(package_file.id),
            version_no=1,
            source_channel="SYSTEM_GENERATED",
            uploader_user_id="9201",
            uploader_name_snapshot="学工管理员",
            status="APPROVED",
            is_current=True,
            submitted_at=datetime.utcnow(),
        )
        db.add(package_version)
        db.flush()
        package_asset.current_version_id = int(package_version.id)
        package = ArchivePackage(
            tenant_id=TENANT_ID,
            batch_id=525,
            student_id=int(student.id),
            missing_items_json="[]",
            package_file_id=int(package_file.id),
            package_asset_id=int(package_asset.id),
            package_version_id=int(package_version.id),
            status="SUBMITTED",
        )
        db.add(package)
        db.flush()

        provisional = center.freeze_archive_manifest(
            db,
            package,
            {"userId": "9201", "realName": "学工管理员", "currentRoleCode": "STUDENT_AFFAIRS"},
        )
        # 项目 Session 关闭 autoflush；对外 Manifest 查询发生在提交后。
        db.flush()
        manifest_model = db.get(ArchiveManifest, int(provisional["manifestId"]))
        persisted = center._manifest_row(db, manifest_model)
        db.commit()

        assert persisted["status"] == "FROZEN"
        assert persisted["itemCount"] == 2
        version_ids = {int(item["versionId"]) for item in persisted["items"]}
        assert int(version_v2.id) in version_ids
        assert int(version_v1.id) not in version_ids
        item = db.scalar(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == TENANT_ID,
            ArchiveManifestItem.manifest_id == int(package.manifest_id),
            ArchiveManifestItem.version_id == int(version_v2.id),
        ))
        assert item is not None
        assert int(item.file_object_id) == int(clean_v2.id)
        assert item.sha256_snapshot == clean_v2.sha256
        assert item.scan_result == "CLEAN"

        generic_file_admin = {
            "userId": "9301",
            "userType": "TEACHER",
            "currentRoleCode": "SYS_ADMIN",
        }
        assert center._staff_can_enumerate(db, requirement, generic_file_admin) is False
        assert material_requirement_resolver(
            db, clean_v2, [binding_v2], generic_file_admin, "meta",
        ) is False

        print("Stage 5 MySQL material resubmit/version/manifest/sensitivity acceptance passed")
    finally:
        db.close()
        _cleanup()
        set_tenant(None)


if __name__ == "__main__":
    main()
