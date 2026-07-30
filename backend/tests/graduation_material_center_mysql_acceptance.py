"""阶段 6：真实 MySQL 毕业设计18类材料、版本审核、Manifest、ExportJob验收。"""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from datetime import datetime

from openpyxl import load_workbook
from sqlalchemy import delete, func, select

TENANT_ID = 990000000000000626
OTHER_TENANT_ID = TENANT_ID + 1
STUDENT_NO = "GD-P6-0001"
LEGACY_STUDENT_NO = "GD-P6-LEGACY"


def _cleanup() -> None:
    from app.db.session import get_sessionmaker
    from app.models import (
        GraduationArchiveRecord,
        GraduationAuditTrail,
        GraduationBatch,
        GraduationDefenseScore,
        GraduationFinal,
        GraduationGrade,
        GraduationGuidance,
        GraduationMidterm,
        GraduationPlagiarismCheck,
        GraduationProposal,
        GraduationReview,
        GraduationStudent,
        GraduationTaskBook,
        GraduationTemplate,
        StudentProfile,
        UnifiedTodo,
    )
    from app.models.data_exchange import ExportJob
    from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileBinding, FileObject, FileVersion
    from app.models.graduation_material import (
        GraduationMaterialBackfillCheckpoint,
        GraduationMaterialItem,
        GraduationMaterialRule,
        GraduationStudentMaterial,
        GraduationTemplateAssetPolicy,
    )

    db = get_sessionmaker()()
    try:
        manifest_ids = list(db.scalars(select(ArchiveManifest.id).where(
            ArchiveManifest.tenant_id.in_((TENANT_ID, OTHER_TENANT_ID)),
        )).all())
        if manifest_ids:
            db.execute(delete(ArchiveManifestItem).where(
                ArchiveManifestItem.tenant_id.in_((TENANT_ID, OTHER_TENANT_ID)),
                ArchiveManifestItem.manifest_id.in_(manifest_ids),
            ))
        rule_ids = list(db.scalars(select(GraduationMaterialRule.id).where(
            GraduationMaterialRule.tenant_id.in_((TENANT_ID, OTHER_TENANT_ID)),
        )).all())
        if rule_ids:
            db.execute(delete(GraduationMaterialItem).where(
                GraduationMaterialItem.tenant_id.in_((TENANT_ID, OTHER_TENANT_ID)),
                GraduationMaterialItem.rule_id.in_(rule_ids),
            ))
        for model in (
            ExportJob,
            ArchiveManifest,
            GraduationMaterialBackfillCheckpoint,
            GraduationTemplateAssetPolicy,
            GraduationStudentMaterial,
            GraduationPlagiarismCheck,
            GraduationReview,
            GraduationDefenseScore,
            GraduationGrade,
            GraduationGuidance,
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
            db.execute(delete(model).where(model.tenant_id.in_((TENANT_ID, OTHER_TENANT_ID))))
        db.commit()
    finally:
        db.close()


def _real_file(
    db,
    *,
    name: str,
    body: bytes,
    owner: int = 6101,
    tenant_id: int = TENANT_ID,
    status: str = "AVAILABLE",
    scan_status: str = "CLEAN",
    storage_zone: str = "ACTIVE",
):
    from app.models.file import FileObject
    from app.services.storage import get_backend

    key = f"phase6/{tenant_id}/{name}"
    backend = get_backend()
    target = backend.staging_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    backend.persist(key, target)
    ext = name.rsplit(".", 1)[-1].lower()
    mime = {
        "pdf": "application/pdf",
        "zip": "application/zip",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "application/octet-stream")
    row = FileObject(
        tenant_id=tenant_id,
        file_key=key,
        file_name=name,
        ext=ext,
        mime_type=mime,
        size_bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        biz_type="ATTACHMENT",
        biz_id="",
        visibility="PRIVATE",
        security_level="SENSITIVE",
        status=status,
        storage_backend="local",
        storage_zone=storage_zone,
        upload_source="USER",
        owner_user_id=owner,
        created_by=owner,
        scan_required=True,
        scan_status=scan_status,
        available_at=datetime.utcnow() if status == "AVAILABLE" else None,
    )
    db.add(row)
    db.flush()
    return row


def _read_file(file_id: int) -> tuple[object, bytes]:
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
        return row, data
    finally:
        db.close()


def _expect_blocked(fn, *, codes: set[str] | None = None) -> None:
    from app.core.exceptions import AppException

    try:
        fn()
    except AppException as exc:
        if codes:
            assert exc.code in codes, (exc.code, str(exc))
    else:
        raise AssertionError("operation unexpectedly passed the Stage 6 safety gate")


def _expect_not_found(fn) -> None:
    from app.core.exceptions import AppException

    try:
        fn()
    except AppException as exc:
        assert exc.code in {"NOT_FOUND", "NO_PERMISSION"}, (exc.code, str(exc))
        assert getattr(exc, "http_status", 404) in {403, 404}
    else:
        raise AssertionError("enumeration attempt unexpectedly succeeded")


def _zip_payload(file_id: int):
    row, data = _read_file(file_id)
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        names = archive.namelist()
        entries = {name: archive.read(name) for name in names}
        manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    return row, names, entries, manifest


def _xlsx_rows(data: bytes) -> list[tuple]:
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
    try:
        sheet = workbook["毕业设计档案清单"]
        return list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (
        GraduationArchiveRecord,
        GraduationBatch,
        GraduationDefenseScore,
        GraduationFinal,
        GraduationGrade,
        GraduationGuidance,
        GraduationMidterm,
        GraduationPlagiarismCheck,
        GraduationProposal,
        GraduationReview,
        GraduationStudent,
        GraduationTaskBook,
        GraduationTemplate,
        StudentProfile,
    )
    from app.models.file import ArchiveManifest, ArchiveManifestItem, FileBinding, FileObject, FileVersion
    from app.models.graduation_material import GraduationStudentMaterial
    from app.modules.graduation.services import graduation_material_catalog_service as catalog
    from app.modules.graduation.services import graduation_material_center_service as center
    from app.modules.graduation.services import graduation_material_export_service as archive_export
    from app.services.data_exchange_job_service import create_download_ticket

    _cleanup()
    set_tenant({"tenantId": TENANT_ID, "tenantCode": "graduation-stage6"})
    student_user = {
        "userId": "6101",
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
        "studentNo": STUDENT_NO,
        "realName": "阶段六学生",
    }
    teacher_user = {
        "userId": "6201",
        "loginName": "GD-ADMIN-P6",
        "userType": "TEACHER",
        "currentRoleCode": "GRADUATION_ADMIN",
        "realName": "阶段六毕设管理员",
        "permissions": ["*"],
    }
    unauthorized_teacher = {
        "userId": "6202",
        "loginName": "GD-COLLEGE-OTHER",
        "userType": "TEACHER",
        "currentRoleCode": "GD_COLLEGE_ADMIN",
        "collegeId": "OTHER-COLLEGE",
        "collegeIds": ["OTHER-COLLEGE"],
        "realName": "其他学院教师",
        "permissions": ["graduationDesign.view", "graduationDesign.proposal.review"],
    }

    db = get_sessionmaker()()
    try:
        profile = StudentProfile(
            tenant_id=TENANT_ID,
            student_no=STUDENT_NO,
            real_name="阶段六学生",
            current_stage="IN_SCHOOL",
            student_status="NORMAL",
            status="ACTIVE",
        )
        legacy_profile = StudentProfile(
            tenant_id=TENANT_ID,
            student_no=LEGACY_STUDENT_NO,
            real_name="旧材料学生",
            current_stage="IN_SCHOOL",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([profile, legacy_profile])
        db.flush()
        student_user["studentId"] = str(profile.id)

        batch = GraduationBatch(
            tenant_id=TENANT_ID,
            batch_name="阶段六毕业设计批次",
            batch_no="GD-P6-2026",
            academic_year="2025-2026",
            grade_year="2026届",
            status="RUNNING",
        )
        db.add(batch)
        db.flush()
        student_user["graduationBatchId"] = str(batch.id)

        student = GraduationStudent(
            tenant_id=TENANT_ID,
            batch_id=int(batch.id),
            topic_id=66001,
            student_id=int(profile.id),
            student_no=STUDENT_NO,
            name="阶段六学生",
            class_id="C-P6",
            class_name="软件技术1班",
            college_id="COL-P6",
            major_id="MAJ-P6",
            topic_title="=阶段六公共文件版本毕业设计",
            advisor_name="阶段六导师",
            defense_group="第一答辩组",
            stage="TASKBOOK_CONFIRM",
            eligibility_status="QUALIFIED",
            record_status="ACTIVE",
        )
        legacy_student = GraduationStudent(
            tenant_id=TENANT_ID,
            batch_id=int(batch.id),
            topic_id=66002,
            student_id=int(legacy_profile.id),
            student_no=LEGACY_STUDENT_NO,
            name="旧材料学生",
            class_id="C-P6",
            class_name="软件技术1班",
            college_id="COL-P6",
            major_id="MAJ-P6",
            topic_title="旧材料回填",
            advisor_name="阶段六导师",
            stage="TASKBOOK_CONFIRM",
            eligibility_status="QUALIFIED",
            record_status="ACTIVE",
        )
        db.add_all([student, legacy_student])
        db.flush()

        db.add(GraduationTaskBook(
            tenant_id=TENANT_ID,
            gd_student_id=int(student.id),
            status="CONFIRMED",
            objective="完成毕业设计",
            content="实现公共版本与归档任务",
            progress_plan="按阶段推进",
            outcome_requirement="形成可审计归档成果",
            confirmed_at=datetime.utcnow(),
        ))
        db.add(GraduationGuidance(
            tenant_id=TENANT_ID,
            gd_student_id=int(student.id),
            guidance_date=datetime.utcnow(),
            method="ONLINE",
            content="核对公共文件版本与安全状态",
            issues="完成真实归档证据",
        ))
        db.add(GraduationMidterm(
            tenant_id=TENANT_ID,
            gd_student_id=int(student.id),
            batch_id=int(batch.id),
            status="CHECKED_PASS",
            conclusion="PASS",
            check_comment="中期检查通过",
            check_by=teacher_user["realName"],
            checked_at=datetime.utcnow(),
        ))
        db.commit()
        student_id = int(student.id)
        legacy_student_id = int(legacy_student.id)
        batch_id = int(batch.id)
    finally:
        db.close()

    # 完整材料规则必须包含18类，学生材料库必须真实生成18个材料项。
    set_current_user(teacher_user)
    rules = catalog.list_rules(batch_id, teacher_user)
    assert rules["total"] >= 1
    active_rule = next(item for item in rules["items"] if item["status"] == "ENABLED")
    rule_codes = {item["materialCode"] for item in active_rule["items"]}
    assert rule_codes == set(catalog.SPEC_BY_CODE)
    assert len(rule_codes) == 18

    set_current_user(student_user)
    initial_library = catalog.student_library(None, student_user)
    assert initial_library["total"] == 18
    assert all("version" in item for item in initial_library["items"])
    item_versions = {item["materialCode"]: int(item["version"]) for item in initial_library["items"]}

    # 开题 v1 → 退回 → v2 → 审核通过；业务 version 不作为文件版本。
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
    p2_version_id = int(p2_detail["currentSafeVersions"][0]["versionId"])
    assert p2_detail["reviewReady"] is True and p2_version_id != p1_version_id
    center.review_proposal(p2_id, "APPROVE", "开题内容完整，同意通过当前安全版本", teacher_user)

    db = get_sessionmaker()()
    try:
        v1 = db.get(FileVersion, p1_version_id)
        v2 = db.get(FileVersion, p2_version_id)
        assert v1 is not None and v1.is_current is False and v1.status == "INVALIDATED"
        assert v2 is not None and v2.is_current is True and v2.status == "APPROVED"
        old_binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == TENANT_ID,
            FileBinding.version_id == p1_version_id,
            FileBinding.module_code == "graduation",
        )).first()
        assert old_binding is not None and old_binding.is_current is False

        draft_file = _real_file(
            db,
            name="阶段六毕业设计初稿.pdf",
            body=b"%PDF-1.4\nphase6 graduation draft\n%%EOF\n",
        )
        final_file = _real_file(
            db,
            name="阶段六毕业设计定稿.pdf",
            body=b"%PDF-1.4\nphase6 graduation final approved\n%%EOF\n",
        )
        legacy_file = _real_file(
            db,
            name="旧开题附件.pdf",
            body=b"%PDF-1.4\nlegacy graduation material\n%%EOF\n",
            owner=6301,
        )
        pending_file = _real_file(
            db,
            name="扫描中设计作品.pdf",
            body=b"%PDF-1.4\npending design work\n%%EOF\n",
            status="QUARANTINED",
            scan_status="PENDING",
            storage_zone="QUARANTINE",
        )
        infected_file = _real_file(
            db,
            name="感染源代码.zip",
            body=b"PK\x03\x04phase6 infected fixture metadata only",
            status="REJECTED",
            scan_status="INFECTED",
            storage_zone="QUARANTINE",
        )
        clean_design = _real_file(
            db,
            name="安全设计作品.pdf",
            body=b"%PDF-1.4\nclean design work\n%%EOF\n",
        )
        clean_source = _real_file(
            db,
            name="安全源代码.zip",
            body=b"PK\x03\x04phase6 clean source archive",
        )
        cross_tenant_file = _real_file(
            db,
            name="跨租户材料.pdf",
            body=b"%PDF-1.4\nother tenant\n%%EOF\n",
            tenant_id=OTHER_TENANT_ID,
            owner=9999,
        )
        legacy_student = db.get(GraduationStudent, legacy_student_id)
        legacy_proposal = GraduationProposal(
            tenant_id=TENANT_ID,
            gd_student_id=int(legacy_student.id),
            version="v1",
            is_resubmit=False,
            submit_at=datetime.utcnow(),
            background="旧背景",
            plan="旧计划",
            outcome="旧成果",
            attachments_json=[int(legacy_file.id)],
            status="APPROVED",
            active_key=None,
        )
        db.add(legacy_proposal)
        proposal_v2 = db.get(GraduationProposal, p2_id)
        proposal_v2.defense_result = "PASS"
        proposal_v2.defense_comment = "开题答辩通过"
        proposal_v2.defense_at = datetime.utcnow()
        db.commit()

        draft_file_id = int(draft_file.id)
        final_file_id = int(final_file.id)
        pending_file_id = int(pending_file.id)
        infected_file_id = int(infected_file.id)
        clean_design_id = int(clean_design.id)
        clean_source_id = int(clean_source.id)
        cross_tenant_file_id = int(cross_tenant_file.id)
        legacy_proposal_id = int(legacy_proposal.id)
    finally:
        db.close()

    # 成果初稿/定稿进入公共版本，定稿审批再次检查文件安全和查重状态。
    set_current_user(student_user)
    draft = center.submit_final(student_user, {"finalType": "初稿", "attachments": [draft_file_id]})
    draft_id = int(draft["id"])
    set_current_user(teacher_user)
    draft_detail = center.final_detail(draft_id)
    assert draft_detail["reviewReady"] is True
    center.review_final(draft_id, "APPROVE", "初稿结构完整，同意通过当前安全版本", teacher_user)

    set_current_user(student_user)
    final = center.submit_final(student_user, {"finalType": "定稿", "attachments": [final_file_id]})
    final_id = int(final["id"])
    db = get_sessionmaker()()
    try:
        db.add(GraduationPlagiarismCheck(
            tenant_id=TENANT_ID,
            gd_student_id=student_id,
            gd_final_id=final_id,
            submit_at=datetime.utcnow(),
            status="DONE",
            active_key=None,
            rate="8.5%",
            threshold=30,
            over_threshold=False,
            dispute_status="NONE",
        ))
        db.add(GraduationReview(
            tenant_id=TENANT_ID,
            gd_student_id=student_id,
            gd_final_id=final_id,
            reviewer_name="阶段六评阅教师",
            status="COMPLETED",
            score=88,
            opinion="评阅通过",
            reviewed_at=datetime.utcnow(),
        ))
        db.add(GraduationDefenseScore(
            tenant_id=TENANT_ID,
            gd_student_id=student_id,
            defense_group_id=77001,
            judge_name="阶段六答辩评委",
            judge_identity="MENTOR:77001",
            score=90,
            comment="答辩通过",
            round_no=1,
            status="CONFIRMED",
            confirmed_at=datetime.utcnow(),
        ))
        db.add(GraduationGrade(
            tenant_id=TENANT_ID,
            gd_student_id=student_id,
            advisor_score=89,
            reviewer_score=88,
            defense_score=90,
            total_score=89,
            grade_level="良好",
            status="REVIEWED",
            reviewed_by=teacher_user["realName"],
            reviewed_at=datetime.utcnow(),
            source_snapshot_hash=hashlib.sha256(b"phase6-grade-snapshot").hexdigest(),
        ))
        db.commit()
    finally:
        db.close()

    set_current_user(teacher_user)
    final_detail = center.final_detail(final_id)
    final_version_id = int(final_detail["currentSafeVersions"][0]["versionId"])
    center.review_final(final_id, "APPROVE", "定稿及查重结果合格，同意通过当前安全版本", teacher_user)

    db = get_sessionmaker()()
    try:
        student = db.get(GraduationStudent, student_id)
        student.stage = "FINAL_CHECK"
        archive = GraduationArchiveRecord(
            tenant_id=TENANT_ID,
            gd_student_id=student_id,
            checklist_json=[],
            missing_items=[],
            status="SUBMITTED",
            generated_at=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
            archive_batch_no="GD-P6-ARCHIVE",
        )
        db.add(archive)
        db.commit()
    finally:
        db.close()

    # 扫描中、感染、跨租户文件不能通过学生提交。
    set_current_user(student_user)
    _expect_blocked(
        lambda: catalog.submit_material(student_user, "WORK_DESCRIPTION", pending_file_id),
        codes={"DATA_CONFLICT", "NOT_FOUND", "FILE_TYPE_NOT_ALLOWED"},
    )
    _expect_blocked(
        lambda: catalog.submit_material(student_user, "SOURCE_CODE", infected_file_id),
        codes={"DATA_CONFLICT", "NOT_FOUND", "FILE_TYPE_NOT_ALLOWED"},
    )
    _expect_not_found(lambda: catalog.submit_material(student_user, "WORK_DESCRIPTION", cross_tenant_file_id))

    # 构造历史遗留的异常当前版本，验证总览真实计数且归档 fail-closed，不静默跳过可选材料。
    set_current_user(teacher_user)
    db = get_sessionmaker()()
    try:
        student = db.get(GraduationStudent, student_id)
        catalog._ensure_student_rows(db, student, teacher_user)
        pending_material = catalog._row_for_code(db, student, "DESIGN_WORK", user=teacher_user)
        pending_obj = db.get(FileObject, pending_file_id)
        catalog._append_version(
            db, student, pending_material, pending_obj, teacher_user,
            source_channel="LEGACY_ADAPTER", status="SUBMITTED",
            source_type="LEGACY", source_id="PENDING", comment="历史扫描中材料",
        )
        pending_material.version = int(pending_material.version or 0) + 1
        db.commit()
    finally:
        db.close()

    overview = catalog.material_overview(teacher_user, batch_id=batch_id)
    assert overview["summary"]["scanAbnormalStudents"] == 1
    assert overview["items"][0]["scanAbnormalCount"] >= 1
    _expect_blocked(
        lambda: archive_export.freeze_manifest(student_id, "GD-P6-ARCHIVE", teacher_user),
        codes={"DATA_CONFLICT"},
    )

    # 以清洁已审核新版本替换异常旧版，旧版历史保留但不再是当前版本。
    db = get_sessionmaker()()
    try:
        student = db.get(GraduationStudent, student_id)
        design_material = catalog._row_for_code(db, student, "DESIGN_WORK", user=teacher_user)
        clean_obj = db.get(FileObject, clean_design_id)
        design_version = catalog._append_version(
            db, student, design_material, clean_obj, teacher_user,
            source_channel="TEACHER_UPLOAD", status="APPROVED",
            source_type="MATERIAL_ITEM", source_id=str(design_material.id), comment="安全设计作品",
        )
        design_material.version = int(design_material.version or 0) + 1
        source_material = catalog._row_for_code(db, student, "SOURCE_CODE", user=teacher_user)
        infected_obj = db.get(FileObject, infected_file_id)
        catalog._append_version(
            db, student, source_material, infected_obj, teacher_user,
            source_channel="LEGACY_ADAPTER", status="SUBMITTED",
            source_type="LEGACY", source_id="INFECTED", comment="历史感染材料",
        )
        source_material.version = int(source_material.version or 0) + 1
        db.commit()
        design_version_id = int(design_version.id)
    finally:
        db.close()

    _expect_blocked(
        lambda: archive_export.freeze_manifest(student_id, "GD-P6-ARCHIVE", teacher_user),
        codes={"DATA_CONFLICT"},
    )

    db = get_sessionmaker()()
    try:
        student = db.get(GraduationStudent, student_id)
        source_material = catalog._row_for_code(db, student, "SOURCE_CODE", user=teacher_user)
        clean_obj = db.get(FileObject, clean_source_id)
        source_version = catalog._append_version(
            db, student, source_material, clean_obj, teacher_user,
            source_channel="TEACHER_UPLOAD", status="APPROVED",
            source_type="MATERIAL_ITEM", source_id=str(source_material.id), comment="安全源代码包",
        )
        source_material.version = int(source_material.version or 0) + 1
        db.commit()
        source_version_id = int(source_version.id)
    finally:
        db.close()

    # 回填具备 dry-run、断点与幂等；重复执行不能创建重复公共版本。
    dry_run = catalog.backfill_legacy(
        teacher_user, page_size=1, cursor_model="PROPOSAL",
        cursor_id=legacy_proposal_id - 1, dry_run=True,
    )
    assert dry_run["scanned"] == 1 and dry_run["converted"] == 1
    first_backfill = catalog.backfill_legacy(
        teacher_user, page_size=1, cursor_model="PROPOSAL",
        cursor_id=legacy_proposal_id - 1, dry_run=False,
    )
    assert first_backfill["converted"] == 1
    second_backfill = catalog.backfill_legacy(
        teacher_user, page_size=1, cursor_model="PROPOSAL",
        cursor_id=legacy_proposal_id - 1, dry_run=False,
    )
    assert second_backfill["skipped"] == 1
    db = get_sessionmaker()()
    try:
        legacy_versions = db.scalar(select(func.count(FileVersion.id)).join(
            FileBinding, FileBinding.version_id == FileVersion.id,
        ).where(
            FileBinding.tenant_id == TENANT_ID,
            FileBinding.module_code == "graduation",
            FileBinding.scope_json["recordType"].as_string() == "PROPOSAL",
            FileBinding.scope_json["recordId"].as_string() == str(legacy_proposal_id),
        ))
        assert int(legacy_versions or 0) == 1
    finally:
        db.close()

    # 模板真实 Asset/FileVersion v1→v2，扫描异常模板不能发布启用。
    db = get_sessionmaker()()
    try:
        template = GraduationTemplate(
            tenant_id=TENANT_ID,
            name="阶段六开题模板",
            template_type="开题报告",
            content="模板正文",
            template_version="v1",
            variables_json=["studentName", "topicTitle"],
            status="ENABLED",
        )
        template_v1_file = _real_file(
            db, name="阶段六开题模板_v1.pdf",
            body=b"%PDF-1.4\nphase6 template v1\n%%EOF\n", owner=6201,
        )
        template_v2_file = _real_file(
            db, name="阶段六开题模板_v2.pdf",
            body=b"%PDF-1.4\nphase6 template v2\n%%EOF\n", owner=6201,
        )
        unsafe_template_file = _real_file(
            db, name="阶段六不安全模板.pdf",
            body=b"%PDF-1.4\npending template\n%%EOF\n", owner=6201,
            status="QUARANTINED", scan_status="PENDING", storage_zone="QUARANTINE",
        )
        db.add(template)
        db.commit()
        template_id = int(template.id)
        template_v1_file_id = int(template_v1_file.id)
        template_v2_file_id = int(template_v2_file.id)
        unsafe_template_file_id = int(unsafe_template_file.id)
    finally:
        db.close()

    template_v1 = catalog.publish_template_policy(
        template_id, template_v1_file_id,
        {"templateCode": "GD_PROPOSAL", "batchId": batch_id,
         "variableSchema": {"variables": [{"name": "studentName", "type": "string"}]}},
        teacher_user,
    )
    template_v2 = catalog.publish_template_policy(
        template_id, template_v2_file_id,
        {"templateCode": "GD_PROPOSAL", "batchId": batch_id,
         "variableSchema": {"variables": [
             {"name": "studentName", "type": "string"},
             {"name": "topicTitle", "type": "string"},
         ]}},
        teacher_user,
    )
    assert int(template_v2["versionNo"]) == 2
    _expect_blocked(
        lambda: catalog.publish_template_policy(
            template_id, unsafe_template_file_id,
            {"templateCode": "GD_PROPOSAL", "batchId": batch_id},
            teacher_user,
        ),
        codes={"DATA_CONFLICT", "FILE_TYPE_NOT_ALLOWED"},
    )
    template_catalog = catalog.template_catalog(teacher_user, batch_id=batch_id)
    policy = next(item for item in template_catalog["items"] if item["templateCode"] == "GD_PROPOSAL")
    assert len(policy["versions"]) == 2
    assert policy["variableSchema"]["variables"][1]["name"] == "topicTitle"
    db = get_sessionmaker()()
    try:
        old_template_version = db.get(FileVersion, int(template_v1["versionId"]))
        new_template_version = db.get(FileVersion, int(template_v2["versionId"]))
        assert old_template_version.is_current is False and old_template_version.status == "INVALIDATED"
        assert new_template_version.is_current is True
    finally:
        db.close()

    # 无权教师、猜测学生/Manifest/ExportJob ID统一不可枚举。
    set_current_user(unauthorized_teacher)
    _expect_not_found(lambda: catalog.student_library(student_id, unauthorized_teacher))
    _expect_not_found(lambda: archive_export.latest_manifest(student_id, unauthorized_teacher))
    _expect_not_found(lambda: archive_export.get_export_job(999999999, unauthorized_teacher))
    set_current_user(teacher_user)
    _expect_not_found(lambda: catalog.student_library(999999999, teacher_user))
    _expect_not_found(lambda: archive_export.latest_manifest(999999999, teacher_user))
    _expect_not_found(lambda: archive_export.get_export_job(999999999, teacher_user))

    # 冻结真实 Manifest：只引用当前、安全、已审核版本；v1不得进入。
    manifest = archive_export.freeze_manifest(student_id, "GD-P6-ARCHIVE", teacher_user)
    manifest_id = int(manifest["manifestId"])
    assert manifest["status"] == "FROZEN"
    assert manifest["itemCount"] >= 11
    manifest_version_ids = {int(item["fileVersionId"]) for item in manifest["items"]}
    assert p2_version_id in manifest_version_ids
    assert p1_version_id not in manifest_version_ids
    assert final_version_id in manifest_version_ids
    assert design_version_id in manifest_version_ids
    assert source_version_id in manifest_version_ids
    for item in manifest["items"]:
        assert item["fileObjectId"] and item["fileName"]
        assert int(item["sizeBytes"]) > 0
        assert len(item["sha256"]) == 64
        assert item["scanResult"] in {"CLEAN", "NOT_REQUIRED"}
        assert item["reviewStatus"] in {"APPROVED", "NOT_REQUIRED"}
        assert item["uploader"]
        assert item["submittedAt"]

    db = get_sessionmaker()()
    try:
        persisted_manifest = db.get(ArchiveManifest, manifest_id)
        persisted_items = list(db.scalars(select(ArchiveManifestItem).where(
            ArchiveManifestItem.tenant_id == TENANT_ID,
            ArchiveManifestItem.manifest_id == manifest_id,
        )).all())
        assert persisted_manifest.status == "FROZEN"
        assert len(persisted_items) == manifest["itemCount"]
        for item in persisted_items:
            version = db.get(FileVersion, int(item.version_id))
            file_obj = db.get(FileObject, int(item.file_object_id))
            assert version.is_current is True and version.status == "ARCHIVED"
            assert int(version.file_object_id) == int(file_obj.id)
            assert file_obj.sha256 == item.sha256_snapshot
            assert int(file_obj.size_bytes) == int(item.size_snapshot)
    finally:
        db.close()

    # 真实 ExportJob：生成持久化 ZIP + XLSX，刷新可查询，数量与SHA完全一致。
    created_job = archive_export.create_export_job(
        batch_id=batch_id, scope_type="STUDENT", scope_value=str(student_id), user=teacher_user,
    )
    job_id = int(created_job["id"])
    assert created_job["status"] == "CREATED"
    completed_job = archive_export.run_export_job(job_id, teacher_user)
    assert completed_job["status"] == "SUCCEEDED" and completed_job["progress"] == 100
    refreshed_job = archive_export.get_export_job(job_id, teacher_user)
    assert refreshed_job["status"] == "SUCCEEDED"
    result = refreshed_job["result"]
    zip_id = int(result["zipFileObjectId"])
    xlsx_id = int(result["xlsxFileObjectId"])
    zip_row, zip_names, zip_entries, package_manifest = _zip_payload(zip_id)
    xlsx_row, xlsx_data = _read_file(xlsx_id)
    assert zip_row.sha256 == result["zipSha256"]
    assert xlsx_row.sha256 == result["xlsxSha256"]
    assert hashlib.sha256(zip_entries["档案清单.xlsx"]).hexdigest() == result["xlsxSha256"]
    material_names = [name for name in zip_names if "/materials/" in name]
    assert len(material_names) == result["materialFileCount"]
    assert package_manifest["materialFileCount"] == result["materialFileCount"]
    assert len(package_manifest["items"]) == result["materialFileCount"]
    assert package_manifest["manifestCount"] == 1
    for item in package_manifest["items"]:
        payload = zip_entries[item["archivePath"]]
        assert len(payload) == int(item["sizeBytes"])
        assert hashlib.sha256(payload).hexdigest() == item["sha256"]

    xlsx_rows = _xlsx_rows(xlsx_data)
    zipped_xlsx_rows = _xlsx_rows(zip_entries["档案清单.xlsx"])
    assert xlsx_rows == zipped_xlsx_rows
    assert len(xlsx_rows) - 1 == result["materialFileCount"]
    headers = xlsx_rows[0]
    assert headers == (
        "批次", "学院", "专业", "班级", "学号", "姓名", "指导教师", "题目",
        "材料代码", "材料名称", "文件名", "文件版本", "文件大小", "SHA-256",
        "扫描状态", "审核状态", "上传时间", "归档 revision",
    )
    # 用户可控题目以 '=' 开头，XLSX必须强制转为文本。
    assert all(str(row[7]).startswith("'=") for row in xlsx_rows[1:])

    db = get_sessionmaker()()
    try:
        archived_rows = list(db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == TENANT_ID,
            GraduationStudentMaterial.gd_student_id == student_id,
            GraduationStudentMaterial.current_version_id.is_not(None),
        )).all())
        assert archived_rows and all(row.archive_status == "ARCHIVED" for row in archived_rows)
    finally:
        db.close()

    # 撤销后 Manifest、ExportJob、ZIP和XLSX全部失效；旧票据不能再签发。
    revoked = archive_export.revoke_manifest(student_id, "阶段六验收撤销归档包", teacher_user)
    assert revoked["status"] == "REVOKED" and str(job_id) in revoked["revokedJobs"]
    revoked_job = archive_export.get_export_job(job_id, teacher_user)
    assert revoked_job["status"] == "REVOKED"
    _expect_not_found(lambda: create_download_ticket(
        str(job_id), expected_version=int(revoked_job["version"]), user=teacher_user,
    ))
    db = get_sessionmaker()()
    try:
        assert db.get(FileObject, zip_id).status == "INVALIDATED"
        assert db.get(FileObject, xlsx_id).status == "INVALIDATED"
        current_versions = list(db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == TENANT_ID,
            FileVersion.id.in_(manifest_version_ids),
            FileVersion.is_current.is_(True),
        )).all())
        assert current_versions and all(version.status == "APPROVED" for version in current_versions)
        student = db.get(GraduationStudent, student_id)
        assert student.stage == "FINAL_CHECK"
    finally:
        db.close()

    # 重新冻结形成新 revision，不静默修改旧 Manifest。
    second_manifest = archive_export.freeze_manifest(student_id, "GD-P6-ARCHIVE-R2", teacher_user)
    assert int(second_manifest["revision"]) == int(manifest["revision"]) + 1
    assert int(second_manifest["manifestId"]) != manifest_id

    final_library = catalog.student_library(student_id, teacher_user)
    assert final_library["total"] == 18
    assert all(isinstance(item["version"], int) for item in final_library["items"])
    assert any(item["version"] > item_versions[item["materialCode"]] for item in final_library["items"])

    print(
        "Stage 6 MySQL graduation 18-material/version/review/manifest/"
        "ExportJob/ZIP/XLSX/template/revoke acceptance passed"
    )
    set_current_user(None)
    set_tenant(None)
    _cleanup()


if __name__ == "__main__":
    main()
