"""阶段 6：真实 MySQL 毕业设计公共版本、审核、Manifest、ZIP/Excel 验收。"""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from datetime import datetime

from sqlalchemy import delete, select

TENANT_ID = 990000000000000626
STUDENT_NO = "GD-P6-0001"
LEGACY_STUDENT_NO = "GD-P6-LEGACY"


def _cleanup() -> None:
    from app.db.session import get_sessionmaker
    from app.models import (
        GraduationArchiveRecord,
        GraduationAuditTrail,
        GraduationBatch,
        GraduationFinal,
        GraduationMidterm,
        GraduationPlagiarismCheck,
        GraduationProposal,
        GraduationStudent,
        GraduationTaskBook,
        GraduationTemplate,
        StudentProfile,
        UnifiedTodo,
    )
    from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion
    from app.models.graduation_material import GraduationMaterialItem, GraduationMaterialRule

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
        rule_ids = list(db.scalars(select(GraduationMaterialRule.id).where(
            GraduationMaterialRule.tenant_id == TENANT_ID,
        )).all())
        if rule_ids:
            db.execute(delete(GraduationMaterialItem).where(
                GraduationMaterialItem.tenant_id == TENANT_ID,
                GraduationMaterialItem.rule_id.in_(rule_ids),
            ))
        for model in (
            ArchiveManifest,
            GraduationPlagiarismCheck,
            GraduationFinal,
            GraduationProposal,
            GraduationArchiveRecord,
            GraduationMidterm,
            GraduationTaskBook,
            GraduationAuditTrail,
            UnifiedTodo,
            GraduationTemplate,
            GraduationStudent,
            GraduationBatch,
            GraduationMaterialRule,
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


def _real_file(db, *, name: str, body: bytes, owner: int = 6101):
    from app.models.file import FileObject
    from app.services.storage import get_backend

    key = f"phase6/{TENANT_ID}/{name}"
    backend = get_backend()
    target = backend.staging_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    backend.persist(key, target)
    row = FileObject(
        tenant_id=TENANT_ID,
        file_key=key,
        file_name=name,
        ext=name.rsplit(".", 1)[-1].lower(),
        mime_type="application/pdf",
        size_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        biz_type="ATTACHMENT",
        biz_id="",
        visibility="PRIVATE",
        security_level="SENSITIVE",
        status="AVAILABLE",
        storage_backend="local",
        storage_zone="ACTIVE",
        upload_source="USER",
        owner_user_id=owner,
        created_by=owner,
        scan_required=True,
        scan_status="CLEAN",
        available_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def _zip_payload(file_id: int):
    from app.db.session import get_sessionmaker
    from app.models.file import FileObject
    from app.services.storage import get_backend

    db = get_sessionmaker()()
    try:
        row = db.get(FileObject, int(file_id))
        assert row is not None
        path = get_backend().fetch_local(row.file_key)
        assert path is not None and path.exists()
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row.sha256
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            return row, archive, names, manifest, {name: archive.read(name) for name in names}
    finally:
        db.close()


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import (
        GraduationArchiveRecord,
        GraduationBatch,
        GraduationFinal,
        GraduationMidterm,
        GraduationPlagiarismCheck,
        GraduationProposal,
        GraduationStudent,
        GraduationTaskBook,
        GraduationTemplate,
        StudentProfile,
    )
    from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileVersion
    from app.modules.graduation.services import graduation_material_center_service as center
    from app.services.storage import get_backend

    _cleanup()
    set_tenant({"tenantId": TENANT_ID, "tenantCode": "graduation-stage6"})
    student_user = {
        "userId": "6101", "userType": "STUDENT", "currentRoleCode": "STUDENT",
        "studentNo": STUDENT_NO, "realName": "阶段六学生",
    }
    teacher_user = {
        "userId": "6201", "userType": "TEACHER", "currentRoleCode": "GRADUATION_ADMIN",
        "realName": "阶段六毕设管理员", "permissions": ["*"],
    }
    db = get_sessionmaker()()
    try:
        profile = StudentProfile(
            tenant_id=TENANT_ID, student_no=STUDENT_NO, real_name="阶段六学生",
            current_stage="IN_SCHOOL", student_status="NORMAL", status="ACTIVE",
        )
        legacy_profile = StudentProfile(
            tenant_id=TENANT_ID, student_no=LEGACY_STUDENT_NO, real_name="旧材料学生",
            current_stage="IN_SCHOOL", student_status="NORMAL", status="ACTIVE",
        )
        db.add_all([profile, legacy_profile])
        db.flush()
        student_user["studentId"] = str(profile.id)

        batch = GraduationBatch(
            tenant_id=TENANT_ID, batch_name="阶段六毕业设计批次", batch_no="GD-P6-2026",
            academic_year="2025-2026", grade_year="2026届", status="RUNNING",
        )
        db.add(batch)
        db.flush()
        student_user["graduationBatchId"] = str(batch.id)
        student = GraduationStudent(
            tenant_id=TENANT_ID, batch_id=int(batch.id), topic_id=66001,
            student_id=int(profile.id), student_no=STUDENT_NO, name="阶段六学生",
            class_id="C-P6", class_name="软件技术1班", college_id="COL-P6", major_id="MAJ-P6",
            topic_title="公共文件版本驱动的毕业设计", advisor_name="阶段六导师",
            stage="TASKBOOK_CONFIRM", eligibility_status="QUALIFIED", record_status="ACTIVE",
        )
        legacy_student = GraduationStudent(
            tenant_id=TENANT_ID, batch_id=int(batch.id), topic_id=66002,
            student_id=int(legacy_profile.id), student_no=LEGACY_STUDENT_NO, name="旧材料学生",
            class_id="C-P6", class_name="软件技术1班", college_id="COL-P6", major_id="MAJ-P6",
            topic_title="旧材料回填", advisor_name="阶段六导师",
            stage="TASKBOOK_CONFIRM", eligibility_status="QUALIFIED", record_status="ACTIVE",
        )
        db.add_all([student, legacy_student])
        db.flush()
        db.add(GraduationTaskBook(
            tenant_id=TENANT_ID, gd_student_id=int(student.id), status="CONFIRMED",
            objective="完成毕业设计", content="实现公共版本", progress_plan="按阶段推进",
            outcome_requirement="形成可归档成果", confirmed_at=datetime.utcnow(),
        ))
        db.commit()
    finally:
        db.close()

    # 开题 v1 → 驳回 → v2 → 通过。正文即使无附件也生成不可变 TXT 快照。
    set_current_user(student_user)
    p1 = center.submit_proposal(student_user, {
        "background": "第一次开题背景，验证公共文件版本。",
        "plan": "第一次研究方案与进度。",
        "outcome": "形成阶段六验收成果。",
        "attachments": [],
    })
    assert p1["version"] == "v1" and p1["fileVersionCount"] == 1
    p1_id = int(p1["id"])

    set_current_user(teacher_user)
    p1_detail = center.proposal_detail(p1_id)
    assert p1_detail["reviewReady"] is True
    assert len(p1_detail["currentSafeVersions"]) == 1
    p1_version_id = int(p1_detail["currentSafeVersions"][0]["versionId"])
    center.review_proposal(p1_id, "REJECT", "第一次开题内容不完整，请修改后重新提交", teacher_user)

    set_current_user(student_user)
    p2 = center.submit_proposal(student_user, {
        "background": "第二次开题背景，已完成修订。",
        "plan": "第二次研究方案与进度，内容完整。",
        "outcome": "形成可审核和归档的稳定成果。",
        "attachments": [],
    })
    assert p2["version"] == "v2" and p2["isResubmit"] is True
    p2_id = int(p2["id"])

    set_current_user(teacher_user)
    p2_detail = center.proposal_detail(p2_id)
    assert p2_detail["reviewReady"] is True
    p2_version_id = int(p2_detail["currentSafeVersions"][0]["versionId"])
    assert p2_version_id != p1_version_id
    center.review_proposal(p2_id, "APPROVE", "开题内容完整，同意通过当前安全版本", teacher_user)

    db = get_sessionmaker()()
    try:
        v1 = db.get(FileVersion, p1_version_id)
        v2 = db.get(FileVersion, p2_version_id)
        assert v1 is not None and v1.is_current is False
        assert v2 is not None and v2.is_current is True and v2.status == "APPROVED"
        old_binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == TENANT_ID, FileBinding.version_id == p1_version_id,
            FileBinding.module_code == "graduation",
        )).first()
        assert old_binding is not None and old_binding.is_current is False

        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == TENANT_ID, GraduationStudent.student_no == STUDENT_NO,
        )).first()
        student.stage = "FINAL_CHECK"
        db.add(GraduationMidterm(
            tenant_id=TENANT_ID, gd_student_id=int(student.id), batch_id=int(student.batch_id),
            status="CHECKED_PASS", conclusion="PASS", checked_at=datetime.utcnow(),
        ))
        draft_file = _real_file(
            db, name="阶段六毕业设计初稿.pdf",
            body=b"%PDF-1.4\nphase6 graduation draft\n%%EOF\n",
        )
        final_file = _real_file(
            db, name="阶段六毕业设计定稿.pdf",
            body=b"%PDF-1.4\nphase6 graduation final approved\n%%EOF\n",
        )
        legacy_file = _real_file(
            db, name="旧开题附件.pdf",
            body=b"%PDF-1.4\nlegacy graduation material\n%%EOF\n",
            owner=6301,
        )
        legacy_student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == TENANT_ID,
            GraduationStudent.student_no == LEGACY_STUDENT_NO,
        )).first()
        legacy_proposal = GraduationProposal(
            tenant_id=TENANT_ID, gd_student_id=int(legacy_student.id), version="v1",
            is_resubmit=False, submit_at=datetime.utcnow(), background="旧背景",
            plan="旧计划", outcome="旧成果", attachments_json=[int(legacy_file.id)],
            status="APPROVED", active_key=None,
        )
        db.add(legacy_proposal)
        db.commit()
        draft_file_id, final_file_id = int(draft_file.id), int(final_file.id)
        student_id = int(student.id)
    finally:
        db.close()

    # 初稿和定稿均进入公共版本；定稿审核前必须存在服务端查重完成记录。
    set_current_user(student_user)
    draft = center.submit_final(student_user, {"finalType": "初稿", "attachments": [draft_file_id]})
    draft_id = int(draft["id"])
    set_current_user(teacher_user)
    draft_detail = center.final_detail(draft_id)
    assert draft_detail["reviewReady"] is True and len(draft_detail["currentSafeVersions"]) == 1
    center.review_final(draft_id, "APPROVE", "初稿结构完整，同意通过当前安全版本", teacher_user)

    set_current_user(student_user)
    approved = center.submit_final(student_user, {"finalType": "定稿", "attachments": [final_file_id]})
    approved_id = int(approved["id"])
    db = get_sessionmaker()()
    try:
        db.add(GraduationPlagiarismCheck(
            tenant_id=TENANT_ID, gd_student_id=student_id, gd_final_id=approved_id,
            submit_at=datetime.utcnow(), status="DONE", active_key=None,
            rate="8.5%", threshold=30, over_threshold=False, dispute_status="NONE",
        ))
        db.commit()
    finally:
        db.close()
    set_current_user(teacher_user)
    final_detail = center.final_detail(approved_id)
    assert final_detail["reviewReady"] is True
    final_version_id = int(final_detail["currentSafeVersions"][0]["versionId"])
    center.review_final(approved_id, "APPROVE", "定稿及查重结果合格，同意通过当前安全版本", teacher_user)

    # 不安全文件不能进入提交、审核或归档。
    db = get_sessionmaker()()
    try:
        unsafe = _real_file(
            db, name="扫描中材料.pdf", body=b"%PDF-1.4\nunsafe pending\n%%EOF\n",
        )
        unsafe.status = "QUARANTINED"
        unsafe.scan_status = "PENDING"
        unsafe.storage_zone = "QUARANTINE"
        db.commit()
        unsafe_id = int(unsafe.id)
    finally:
        db.close()
    set_current_user(student_user)
    try:
        center.submit_final(student_user, {"finalType": "初稿", "attachments": [unsafe_id]})
    except AppException as exc:
        assert exc.code in {"DATA_CONFLICT", "FILE_TYPE_NOT_ALLOWED"}
    else:
        raise AssertionError("unsafe graduation material unexpectedly passed phase 6 gate")

    # 旧 attachments_json 回填：首轮转换，第二轮幂等完成。
    set_current_user(teacher_user)
    first_backfill = center.backfill_legacy(teacher_user)
    assert first_backfill["convertedProposals"] == 1
    second_backfill = center.backfill_legacy(teacher_user)
    assert second_backfill["completed"] is True

    # 模板资产 v1→v2，旧版本保留但失效。
    db = get_sessionmaker()()
    try:
        template = GraduationTemplate(
            tenant_id=TENANT_ID, name="阶段六开题模板", template_type="开题报告",
            content="第一版模板正文", template_version="v1", status="ENABLED",
        )
        db.add(template)
        db.commit()
        template_id = int(template.id)
    finally:
        db.close()
    template_v1 = center.publish_template_asset(template_id, None, teacher_user)
    db = get_sessionmaker()()
    try:
        template = db.get(GraduationTemplate, template_id)
        template.content = "第二版模板正文"
        template.template_version = "v2"
        db.commit()
    finally:
        db.close()
    template_v2 = center.publish_template_asset(template_id, None, teacher_user)
    assert int(template_v2["versionNo"]) == 2
    db = get_sessionmaker()()
    try:
        old_template_version = db.get(FileVersion, int(template_v1["versionId"]))
        new_template_version = db.get(FileVersion, int(template_v2["versionId"]))
        assert old_template_version.is_current is False and old_template_version.status == "INVALIDATED"
        assert new_template_version.is_current is True
    finally:
        db.close()

    # 冻结真实 Manifest，只包含当前已通过开题 v2 与定稿；再生成单人 ZIP。
    db = get_sessionmaker()()
    try:
        student = db.get(GraduationStudent, student_id)
        archive = GraduationArchiveRecord(
            tenant_id=TENANT_ID, gd_student_id=student_id,
            checklist_json=[], missing_items=[], status="SUBMITTED",
            generated_at=datetime.utcnow(), submitted_at=datetime.utcnow(),
            archive_batch_no="GD-P6-ARCHIVE",
        )
        db.add(archive)
        db.flush()
        frozen = center.freeze_archive_manifest(db, archive, student, "GD-P6-ARCHIVE", teacher_user)
        archive.status = "FILED"
        archive.verified_by = teacher_user["realName"]
        archive.filed_at = datetime.utcnow()
        archive.manifest_hash = frozen["manifestSha256"]
        db.commit()
        manifest_id = int(frozen["manifestId"])
    finally:
        db.close()

    db = get_sessionmaker()()
    try:
        manifest = db.get(ArchiveManifest, manifest_id)
        items = db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == TENANT_ID,
            ArchiveManifestItem.manifest_id == manifest_id,
        ).order_by(ArchiveManifestItem.sort_no)).all()
        assert manifest.status == "FROZEN"
        assert len(items) >= 2
        version_ids = {int(item.version_id) for item in items}
        assert p2_version_id in version_ids
        assert p1_version_id not in version_ids
        assert final_version_id in version_ids
        for item in items:
            version = db.get(FileVersion, int(item.version_id))
            assert version.is_current is True and version.status == "APPROVED"
            assert int(version.file_object_id) == int(item.file_object_id)
    finally:
        db.close()

    package = center.build_student_package(student_id, teacher_user)
    _, _archive, names, package_manifest, zip_entries = _zip_payload(int(package["fileId"]))
    material_names = [name for name in names if name.startswith("materials/")]
    assert len(material_names) == package_manifest["materialFileCount"]
    assert package_manifest["materialFileCount"] == package["materialFileCount"]
    assert len(package_manifest["items"]) == len(material_names)
    for item in package_manifest["items"]:
        data = zip_entries[item["archivePath"]]
        assert len(data) == int(item["sizeBytes"])
        assert hashlib.sha256(data).hexdigest() == item["sha256"]

    # 批量 ZIP 同时带真实 Excel 索引；材料文件数、清单项与哈希完全一致。
    batch_package = center.build_batch_package(int(student_user["graduationBatchId"]), teacher_user)
    _, _batch_archive, batch_names, batch_manifest, batch_entries = _zip_payload(int(batch_package["zipFileId"]))
    assert "归档索引.xlsx" in batch_names
    assert batch_manifest["materialFileCount"] == batch_package["materialFileCount"]
    batch_materials = [name for name in batch_names if "/materials/" in name]
    assert len(batch_materials) == batch_manifest["materialFileCount"]
    assert hashlib.sha256(batch_entries["归档索引.xlsx"]).hexdigest() == batch_manifest["indexFile"]["sha256"]
    for item in batch_manifest["items"]:
        data = batch_entries[item["archivePath"]]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]

    library = center.student_material_library(student_id, teacher_user)
    assert library["total"] >= 3
    assert any(int(asset["versionCount"]) >= 2 for asset in library["items"])

    print("Stage 6 MySQL graduation version/review/manifest/zip/excel/template acceptance passed")
    set_current_user(None)
    set_tenant(None)
    _cleanup()


if __name__ == "__main__":
    main()
