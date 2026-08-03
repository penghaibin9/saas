"""The only write path for graduation material instances and file versions."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.models import GraduationArchiveRecord, GraduationBatch, GraduationStudent, GraduationTemplate
from app.models.file import ArchiveManifest, FileAsset, FileBinding, FileObject, FileVersion
from app.models.graduation_material import (
    GraduationMaterialItem,
    GraduationStudentMaterial,
    GraduationTemplateAssetPolicy,
)
from app.services.db_service import _iso, _tid, session
from app.services.file_access_service import require_file_access
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED
from app.services.file_scan_service import assert_file_ready_for_business
from app.services.message_identity import resolve_message_user_id

from .definitions import MANIFEST_ARCHIVE_TYPE, MANIFEST_TARGET_TYPE, MODULE_CODE
from .rule_service import active_rule, rule_item, rule_items


_OWNER_ROLES = {
    "STUDENT": {"STUDENT"},
    "MENTOR": {"GD_MENTOR", "MENTOR", "TEACHER"},
    "REVIEWER": {"GD_REVIEWER", "REVIEWER"},
    "DEFENSE_SECRETARY": {"GD_DEFENSE_SECRETARY", "DEFENSE_SECRETARY"},
    "ADMIN": {
        "PLATFORM_SUPER_ADMIN", "SCHOOL_ADMIN", "GRADUATION_ADMIN", "GD_GRADE_ADMIN",
        "GD_COLLEGE_ADMIN", "COLLEGE_ADMIN", "GD_MAJOR_ADMIN",
    },
    "SYSTEM": {"SYSTEM"},
}


_REVIEW_PERMISSION_BY_CODE = {
    "TOPIC_ATTACHMENT": "graduationDesign.topic.review",
    "TASKBOOK": "graduationDesign.taskbook.update",
    "PROPOSAL_REPORT": "graduationDesign.proposal.review",
    "PROPOSAL_DEFENSE": "graduationDesign.proposal.review",
    "MIDTERM_REPORT": "graduationDesign.midterm.review",
    "THESIS_DRAFT": "graduationDesign.final.review",
    "THESIS_FINAL": "graduationDesign.final.review",
    "DESIGN_WORK": "graduationDesign.final.review",
    "SOURCE_CODE": "graduationDesign.final.review",
    "WORK_DESCRIPTION": "graduationDesign.final.review",
    "PLAGIARISM_REPORT": "graduationDesign.plagiarism.result",
    "REVIEW_ATTACHMENT": "graduationDesign.review.submit",
    "DEFENSE_SIGNED_SHEET": "graduationDesign.defense.scoreConfirm",
}


def review_permission_code(material_code: str) -> str:
    code = _REVIEW_PERMISSION_BY_CODE.get(str(material_code or "").strip().upper())
    if not code:
        raise AppException("NO_PERMISSION", "该材料未配置审核动作权限，系统已拒绝操作", http_status=403)
    return code


def _enforce_review_permission(user: dict, material_code: str) -> str:
    if str((user or {}).get("userType") or "").strip().upper() == "STUDENT":
        raise AppException("NO_PERMISSION", "学生不能审核毕业设计材料", http_status=403)
    code = review_permission_code(material_code)
    enforce_permission(user or {}, code)
    return code


def _actor_id(user: dict | None) -> int | None:
    return resolve_message_user_id(user or {}) or None


def _actor_name(user: dict | None) -> str:
    value = user or get_current_user_ctx() or {}
    return str(value.get("realName") or value.get("loginName") or value.get("username") or "system")[:100]


def _actor_role(user: dict | None) -> str:
    value = user or get_current_user_ctx() or {}
    return str(value.get("currentRoleCode") or value.get("userType") or "").strip().upper()


def _safe_int(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _student_for_update(db, gd_student_id: int) -> GraduationStudent:
    row = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.id == int(gd_student_id),
        GraduationStudent.record_status == "ACTIVE",
        GraduationStudent.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise not_found("毕业设计学生档案不存在")
    if not row.batch_id:
        raise AppException("DATA_CONFLICT", "学生尚未加入毕业设计批次")
    return row


def _batch_for_update(db, batch_id: int) -> GraduationBatch:
    row = db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == _tid(), GraduationBatch.id == int(batch_id),
        GraduationBatch.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise not_found("毕业设计批次不存在")
    return row


def _assert_not_archived(db, student: GraduationStudent) -> None:
    if str(student.stage or "").upper() == "ARCHIVED":
        raise AppException("DATA_CONFLICT", "已归档学生不允许普通提交；请先撤销归档")
    archive = db.scalars(select(GraduationArchiveRecord).where(
        GraduationArchiveRecord.tenant_id == _tid(),
        GraduationArchiveRecord.gd_student_id == int(student.id),
        GraduationArchiveRecord.is_deleted.is_(False),
    ).with_for_update()).first()
    if archive and archive.status == "FILED":
        raise AppException("DATA_CONFLICT", "已归档学生不允许普通提交；请先撤销归档")
    manifest = db.scalars(select(ArchiveManifest.id).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == MANIFEST_ARCHIVE_TYPE,
        ArchiveManifest.target_type == MANIFEST_TARGET_TYPE,
        ArchiveManifest.target_id == str(student.id),
        ArchiveManifest.status.in_(("FROZEN", "PACKAGED")),
        ArchiveManifest.is_deleted.is_(False),
    ).limit(1)).first()
    if manifest:
        raise AppException("DATA_CONFLICT", "有效归档 Manifest 存在，不允许修改材料")


def _required_status(item: GraduationMaterialItem) -> str:
    return "REQUIRED" if item.required else "OPTIONAL"


def _new_material(student: GraduationStudent, item: GraduationMaterialItem, rule_id: int, rule_version: int,
                  actor_id: int | None) -> GraduationStudentMaterial:
    return GraduationStudentMaterial(
        tenant_id=_tid(), batch_id=int(student.batch_id), gd_student_id=int(student.id),
        student_id=student.student_id, topic_id=student.topic_id, rule_id=int(rule_id),
        rule_version=int(rule_version), material_code=item.material_code,
        material_name=item.material_name, biz_stage=item.biz_stage, owner_role=item.owner_role,
        business_status="MISSING", review_status="NOT_SUBMITTED",
        required_status=_required_status(item), archive_status="NOT_ARCHIVED",
        sensitivity_level=item.sensitivity_level, migration_status="NATIVE", created_by=actor_id,
    )


def initialize_student_materials_in_session(db, gd_student_id: int, user: dict | None = None) -> dict:
    """Idempotently materialize the enabled rule for one active student."""
    student = _student_for_update(db, int(gd_student_id))
    rule = active_rule(db, int(student.batch_id), lock=True)
    items = rule_items(db, int(rule.id), lock=True)
    existing = {row.material_code: row for row in db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).all()}
    created = 0
    for item in items:
        if item.material_code in existing:
            continue
        db.add(_new_material(student, item, int(rule.id), int(rule.rule_version), _actor_id(user)))
        created += 1
    db.flush()
    return {
        "gdStudentId": str(student.id), "ruleId": str(rule.id),
        "ruleVersion": int(rule.rule_version), "created": created, "total": len(items),
    }


def initialize_student_materials(gd_student_id: int, user: dict | None = None) -> dict:
    with session() as db:
        result = initialize_student_materials_in_session(db, int(gd_student_id), user)
        db.commit()
        return result


def initialize_batch_materials_in_session(db, batch_id: int, user: dict | None = None) -> dict:
    """Idempotently initialize all active students in a batch in the caller's transaction."""
    _batch_for_update(db, int(batch_id))
    active_rule(db, int(batch_id), lock=True)
    student_ids = list(db.scalars(select(GraduationStudent.id).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
    ).order_by(GraduationStudent.id).with_for_update()).all())
    created = 0
    for gd_student_id in student_ids:
        created += int(initialize_student_materials_in_session(db, int(gd_student_id), user)["created"])
    return {"batchId": str(batch_id), "studentCount": len(student_ids), "created": created}


def initialize_batch_materials(batch_id: int, user: dict | None = None) -> dict:
    with session() as db:
        result = initialize_batch_materials_in_session(db, int(batch_id), user)
        db.commit()
        return result


def repair_material_catalog(batch_id: int, user: dict | None = None) -> dict:
    """Explicit repair command; archived evidence and submitted versions are never rewritten."""
    with session() as db:
        _batch_for_update(db, int(batch_id))
        rule = active_rule(db, int(batch_id), lock=True)
        definitions = {row.material_code: row for row in rule_items(db, int(rule.id), lock=True)}
        student_ids = list(db.scalars(select(GraduationStudent.id).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
        ).order_by(GraduationStudent.id).with_for_update()).all())
        created = updated = preserved = 0
        for gd_student_id in student_ids:
            created += int(initialize_student_materials_in_session(db, int(gd_student_id), user)["created"])
            rows = list(db.scalars(select(GraduationStudentMaterial).where(
                GraduationStudentMaterial.tenant_id == _tid(),
                GraduationStudentMaterial.gd_student_id == int(gd_student_id),
                GraduationStudentMaterial.is_deleted.is_(False),
            ).with_for_update()).all())
            for material in rows:
                item = definitions.get(material.material_code)
                if not item or material.archive_status in {"FROZEN", "ARCHIVED"}:
                    preserved += 1
                    continue
                if material.current_version_id:
                    preserved += 1
                    continue
                material.rule_id = int(rule.id)
                material.rule_version = int(rule.rule_version)
                material.material_name = item.material_name
                material.biz_stage = item.biz_stage
                material.owner_role = item.owner_role
                material.required_status = _required_status(item)
                material.sensitivity_level = item.sensitivity_level
                material.updated_by = _actor_id(user)
                updated += 1
        db.commit()
        return {
            "batchId": str(batch_id), "ruleId": str(rule.id), "studentCount": len(student_ids),
            "created": created, "updated": updated, "preserved": preserved,
        }


def _assert_owner_role(item: GraduationMaterialItem, user: dict) -> None:
    role = _actor_role(user)
    allowed = _OWNER_ROLES.get(str(item.owner_role or "").upper(), set())
    if role not in allowed:
        raise AppException("NO_PERMISSION", f"材料 {item.material_code} 由 {item.owner_role} 角色提交")


def submission_spec(user: dict, material_code: str, *, gd_student_id: int | None = None) -> dict:
    """Resolve submission metadata from the enabled rule, never from code defaults."""
    with session() as db:
        if gd_student_id is None:
            from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student

            student = resolve_current_gd_student(db, user)
        else:
            student = db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(gd_student_id),
                GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
            )).first()
        if not student or not student.batch_id:
            raise not_found("毕业设计学生档案不存在")
        from app.modules.graduation.services.graduation_scope_service import assert_student_access

        assert_student_access(db, student, "material.submit")
        _, item = rule_item(db, int(student.batch_id), material_code)
        return {
            "materialCode": item.material_code, "materialName": item.material_name,
            "ownerRole": item.owner_role, "bizStage": item.biz_stage,
        }


def _validate_file(item: GraduationMaterialItem, file_obj: FileObject) -> None:
    ext = str(file_obj.ext or "").lower().lstrip(".")
    allowed = {str(value).lower().lstrip(".") for value in (item.allowed_ext_json or [])}
    if ext not in allowed:
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"{item.material_name} 不允许 .{ext or '未知'} 文件")
    if int(file_obj.size_bytes or 0) > int(item.max_size_bytes or 0):
        raise AppException("FILE_TOO_LARGE", f"{item.material_name} 超过允许大小")


def _assert_locked_file_ready(item: GraduationMaterialItem, file_obj: FileObject, user: dict) -> None:
    """Re-check authorization and immutable security facts after SELECT ... FOR UPDATE."""
    _validate_file(item, file_obj)
    require_file_access(str(file_obj.id), user=user, action="bind")
    scan = str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper()
    if not is_downloadable_status(file_obj.status) or scan not in READY_SCAN_STATES:
        raise AppException("FILE_NOT_READY", "文件安全状态已变化，请重新上传或等待扫描完成", http_status=409)
    digest = str(file_obj.sha256 or "")
    if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
        raise AppException("FILE_HASH_MISSING", "文件缺少可信 SHA-256，禁止登记材料版本", http_status=409)


def _ensure_asset(db, student: GraduationStudent, material: GraduationStudentMaterial, user: dict) -> FileAsset:
    code = f"GD:{_tid()}:{student.id}:{material.material_code}"
    row = db.scalars(select(FileAsset).where(
        FileAsset.tenant_id == _tid(), FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False),
    ).with_for_update()).first()
    if row:
        return row
    row = FileAsset(
        tenant_id=_tid(), asset_code=code, title=f"{student.name}·{material.material_name}",
        category_code=material.material_code, owner_type="GRADUATION_STUDENT_MATERIAL",
        owner_id=str(student.id), lifecycle_status="ACTIVE", version_count=0,
        sensitivity_level=material.sensitivity_level, created_by=_actor_id(user),
    )
    db.add(row)
    db.flush()
    return row


def _append_version(db, student: GraduationStudent, material: GraduationStudentMaterial,
                    item: GraduationMaterialItem, file_obj: FileObject, user: dict,
                    *, source_channel: str, source_record_type: str = "MATERIAL_ITEM",
                    source_record_id: str | None = None, comment: str | None = None,
                    approved_override: bool | None = None,
                    binding_metadata: dict[str, Any] | None = None) -> FileVersion:
    asset = _ensure_asset(db, student, material, user)
    duplicate = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
        FileVersion.file_object_id == int(file_obj.id), FileVersion.is_deleted.is_(False),
    ).with_for_update()).first()
    if duplicate:
        if duplicate.is_current:
            return duplicate
        raise AppException("DATA_CONFLICT", "该历史文件已提交过，请上传修改后的新文件")
    current = list(db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
        FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
    ).with_for_update()).all())
    for old in current:
        old.is_current = False
        # Evidence states are immutable. Only an unreviewed submission is superseded.
        if old.status in {"UPLOADED", "READY", "SUBMITTED", "REJECTED"}:
            old.status = "INVALIDATED"
            old.invalidated_at = datetime.utcnow()
            old.invalidated_by = _actor_name(user)
            old.invalid_reason = "毕业设计材料受控重交新版本"
    bindings = list(db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.asset_id == int(asset.id),
        FileBinding.is_current.is_(True), FileBinding.is_deleted.is_(False),
    ).with_for_update()).all())
    for old in bindings:
        old.is_current = False
        old.status = "SUPERSEDED"
        old.invalidated_at = datetime.utcnow()
    latest = int(db.scalar(select(func.max(FileVersion.version_no)).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
    )) or 0)
    auto_approved = bool(approved_override) if approved_override is not None else not bool(item.review_required)
    version = FileVersion(
        tenant_id=_tid(), asset_id=int(asset.id), file_object_id=int(file_obj.id),
        version_no=latest + 1, source_channel=source_channel,
        uploader_user_id=str(_actor_id(user) or file_obj.owner_user_id or "") or None,
        uploader_name_snapshot=_actor_name(user), submit_comment=str(comment or "")[:500] or None,
        status="APPROVED" if auto_approved else "SUBMITTED", is_current=True,
        submitted_at=datetime.utcnow(), created_by=_actor_id(user),
    )
    db.add(version)
    db.flush()
    binding = FileBinding(
        tenant_id=_tid(), file_id=int(file_obj.id), biz_type="GRADUATION_MATERIAL",
        biz_id=str(material.id), relation_type="GRADUATION_MATERIAL_ITEM",
        subject_type="STUDENT", subject_id=str(student.student_id or student.id),
        batch_id=str(student.batch_id), version_no=int(version.version_no),
        is_current=True, status="ACTIVE", asset_id=int(asset.id), version_id=int(version.id),
        module_code=MODULE_CODE, student_id=int(student.student_id or student.id),
        college_id=_safe_int(student.college_id), class_id=_safe_int(student.class_id),
        scope_json={
            "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
            "batchId": str(student.batch_id), "materialCode": material.material_code,
            "materialName": material.material_name, "recordType": source_record_type,
            "recordId": str(source_record_id or material.id), "reviewStatus": version.status,
            **(binding_metadata or {}),
        },
        data_scope_snapshot_json={
            "gdStudentId": str(student.id), "batchId": str(student.batch_id),
            "collegeId": str(student.college_id or ""), "majorId": str(student.major_id or ""),
            "classId": str(student.class_id or ""), "mentorId": str(student.mentor_id or ""),
        },
        created_by=_actor_id(user),
    )
    db.add(binding)
    asset.current_version_id = int(version.id)
    asset.version_count = int(version.version_no)
    material.asset_id = int(asset.id)
    material.current_version_id = int(version.id)
    material.business_status = "APPROVED" if auto_approved else "SUBMITTED"
    material.review_status = "NOT_REQUIRED" if auto_approved else "PENDING"
    material.archive_status = "ELIGIBLE" if auto_approved else "NOT_ARCHIVED"
    material.submitted_at = version.submitted_at
    material.source_record_type = source_record_type
    material.source_record_id = str(source_record_id or material.id)
    material.reject_reason = None
    material.reviewer_user_id = None
    material.reviewer_name = None
    material.reviewed_at = None
    material.updated_by = _actor_id(user)
    material.version = int(material.version or 0) + 1
    file_obj.biz_type = "GRADUATION_MATERIAL"
    file_obj.biz_id = str(material.id)
    file_obj.visibility = "BIZ_SCOPED"
    file_obj.security_level = material.sensitivity_level
    db.flush()
    return version


def submit_material(user: dict, material_code: str, file_id: int, *, gd_student_id: int | None = None,
                    expected_version: int | None, source_channel: str = "MATERIAL_CENTER",
                    source_record_type: str = "MATERIAL_ITEM", source_record_id: str | None = None,
                    comment: str | None = None) -> dict:
    """Append a submission using the enabled rule and public file authorization."""
    if expected_version is None:
        raise AppException("VALIDATION_ERROR", "expectedVersion 不能为空")
    # Central resolver validates tenant, file ownership/binding and current scan state.
    require_file_access(str(file_id), user=user, action="bind")
    assert_file_ready_for_business(str(file_id), user=user)
    with session() as db:
        if gd_student_id is None:
            from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student

            resolved = resolve_current_gd_student(db, user)
            if not resolved:
                raise not_found("毕业设计学生档案不存在")
            gd_student_id = int(resolved.id)
        student = _student_for_update(db, int(gd_student_id))
        from app.modules.graduation.services.graduation_scope_service import assert_student_access

        assert_student_access(db, student, "material.submit")
        batch = _batch_for_update(db, int(student.batch_id))
        if batch.status != "RUNNING":
            raise AppException("DATA_CONFLICT", "仅进行中的批次允许提交材料")
        _assert_not_archived(db, student)
        rule, item = rule_item(db, int(student.batch_id), material_code, lock=True)
        _assert_owner_role(item, user)
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.batch_id == int(student.batch_id),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.material_code == item.material_code,
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
        if not material:
            initialize_student_materials_in_session(db, int(student.id), user)
            material = db.scalars(select(GraduationStudentMaterial).where(
                GraduationStudentMaterial.tenant_id == _tid(),
                GraduationStudentMaterial.gd_student_id == int(student.id),
                GraduationStudentMaterial.material_code == item.material_code,
                GraduationStudentMaterial.is_deleted.is_(False),
            ).with_for_update()).first()
        if not material:
            raise AppException("DATA_CONFLICT", "材料目录初始化失败")
        if int(material.rule_id or 0) != int(rule.id):
            raise AppException("MATERIAL_RULE_VERSION_CONFLICT", "材料实例不属于当前冻结规则，请先执行目录修复")
        if int(material.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "材料状态已变化，请刷新后重试")
        if material.review_status == "PENDING":
            raise AppException("DATA_CONFLICT", "当前版本正在审核，不允许重复提交")
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_obj:
            raise not_found("文件不存在")
        _assert_locked_file_ready(item, file_obj, user)
        version = _append_version(
            db, student, material, item, file_obj, user, source_channel=source_channel,
            source_record_type=source_record_type, source_record_id=source_record_id, comment=comment,
        )
        db.commit()
        return {
            "materialId": str(material.id), "materialCode": material.material_code,
            "assetId": str(material.asset_id), "fileVersionId": str(version.id),
            "versionNo": int(version.version_no), "businessStatus": material.business_status,
            "reviewStatus": material.review_status, "version": int(material.version or 0),
        }


def submit_material_in_session(
    db,
    user: dict,
    gd_student_id: int,
    material_code: str,
    file_id: int,
    *,
    expected_version: int,
    source_channel: str,
    source_record_type: str,
    source_record_id: str,
    comment: str | None = None,
) -> dict:
    """Caller-owned transaction adapter used by authoritative business records."""
    student = _student_for_update(db, int(gd_student_id))
    from app.modules.graduation.services.graduation_scope_service import assert_student_access

    assert_student_access(db, student, "material.submit")
    batch = _batch_for_update(db, int(student.batch_id))
    if batch.status != "RUNNING":
        raise AppException("DATA_CONFLICT", "仅进行中的批次允许提交材料")
    _assert_not_archived(db, student)
    rule, item = rule_item(db, int(student.batch_id), material_code, lock=True)
    _assert_owner_role(item, user)
    material = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.material_code == item.material_code,
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    if not material:
        initialize_student_materials_in_session(db, int(student.id), user)
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.material_code == item.material_code,
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
    if not material:
        raise AppException("DATA_CONFLICT", "材料目录初始化失败")
    if int(material.rule_id or 0) != int(rule.id):
        raise AppException("MATERIAL_RULE_VERSION_CONFLICT", "材料实例不属于当前冻结规则，请先执行目录修复")
    if int(material.version or 0) != int(expected_version):
        raise AppException("APPROVAL_VERSION_CONFLICT", "材料状态已变化，请刷新后重试")
    if material.review_status == "PENDING":
        raise AppException("DATA_CONFLICT", "当前版本正在审核，不允许重复提交")
    file_obj = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(file_id), FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
    if not file_obj:
        raise not_found("文件不存在")
    _assert_locked_file_ready(item, file_obj, user)
    version = _append_version(
        db, student, material, item, file_obj, user, source_channel=source_channel,
        source_record_type=source_record_type, source_record_id=source_record_id, comment=comment,
    )
    return {
        "materialId": str(material.id), "materialCode": material.material_code,
        "assetId": str(material.asset_id), "fileVersionId": str(version.id),
        "versionNo": int(version.version_no), "businessStatus": material.business_status,
        "reviewStatus": material.review_status, "version": int(material.version or 0),
    }


def review_material(material_id: int, expected_file_version_id: int, action: str,
                    comment: str | None, user: dict, *, expected_version: int | None = None) -> dict:
    action = str(action or "").upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if expected_version is None:
        raise AppException("VALIDATION_ERROR", "expectedVersion 不能为空")
    if action == "REJECT" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 个字")
    with session() as db:
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(), GraduationStudentMaterial.id == int(material_id),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
        if not material:
            raise not_found("毕业设计材料不存在")
        student = _student_for_update(db, int(material.gd_student_id))
        from app.modules.graduation.services.graduation_scope_service import assert_student_access

        assert_student_access(db, student, "material.review")
        _assert_not_archived(db, student)
        _, item = rule_item(db, int(student.batch_id), material.material_code, lock=True)
        _enforce_review_permission(user, material.material_code)
        if not item.review_required:
            raise AppException("DATA_CONFLICT", "该材料按批次规则无需人工审核")
        if int(material.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "材料状态已变化，请刷新后重试")
        if material.review_status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核材料可执行审核")
        if not material.current_version_id or int(material.current_version_id) != int(expected_file_version_id):
            raise AppException("APPROVAL_VERSION_CONFLICT", "当前文件版本已变化，请刷新后重试")
        version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.id == int(expected_file_version_id),
            FileVersion.asset_id == int(material.asset_id), FileVersion.is_current.is_(True),
            FileVersion.status == "SUBMITTED", FileVersion.is_deleted.is_(False),
        ).with_for_update()).first()
        if not version:
            raise AppException("DATA_CONFLICT", "当前待审核文件版本不存在")
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(version.file_object_id),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_obj:
            raise AppException("FILE_NOT_READY", "文件已丢失，不能审核", http_status=409)
        assert_file_ready_for_business(str(file_obj.id), user=user)
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
        version.status = target
        material.last_reviewed_version_id = int(version.id)
        material.business_status = "APPROVED" if action == "APPROVE" else "RETURNED"
        material.review_status = "APPROVED" if action == "APPROVE" else "RETURNED"
        material.archive_status = "ELIGIBLE" if action == "APPROVE" else "NOT_ARCHIVED"
        material.reject_reason = str(comment or "").strip() or None
        material.reviewer_user_id = _actor_id(user)
        material.reviewer_name = _actor_name(user)
        material.reviewed_at = datetime.utcnow()
        material.updated_by = _actor_id(user)
        material.version = int(material.version or 0) + 1
        for binding in db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(version.id),
            FileBinding.is_deleted.is_(False),
        ).with_for_update()).all():
            scope = dict(binding.scope_json or {})
            scope["reviewStatus"] = target
            scope["reviewComment"] = str(comment or "").strip()
            binding.scope_json = scope
        db.commit()
        return {
            "materialId": str(material.id), "fileVersionId": str(version.id),
            "reviewStatus": material.review_status, "businessStatus": material.business_status,
            "version": int(material.version or 0),
        }


def review_material_in_session(
    db,
    material_id: int,
    expected_file_version_id: int,
    action: str,
    comment: str | None,
    user: dict,
    *,
    expected_version: int,
) -> dict:
    """Caller-owned transaction adapter for proposal/final record reviews."""
    normalized = str(action or "").upper()
    if normalized not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if normalized == "REJECT" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 个字")
    material = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(), GraduationStudentMaterial.id == int(material_id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    if not material:
        raise not_found("毕业设计材料不存在")
    student = _student_for_update(db, int(material.gd_student_id))
    from app.modules.graduation.services.graduation_scope_service import assert_student_access

    assert_student_access(db, student, "material.review")
    _assert_not_archived(db, student)
    _, item = rule_item(db, int(student.batch_id), material.material_code, lock=True)
    _enforce_review_permission(user, material.material_code)
    if not item.review_required:
        raise AppException("DATA_CONFLICT", "该材料按批次规则无需人工审核")
    if int(material.version or 0) != int(expected_version):
        raise AppException("APPROVAL_VERSION_CONFLICT", "材料状态已变化，请刷新后重试")
    if material.review_status != "PENDING":
        raise AppException("DATA_CONFLICT", "仅待审核材料可执行审核")
    if not material.current_version_id or int(material.current_version_id) != int(expected_file_version_id):
        raise AppException("APPROVAL_VERSION_CONFLICT", "当前文件版本已变化，请刷新后重试")
    version = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.id == int(expected_file_version_id),
        FileVersion.asset_id == int(material.asset_id or 0), FileVersion.is_current.is_(True),
        FileVersion.status == "SUBMITTED", FileVersion.is_deleted.is_(False),
    ).with_for_update()).first()
    if not version:
        raise AppException("DATA_CONFLICT", "当前待审核文件版本不存在")
    file_obj = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(version.file_object_id),
        FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
    if not file_obj:
        raise AppException("FILE_NOT_READY", "文件已丢失，不能审核", http_status=409)
    assert_file_ready_for_business(str(file_obj.id), user=user)
    target = "APPROVED" if normalized == "APPROVE" else "REJECTED"
    version.status = target
    material.last_reviewed_version_id = int(version.id)
    material.business_status = "APPROVED" if normalized == "APPROVE" else "RETURNED"
    material.review_status = "APPROVED" if normalized == "APPROVE" else "RETURNED"
    material.archive_status = "ELIGIBLE" if normalized == "APPROVE" else "NOT_ARCHIVED"
    material.reject_reason = str(comment or "").strip() or None
    material.reviewer_user_id = _actor_id(user)
    material.reviewer_name = _actor_name(user)
    material.reviewed_at = datetime.utcnow()
    material.updated_by = _actor_id(user)
    material.version = int(material.version or 0) + 1
    for binding in db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.version_id == int(version.id),
        FileBinding.is_deleted.is_(False),
    ).with_for_update()).all():
        scope = dict(binding.scope_json or {})
        scope["reviewStatus"] = target
        scope["reviewComment"] = str(comment or "").strip()
        binding.scope_json = scope
    return {
        "materialId": str(material.id), "fileVersionId": str(version.id),
        "reviewStatus": material.review_status, "businessStatus": material.business_status,
        "version": int(material.version or 0),
    }


def register_generated_snapshot(
    gd_student_id: int,
    material_code: str,
    file_id: int,
    *,
    source_record_type: str,
    source_record_id: str,
    source_data_hash: str,
    snapshot_schema_version: str,
    generator_version: str,
    approved: bool,
    user: dict,
) -> dict:
    """Register one generated snapshot through the same immutable version writer."""
    if not re_full_sha256(source_data_hash):
        raise AppException("VALIDATION_ERROR", "sourceDataHash 格式不正确")
    require_file_access(str(file_id), user=user, action="bind")
    assert_file_ready_for_business(str(file_id), user=user)
    with session() as db:
        student = _student_for_update(db, int(gd_student_id))
        from app.modules.graduation.services.graduation_scope_service import assert_student_access

        assert_student_access(db, student, "structured.snapshot")
        _assert_not_archived(db, student)
        _, item = rule_item(db, int(student.batch_id), material_code, lock=True)
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.material_code == item.material_code,
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
        if not material:
            initialize_student_materials_in_session(db, int(student.id), user)
            material = db.scalars(select(GraduationStudentMaterial).where(
                GraduationStudentMaterial.tenant_id == _tid(),
                GraduationStudentMaterial.gd_student_id == int(student.id),
                GraduationStudentMaterial.material_code == item.material_code,
                GraduationStudentMaterial.is_deleted.is_(False),
            ).with_for_update()).first()
        current_version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.id == int(material.current_version_id or 0),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        ).with_for_update()).first()
        current_binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(material.current_version_id or 0),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).with_for_update()).first()
        if current_version and str(current_version.source_channel or "").upper() != "SYSTEM_GENERATED":
            return {
                "status": "PRESERVED_UPLOAD", "materialId": str(material.id),
                "fileVersionId": str(material.current_version_id),
            }
        if current_binding and (current_binding.scope_json or {}).get("sourceDataHash") == source_data_hash:
            return {
                "status": "UNCHANGED", "materialId": str(material.id),
                "fileVersionId": str(material.current_version_id),
            }
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_obj:
            raise not_found("结构化快照文件不存在")
        _assert_locked_file_ready(item, file_obj, user)
        version = _append_version(
            db, student, material, item, file_obj, user,
            source_channel="SYSTEM_GENERATED", source_record_type=source_record_type,
            source_record_id=source_record_id, approved_override=approved,
            comment=f"{source_record_type} 结构化数据快照",
            binding_metadata={
                "sourceDataHash": source_data_hash,
                "snapshotSchemaVersion": snapshot_schema_version,
                "generatorVersion": generator_version,
            },
        )
        db.commit()
        return {
            "status": "CREATED", "materialId": str(material.id),
            "fileVersionId": str(version.id), "versionNo": int(version.version_no),
        }


def adopt_legacy_file_in_session(
    db,
    student: GraduationStudent,
    material_code: str,
    file_id: int,
    *,
    source_record_type: str,
    source_record_id: str,
    user: dict,
    approved: bool,
    binding_metadata: dict | None = None,
) -> dict:
    """Idempotent migration adapter; callers own the page transaction."""
    initialize_student_materials_in_session(db, int(student.id), user)
    _, item = rule_item(db, int(student.batch_id), material_code)
    material = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.material_code == item.material_code,
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    file_obj = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
        FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
    if not file_obj:
        raise not_found("历史附件文件不存在")
    if material.asset_id:
        existing = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(material.asset_id),
            FileVersion.file_object_id == int(file_obj.id), FileVersion.is_deleted.is_(False),
        )).first()
        if existing:
            return {"status": "SKIPPED", "reason": "ALREADY_BOUND", "fileVersionId": str(existing.id)}
    _assert_locked_file_ready(item, file_obj, user)
    version = _append_version(
        db, student, material, item, file_obj, user,
        source_channel="BACKFILL", source_record_type=source_record_type,
        source_record_id=str(source_record_id), approved_override=bool(approved),
        comment="历史 attachments_json 幂等回填", binding_metadata=binding_metadata,
    )
    material.migration_status = "MIGRATED"
    return {"status": "CONVERTED", "fileVersionId": str(version.id), "versionNo": int(version.version_no)}


def re_full_sha256(value: str) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def publish_template_policy(template_id: int, file_id: int, payload: dict, user: dict) -> dict:
    """Publish a template through the same immutable public-file version boundary."""
    with session() as db:
        template = db.scalars(select(GraduationTemplate).where(
            GraduationTemplate.tenant_id == _tid(), GraduationTemplate.id == int(template_id),
            GraduationTemplate.is_deleted.is_(False),
        ).with_for_update()).first()
        if not template:
            raise not_found("毕业设计模板不存在")
        file_obj = db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(), FileObject.id == int(file_id),
            FileObject.is_deleted.is_(False),
        ).with_for_update()).first()
        if not file_obj:
            raise not_found("毕业设计模板文件不存在")
        if str(file_obj.ext or "").lower().lstrip(".") not in {"docx", "pdf", "xlsx", "pptx"}:
            raise AppException("FILE_TYPE_NOT_ALLOWED", "模板仅支持 DOCX、PDF、XLSX、PPTX")
        require_file_access(str(file_obj.id), user=user, action="bind")
        assert_file_ready_for_business(str(file_obj.id), user=user)
        code = f"GD_TEMPLATE:{_tid()}:{template.id}"
        asset = db.scalars(select(FileAsset).where(
            FileAsset.tenant_id == _tid(), FileAsset.asset_code == code,
            FileAsset.is_deleted.is_(False),
        ).with_for_update()).first()
        if not asset:
            asset = FileAsset(
                tenant_id=_tid(), asset_code=code, title=template.name,
                category_code="GRADUATION_TEMPLATE", owner_type="GRADUATION_TEMPLATE",
                owner_id=str(template.id), lifecycle_status="ACTIVE", version_count=0,
                sensitivity_level="NORMAL", created_by=_actor_id(user),
            )
            db.add(asset)
            db.flush()
        current = list(db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        ).with_for_update()).all())
        for old in current:
            old.is_current = False
            if old.status != "ARCHIVED":
                old.status = "INVALIDATED"
                old.invalidated_at = datetime.utcnow()
                old.invalidated_by = _actor_name(user)
                old.invalid_reason = "模板发布新版本"
        for binding in db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.asset_id == int(asset.id),
            FileBinding.is_current.is_(True), FileBinding.is_deleted.is_(False),
        ).with_for_update()).all():
            binding.is_current = False
            binding.status = "SUPERSEDED"
        latest = int(db.scalar(select(func.max(FileVersion.version_no)).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
        )) or 0)
        version = FileVersion(
            tenant_id=_tid(), asset_id=int(asset.id), file_object_id=int(file_obj.id),
            version_no=latest + 1, source_channel="TEMPLATE_PUBLISH",
            uploader_user_id=str(_actor_id(user) or "") or None,
            uploader_name_snapshot=_actor_name(user), submit_comment=template.template_version or "",
            status="APPROVED" if template.status == "ENABLED" else "READY",
            is_current=True, submitted_at=datetime.utcnow(), created_by=_actor_id(user),
        )
        db.add(version)
        db.flush()
        db.add(FileBinding(
            tenant_id=_tid(), file_id=int(file_obj.id), biz_type="GRADUATION_TEMPLATE",
            biz_id=str(template.id), relation_type="GRADUATION_TEMPLATE_SOURCE",
            subject_type="BUSINESS_OBJECT", subject_id=str(template.id),
            version_no=int(version.version_no), is_current=True, status="ACTIVE",
            scope_json={"templateId": str(template.id), "templateType": template.template_type,
                        "templateVersion": template.template_version or ""},
            asset_id=int(asset.id), version_id=int(version.id), module_code=MODULE_CODE,
            created_by=_actor_id(user),
        ))
        asset.current_version_id = int(version.id)
        asset.version_count = int(version.version_no)
        file_obj.biz_type = "GRADUATION_TEMPLATE"
        file_obj.biz_id = str(template.id)
        file_obj.visibility = "BIZ_SCOPED"
        policy = db.scalars(select(GraduationTemplateAssetPolicy).where(
            GraduationTemplateAssetPolicy.tenant_id == _tid(),
            GraduationTemplateAssetPolicy.template_id == int(template.id),
            GraduationTemplateAssetPolicy.is_deleted.is_(False),
        ).with_for_update()).first()
        if not policy:
            policy = GraduationTemplateAssetPolicy(
                tenant_id=_tid(), template_id=int(template.id),
                template_code=str(payload.get("templateCode") or f"GD_TEMPLATE_{template.id}").upper()[:100],
                created_by=_actor_id(user),
            )
            db.add(policy)
        policy.template_code = str(payload.get("templateCode") or policy.template_code).upper()[:100]
        policy.batch_id = _safe_int(payload.get("batchId"))
        policy.college_id = str(payload.get("collegeId") or "")[:64] or None
        policy.major_id = str(payload.get("majorId") or "")[:64] or None
        policy.asset_id = int(asset.id)
        policy.current_version_id = int(version.id)
        policy.variable_schema_json = payload.get("variableSchema") or {"variables": template.variables_json or []}
        policy.scope_json = payload.get("scope") or {"applicableNote": template.applicable_note or ""}
        policy.effective_at = datetime.utcnow()
        policy.enabled = template.status == "ENABLED"
        policy.status = "ENABLED" if policy.enabled else "DRAFT"
        policy.version = int(policy.version or 0) + 1
        db.flush()
        result = {
            "templateId": str(template.id), "assetId": str(asset.id),
            "versionId": str(version.id), "versionNo": int(version.version_no),
            "fileId": str(file_obj.id), "fileName": file_obj.file_name,
            "sha256": file_obj.sha256, "status": version.status,
            "templateCode": policy.template_code, "policyId": str(policy.id),
            "enabled": bool(policy.enabled), "effectiveAt": _iso(policy.effective_at),
            "variableSchema": policy.variable_schema_json, "scope": policy.scope_json,
        }
        db.commit()
        return result


def update_template_policy_status(policy_id: int, enabled: bool, expected_version: int, user: dict) -> dict:
    with session() as db:
        policy = db.scalars(select(GraduationTemplateAssetPolicy).where(
            GraduationTemplateAssetPolicy.tenant_id == _tid(),
            GraduationTemplateAssetPolicy.id == int(policy_id),
            GraduationTemplateAssetPolicy.is_deleted.is_(False),
        ).with_for_update()).first()
        if not policy:
            raise not_found("毕业设计模板策略不存在")
        if int(policy.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "模板策略版本已变化，请刷新后重试")
        if enabled:
            version = db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(), FileVersion.id == int(policy.current_version_id or 0),
                FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
            )).first()
            file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
            if not version or not file_obj:
                raise AppException("DATA_CONFLICT", "模板当前文件版本不存在")
            assert_file_ready_for_business(str(file_obj.id), user=user)
        policy.enabled = bool(enabled)
        policy.status = "ENABLED" if enabled else "DISABLED"
        policy.version = int(policy.version or 0) + 1
        policy.updated_by = _actor_id(user)
        db.commit()
        return {"policyId": str(policy.id), "enabled": bool(policy.enabled),
                "status": policy.status, "version": int(policy.version or 0)}


__all__ = [
    "initialize_batch_materials", "initialize_batch_materials_in_session",
    "initialize_student_materials", "initialize_student_materials_in_session",
    "adopt_legacy_file_in_session",
    "publish_template_policy", "update_template_policy_status",
    "register_generated_snapshot", "repair_material_catalog", "review_material", "review_material_in_session",
    "submission_spec", "submit_material", "submit_material_in_session",
]
