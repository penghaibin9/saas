"""阶段 6：毕业设计材料规则、学生材料项、旧数据回填与模板资产目录。

本服务只编排毕业设计业务语义，文件对象、安全状态、版本、绑定和下载动作仍复用公共文件中心。
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, not_found
from app.models import (
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
    GraduationTopic,
)
from app.models.file import FileAsset, FileBinding, FileObject, FileVersion
from app.models.graduation_material import (
    GraduationMaterialBackfillCheckpoint,
    GraduationMaterialItem,
    GraduationMaterialRule,
    GraduationStudentMaterial,
    GraduationTemplateAssetPolicy,
)
from app.modules.graduation.services import graduation_material_center_service as legacy_center
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access
from app.services import file_service
from app.services.db_service import _iso, _tid, session
from app.services.file_access_service import file_view

MODULE_CODE = "graduation"
MIGRATION_KEY = "GRADUATION_MATERIAL_CENTER_V1"
SYSTEM_SNAPSHOT_CODES = {
    "TASKBOOK", "PROPOSAL_DEFENSE", "GUIDANCE_RECORD", "MIDTERM_REPORT",
    "PLAGIARISM_REPORT", "REVIEW_ATTACHMENT", "DEFENSE_RECORD", "GRADE_MATERIAL",
}

# materialCode, name, stage, ownerRole, required, ext, maxSize, review, archive, sensitivity
MATERIAL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"materialCode": "TOPIC_ATTACHMENT", "materialName": "题目附件", "stage": "TOPIC", "ownerRole": "MENTOR", "required": False, "allowedExtensions": ["pdf", "doc", "docx", "ppt", "pptx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "TASKBOOK", "materialName": "任务书", "stage": "TASKBOOK", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "PROPOSAL_REPORT", "materialName": "开题报告", "stage": "PROPOSAL", "ownerRole": "STUDENT", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "PROPOSAL_DEFENSE", "materialName": "开题答辩材料", "stage": "PROPOSAL", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["pdf", "ppt", "pptx", "doc", "docx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "GUIDANCE_RECORD", "materialName": "指导记录附件", "stage": "GUIDANCE", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf", "doc", "docx", "png", "jpg", "jpeg"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "MIDTERM_REPORT", "materialName": "中期检查材料", "stage": "MIDTERM", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "THESIS_DRAFT", "materialName": "论文初稿", "stage": "FINAL_DRAFT", "ownerRole": "STUDENT", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 100 * 1024 * 1024, "reviewRequired": True, "archiveRequired": False, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "THESIS_FINAL", "materialName": "论文定稿", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 100 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "DESIGN_WORK", "materialName": "设计作品", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["pdf", "zip", "png", "jpg", "jpeg", "mp4"], "maxSizeBytes": 200 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "SOURCE_CODE", "materialName": "源代码或源代码压缩包", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["zip"], "maxSizeBytes": 200 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "WORK_DESCRIPTION", "materialName": "作品说明书", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "PLAGIARISM_REPORT", "materialName": "查重报告", "stage": "PLAGIARISM", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "REVIEW_ATTACHMENT", "materialName": "评阅意见附件", "stage": "REVIEW", "ownerRole": "REVIEWER", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "DEFENSE_RECORD", "materialName": "答辩记录", "stage": "DEFENSE", "ownerRole": "DEFENSE_SECRETARY", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "DEFENSE_SIGNED_SHEET", "materialName": "答辩签字表", "stage": "DEFENSE", "ownerRole": "DEFENSE_SECRETARY", "required": False, "allowedExtensions": ["pdf", "png", "jpg", "jpeg"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "GRADE_MATERIAL", "materialName": "成绩评定材料", "stage": "GRADE", "ownerRole": "ADMIN", "required": True, "allowedExtensions": ["pdf", "xlsx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "TEMPLATE_REFERENCE", "materialName": "毕业设计模板", "stage": "TEMPLATE", "ownerRole": "ADMIN", "required": False, "allowedExtensions": ["docx", "pdf", "xlsx", "pptx"], "maxSizeBytes": 50 * 1024 * 1024, "reviewRequired": False, "archiveRequired": False, "sensitivityLevel": "NORMAL"},
    {"materialCode": "FINAL_ARCHIVE_PACKAGE", "materialName": "最终归档包", "stage": "ARCHIVE", "ownerRole": "SYSTEM", "required": False, "allowedExtensions": ["zip"], "maxSizeBytes": 1024 * 1024 * 1024, "reviewRequired": False, "archiveRequired": False, "sensitivityLevel": "HIGHLY_SENSITIVE"},
)
SPEC_BY_CODE = {item["materialCode"]: item for item in MATERIAL_DEFINITIONS}
STAGE_GROUPS = (
    ("题目与任务书", {"TOPIC", "TASKBOOK"}),
    ("开题材料", {"PROPOSAL"}),
    ("过程指导", {"GUIDANCE"}),
    ("中期检查", {"MIDTERM"}),
    ("论文与成果", {"FINAL_DRAFT", "FINAL_APPROVED"}),
    ("查重与评阅", {"PLAGIARISM", "REVIEW"}),
    ("答辩材料", {"DEFENSE"}),
    ("成绩材料", {"GRADE"}),
    ("归档材料", {"ARCHIVE", "TEMPLATE"}),
)


def _actor_id(user: dict | None) -> int | None:
    from app.services.message_identity import resolve_message_user_id
    return resolve_message_user_id(user or {}) or None


def _actor_name(user: dict | None) -> str:
    actor = user or {}
    return str(actor.get("realName") or actor.get("name") or actor.get("loginName") or "系统")[:100]


def _spec(code: str) -> dict[str, Any]:
    normalized = str(code or "").upper().strip()
    if normalized not in SPEC_BY_CODE:
        raise AppException("VALIDATION_ERROR", "未知毕业设计材料代码")
    return SPEC_BY_CODE[normalized]


def _rule_view(db, rule: GraduationMaterialRule) -> dict:
    items = db.scalars(select(GraduationMaterialItem).where(
        GraduationMaterialItem.tenant_id == _tid(),
        GraduationMaterialItem.rule_id == int(rule.id),
        GraduationMaterialItem.is_deleted.is_(False),
    ).order_by(GraduationMaterialItem.sort_no, GraduationMaterialItem.id)).all()
    return {
        "id": str(rule.id), "batchId": str(rule.batch_id or ""),
        "ruleCode": rule.rule_code, "ruleName": rule.rule_name,
        "ruleVersion": int(rule.rule_version or 1), "status": rule.status,
        "enabled": bool(rule.enabled), "ownerRole": rule.default_owner_role,
        "versionPolicy": rule.version_policy, "archiveRequired": bool(rule.archive_required),
        "sensitivityLevel": rule.sensitivity_level,
        "applicableBatch": str(rule.batch_id or ""),
        "applicableMajor": rule.applicable_major_id or "",
        "applicableTopicType": rule.applicable_topic_type or "",
        "effectiveAt": _iso(rule.effective_at), "sortOrder": 0,
        "allowedExtensions": rule.allowed_ext_json or [],
        "maxSizeBytes": int(rule.max_size_bytes or 0), "maxFileCount": int(rule.max_files or 0),
        "items": [{
            "id": str(item.id), "materialCode": item.material_code,
            "materialName": item.material_name, "stage": item.biz_stage,
            "ownerRole": item.owner_role, "required": bool(item.required),
            "allowedExtensions": item.allowed_ext_json or [],
            "maxSizeBytes": int(item.max_size_bytes or 0), "maxFileCount": int(item.max_files or 1),
            "versionPolicy": item.version_policy, "reviewRequired": bool(item.review_required),
            "archiveRequired": bool(item.archive_required),
            "sensitivityLevel": item.sensitivity_level,
            "applicableBatch": str(rule.batch_id or ""),
            "applicableMajor": item.applicable_major_id or "",
            "applicableTopicType": item.applicable_topic_type or "",
            "sortOrder": int(item.sort_no or 0), "enabled": bool(item.enabled),
        } for item in items],
    }


def ensure_complete_rule(db, batch_id: int | None, user: dict | None = None) -> GraduationMaterialRule:
    """缺少完整目录时创建新规则版本，绝不原地篡改已被历史 Manifest 引用的规则。"""
    active = db.scalars(select(GraduationMaterialRule).where(
        GraduationMaterialRule.tenant_id == _tid(),
        GraduationMaterialRule.batch_id == int(batch_id) if batch_id else GraduationMaterialRule.batch_id.is_(None),
        GraduationMaterialRule.status == "ENABLED",
        GraduationMaterialRule.is_deleted.is_(False),
    ).order_by(GraduationMaterialRule.rule_version.desc()).with_for_update()).first()
    if active:
        codes = set(db.scalars(select(GraduationMaterialItem.material_code).where(
            GraduationMaterialItem.tenant_id == _tid(),
            GraduationMaterialItem.rule_id == int(active.id),
            GraduationMaterialItem.enabled.is_(True),
            GraduationMaterialItem.is_deleted.is_(False),
        )).all())
        if codes.issuperset(SPEC_BY_CODE):
            if not active.enabled:
                active.enabled = True
            return active
    latest = int(db.scalar(select(func.max(GraduationMaterialRule.rule_version)).where(
        GraduationMaterialRule.tenant_id == _tid(),
        GraduationMaterialRule.batch_id == int(batch_id) if batch_id else GraduationMaterialRule.batch_id.is_(None),
        GraduationMaterialRule.rule_code == "GD_MATERIAL_STANDARD",
    )) or 0)
    if active:
        active.status = "DISABLED"
        active.enabled = False
    rule = GraduationMaterialRule(
        tenant_id=_tid(), batch_id=int(batch_id) if batch_id else None,
        rule_code="GD_MATERIAL_STANDARD", rule_name="毕业设计标准材料规则",
        rule_version=latest + 1, status="ENABLED", enabled=True,
        default_owner_role="STUDENT", version_policy="IMMUTABLE_APPEND",
        archive_required=True, sensitivity_level="SENSITIVE",
        applicable_scope_json={"batchId": str(batch_id or ""), "scope": "CURRENT_BATCH"},
        required_items_json=[item["materialCode"] for item in MATERIAL_DEFINITIONS if item["required"]],
        allowed_ext_json=sorted({ext for item in MATERIAL_DEFINITIONS for ext in item["allowedExtensions"]}),
        max_files=1, max_size_bytes=max(item["maxSizeBytes"] for item in MATERIAL_DEFINITIONS),
        effective_at=datetime.utcnow(), remark="阶段6完整毕业设计材料目录",
        created_by=_actor_id(user),
    )
    db.add(rule)
    db.flush()
    for sort_no, spec in enumerate(MATERIAL_DEFINITIONS, start=1):
        db.add(GraduationMaterialItem(
            tenant_id=_tid(), rule_id=int(rule.id), biz_stage=spec["stage"],
            material_code=spec["materialCode"], material_name=spec["materialName"],
            owner_role=spec["ownerRole"], required=spec["required"],
            allowed_ext_json=spec["allowedExtensions"], max_files=1,
            max_size_bytes=spec["maxSizeBytes"], version_policy="IMMUTABLE_APPEND",
            review_required=spec["reviewRequired"], archive_required=spec["archiveRequired"],
            sensitivity_level=spec["sensitivityLevel"], sort_no=sort_no, enabled=True,
            created_by=_actor_id(user),
        ))
    db.flush()
    return rule


def list_rules(batch_id: int | None, user: dict) -> dict:
    with session() as db:
        ensure_complete_rule(db, batch_id, user)
        db.commit()
        rows = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.is_deleted.is_(False),
            or_(GraduationMaterialRule.batch_id == int(batch_id), GraduationMaterialRule.batch_id.is_(None))
            if batch_id else GraduationMaterialRule.batch_id.is_(None),
        ).order_by(GraduationMaterialRule.rule_version.desc())).all()
        return {"items": [_rule_view(db, row) for row in rows], "total": len(rows)}


def _ensure_student_rows(db, student: GraduationStudent, user: dict | None = None) -> list[GraduationStudentMaterial]:
    if not student.batch_id:
        raise AppException("DATA_CONFLICT", "毕业设计学生尚未归属批次")
    rule = ensure_complete_rule(db, int(student.batch_id), user)
    existing = {row.material_code: row for row in db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).all()}
    for spec in MATERIAL_DEFINITIONS:
        row = existing.get(spec["materialCode"])
        required_status = "REQUIRED" if spec["required"] else "OPTIONAL"
        if row is None:
            row = GraduationStudentMaterial(
                tenant_id=_tid(), batch_id=int(student.batch_id), gd_student_id=int(student.id),
                student_id=int(student.student_id) if student.student_id else None,
                topic_id=int(student.topic_id) if student.topic_id else None,
                rule_id=int(rule.id), rule_version=int(rule.rule_version),
                material_code=spec["materialCode"], material_name=spec["materialName"],
                biz_stage=spec["stage"], owner_role=spec["ownerRole"],
                business_status="MISSING", review_status="NOT_SUBMITTED",
                required_status=required_status, archive_status="NOT_ARCHIVED",
                sensitivity_level=spec["sensitivityLevel"], migration_status="NATIVE",
                created_by=_actor_id(user),
            )
            db.add(row)
            existing[spec["materialCode"]] = row
        else:
            row.rule_id = int(rule.id)
            row.rule_version = int(rule.rule_version)
            row.material_name = spec["materialName"]
            row.biz_stage = spec["stage"]
            row.owner_role = spec["ownerRole"]
            row.required_status = required_status
            row.sensitivity_level = spec["sensitivityLevel"]
    db.flush()
    return list(existing.values())


def _canonical_binding_code(binding: FileBinding) -> str:
    raw = str((binding.scope_json or {}).get("materialCode") or "").upper()
    if raw == "PROPOSAL_SNAPSHOT":
        return "PROPOSAL_REPORT"
    if raw.startswith("PROPOSAL_ATTACHMENT"):
        return "PROPOSAL_DEFENSE" if raw.endswith("_01") else raw
    if raw.startswith("FINAL_DRAFT_ATTACHMENT"):
        return "THESIS_DRAFT" if raw.endswith("_01") else raw
    if raw.startswith("FINAL_APPROVED_ATTACHMENT"):
        return "THESIS_FINAL" if raw.endswith("_01") else raw
    return raw or "GRADUATION_MATERIAL"


def _row_for_code(db, student: GraduationStudent, code: str, binding: FileBinding | None = None,
                  user: dict | None = None) -> GraduationStudentMaterial:
    row = db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(student.batch_id),
        GraduationStudentMaterial.gd_student_id == int(student.id),
        GraduationStudentMaterial.material_code == code,
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).first()
    if row:
        return row
    scope = binding.scope_json or {} if binding else {}
    base = next((spec for spec in MATERIAL_DEFINITIONS if code.startswith(spec["materialCode"])), None)
    row = GraduationStudentMaterial(
        tenant_id=_tid(), batch_id=int(student.batch_id), gd_student_id=int(student.id),
        student_id=int(student.student_id) if student.student_id else None,
        topic_id=int(student.topic_id) if student.topic_id else None,
        rule_id=None, rule_version=1, material_code=code,
        material_name=str(scope.get("materialName") or (base or {}).get("materialName") or code)[:200],
        biz_stage=str((base or {}).get("stage") or "OTHER"),
        owner_role=str((base or {}).get("ownerRole") or "STUDENT"),
        business_status="MISSING", review_status="NOT_SUBMITTED",
        required_status="OPTIONAL", archive_status="NOT_ARCHIVED",
        sensitivity_level=str((base or {}).get("sensitivityLevel") or "SENSITIVE"),
        migration_status="BACKFILLED", created_by=_actor_id(user),
    )
    db.add(row)
    db.flush()
    return row


def _apply_binding_to_material(db, student: GraduationStudent, binding: FileBinding,
                               user: dict | None = None) -> GraduationStudentMaterial | None:
    if not binding.version_id or not binding.asset_id:
        return None
    version = db.get(FileVersion, int(binding.version_id))
    file_obj = db.get(FileObject, int(binding.file_id))
    if not version or not file_obj or version.file_object_id != file_obj.id:
        return None
    code = _canonical_binding_code(binding)
    row = _row_for_code(db, student, code, binding, user)
    row.asset_id = int(binding.asset_id)
    if binding.is_current and version.is_current:
        row.current_version_id = int(version.id)
        row.submitted_at = version.submitted_at
        row.source_record_type = str((binding.scope_json or {}).get("recordType") or "BINDING")
        row.source_record_id = str((binding.scope_json or {}).get("recordId") or binding.biz_id)
        review = str((binding.scope_json or {}).get("reviewStatus") or version.status or "SUBMITTED").upper()
        row.review_status = {"APPROVED": "APPROVED", "REJECTED": "RETURNED"}.get(review, "PENDING")
        row.business_status = {"APPROVED": "APPROVED", "REJECTED": "RETURNED"}.get(review, "SUBMITTED")
        row.reject_reason = version.submit_comment if review == "REJECTED" else None
        if review == "APPROVED":
            row.last_reviewed_version_id = int(version.id)
            row.archive_status = "ELIGIBLE"
    return row


def sync_record(record_type: str, record_id: int, user: dict) -> dict:
    normalized = str(record_type or "").upper()
    if normalized not in {"PROPOSAL", "FINAL"}:
        raise AppException("VALIDATION_ERROR", "仅支持开题或成果记录同步")
    model = GraduationProposal if normalized == "PROPOSAL" else GraduationFinal
    with session() as db:
        record = db.scalars(select(model).where(
            model.tenant_id == _tid(), model.id == int(record_id), model.is_deleted.is_(False),
        ).with_for_update()).first()
        if not record:
            raise not_found("毕业设计材料不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(record.gd_student_id),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("毕业设计材料不存在")
        _ensure_student_rows(db, student, user)
        bindings = legacy_center._record_bindings(db, normalized, int(record.id), current_only=None)
        if not bindings:
            legacy_center._adopt_record(
                db, normalized, record, student,
                {**(user or {}), "sourceChannel": "BACKFILL"}, allow_existing=False,
            )
            bindings = legacy_center._record_bindings(db, normalized, int(record.id), current_only=None)
        rows = [row for binding in bindings if (row := _apply_binding_to_material(db, student, binding, user))]
        db.commit()
        return {"recordType": normalized, "recordId": str(record.id), "materialCount": len(rows)}


def _validate_submission_file(db, file_id: int, spec: dict[str, Any]) -> FileObject:
    row = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(file_id), FileObject.is_deleted.is_(False),
    ).with_for_update()).first()
    if not row:
        raise not_found("毕业设计材料不存在")
    ext = str(row.ext or "").lower()
    if ext not in set(spec["allowedExtensions"]):
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"{spec['materialName']}不允许 .{ext or '未知'} 文件")
    if int(row.size_bytes or 0) > int(spec["maxSizeBytes"]):
        raise AppException("FILE_TOO_LARGE", f"{spec['materialName']}超过允许大小")
    legacy_center._require_file_ready(row)
    return row


def _ensure_asset(db, student: GraduationStudent, material: GraduationStudentMaterial) -> FileAsset:
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
        sensitivity_level=material.sensitivity_level, created_by=_actor_id(None),
    )
    db.add(row)
    db.flush()
    return row


def _append_version(db, student: GraduationStudent, material: GraduationStudentMaterial,
                    file_obj: FileObject, user: dict, *, source_channel: str,
                    status: str = "SUBMITTED", source_type: str | None = None,
                    source_id: str | None = None, comment: str | None = None) -> FileVersion:
    asset = _ensure_asset(db, student, material)
    same = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
        FileVersion.file_object_id == int(file_obj.id), FileVersion.is_deleted.is_(False),
    ).with_for_update()).first()
    if same:
        if same.is_current:
            return same
        raise AppException("DATA_CONFLICT", "该历史文件已提交过，请上传修改后的新文件")
    current = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
        FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
    ).with_for_update()).all()
    for old in current:
        old.is_current = False
        old.status = "INVALIDATED"
        old.invalidated_at = datetime.utcnow()
        old.invalidated_by = _actor_name(user)
        old.invalid_reason = "毕业设计材料重交新版本"
    old_bindings = db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.asset_id == int(asset.id),
        FileBinding.is_current.is_(True), FileBinding.is_deleted.is_(False),
    ).with_for_update()).all()
    for old in old_bindings:
        old.is_current = False
        old.status = "SUPERSEDED"
        old.invalidated_at = datetime.utcnow()
    latest = int(db.scalar(select(func.max(FileVersion.version_no)).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
    )) or 0)
    version = FileVersion(
        tenant_id=_tid(), asset_id=int(asset.id), file_object_id=int(file_obj.id),
        version_no=latest + 1, source_channel=source_channel,
        uploader_user_id=str(_actor_id(user) or file_obj.owner_user_id or "") or None,
        uploader_name_snapshot=_actor_name(user), submit_comment=str(comment or "")[:500] or None,
        status=status, is_current=True, submitted_at=datetime.utcnow(), created_by=_actor_id(user),
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
        college_id=legacy_center._safe_int(student.college_id), class_id=legacy_center._safe_int(student.class_id),
        scope_json={
            "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
            "batchId": str(student.batch_id), "materialCode": material.material_code,
            "materialName": material.material_name, "recordType": source_type or "MATERIAL_ITEM",
            "recordId": str(source_id or material.id), "reviewStatus": status,
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
    material.business_status = "APPROVED" if status == "APPROVED" else "SUBMITTED"
    material.review_status = "APPROVED" if status == "APPROVED" else "PENDING"
    material.archive_status = "ELIGIBLE" if status == "APPROVED" else "NOT_ARCHIVED"
    material.submitted_at = version.submitted_at
    material.source_record_type = source_type or "MATERIAL_ITEM"
    material.source_record_id = str(source_id or material.id)
    material.migration_status = "BACKFILLED" if source_channel == "BACKFILL" else "NATIVE"
    file_obj.biz_type = "GRADUATION_MATERIAL"
    file_obj.biz_id = str(material.id)
    file_obj.visibility = "BIZ_SCOPED"
    file_obj.security_level = material.sensitivity_level
    db.flush()
    return version


def submit_material(user: dict, material_code: str, file_id: int, *, expected_version: int | None = None) -> dict:
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise not_found("毕业设计材料不存在")
    spec = _spec(material_code)
    with session() as db:
        current = resolve_current_gd_student(db, user)
        if not current:
            raise not_found("毕业设计材料不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.id == int(current.id),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        _ensure_student_rows(db, student, user)
        material = _row_for_code(db, student, spec["materialCode"], user=user)
        if expected_version is not None and int(material.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "材料状态已变化，请刷新后重试")
        if spec["ownerRole"] not in {"STUDENT", "MENTOR"}:
            raise AppException("DATA_CONFLICT", "该材料由教师或系统生成，学生不能直接提交")
        file_obj = _validate_submission_file(db, int(file_id), spec)
        version = _append_version(
            db, student, material, file_obj, user,
            source_channel="STUDENT_SUBMISSION", status="SUBMITTED",
            comment="学生材料库提交",
        )
        material.reject_reason = None
        material.reviewer_name = None
        material.reviewed_at = None
        material.version = int(material.version or 0) + 1
        db.commit()
        return {
            "materialId": str(material.id), "materialCode": material.material_code,
            "assetId": str(material.asset_id), "fileVersionId": str(version.id),
            "versionNo": int(version.version_no), "businessStatus": material.business_status,
            "reviewStatus": material.review_status, "version": int(material.version or 0),
        }


def review_material(material_id: int, expected_file_version_id: int, action: str,
                    comment: str | None, user: dict) -> dict:
    action = str(action or "").upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于5字")
    with session() as db:
        material = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(), GraduationStudentMaterial.id == int(material_id),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).with_for_update()).first()
        if not material:
            raise not_found("毕业设计材料不存在")
        student = db.get(GraduationStudent, int(material.gd_student_id))
        if not student or student.is_deleted:
            raise not_found("毕业设计材料不存在")
        assert_student_access(db, student, "material.review")
        if not material.current_version_id or int(material.current_version_id) != int(expected_file_version_id):
            raise AppException("DATA_CONFLICT", "材料版本已变化，请刷新后重试")
        version = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.id == int(expected_file_version_id),
            FileVersion.asset_id == int(material.asset_id), FileVersion.is_current.is_(True),
            FileVersion.is_deleted.is_(False),
        ).with_for_update()).first()
        if not version:
            raise AppException("DATA_CONFLICT", "当前文件版本不存在")
        file_obj = db.get(FileObject, int(version.file_object_id))
        legacy_center._require_file_ready(file_obj)
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
        material.version = int(material.version or 0) + 1
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.version_id == int(version.id),
            FileBinding.is_deleted.is_(False),
        ).with_for_update()).all()
        for binding in bindings:
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


def _pdf_snapshot(title: str, fields: list[tuple[str, Any]]) -> bytes:
    output = io.BytesIO()
    try:
        pdfmetrics.getFont("STSong-Light")
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    page = canvas.Canvas(output, pagesize=(595.28, 841.89), pageCompression=1)
    page.setTitle(title)
    page.setAuthor("毕业设计材料中心")
    y = 805
    page.setFont("STSong-Light", 16)
    page.drawString(48, y, title[:60])
    y -= 34
    page.setFont("STSong-Light", 10)
    for label, value in fields:
        text = f"{label}：{'' if value is None else value}"
        chunks = [text[index:index + 54] for index in range(0, len(text), 54)] or [""]
        for chunk in chunks:
            if y < 55:
                page.showPage()
                page.setFont("STSong-Light", 10)
                y = 805
            page.drawString(48, y, chunk)
            y -= 16
        y -= 4
    page.save()
    return output.getvalue()


def _ensure_snapshot(db, student: GraduationStudent, code: str, title: str,
                     fields: list[tuple[str, Any]], source_type: str, source_id: str,
                     user: dict, *, approved: bool = True) -> GraduationStudentMaterial:
    _ensure_student_rows(db, student, user)
    material = _row_for_code(db, student, code, user=user)
    data = _pdf_snapshot(title, fields)
    digest = hashlib.sha256(data).hexdigest()
    if material.current_version_id:
        current = db.get(FileVersion, int(material.current_version_id))
        current_file = db.get(FileObject, int(current.file_object_id)) if current else None
        if current_file and current_file.sha256 == digest:
            return material
    meta = file_service.store_bytes(
        data, f"{student.student_no or student.id}_{code}.pdf",
        biz_type="GRADUATION_MATERIAL", biz_id=str(material.id), mime_type="application/pdf",
        user=user, visibility="BIZ_SCOPED", security_level=material.sensitivity_level,
    )
    file_obj = db.get(FileObject, int(meta["fileId"]))
    if not file_obj:
        raise AppException("DATA_CONFLICT", "结构化材料PDF快照生成失败")
    _append_version(
        db, student, material, file_obj, user, source_channel="SYSTEM_GENERATED",
        status="APPROVED" if approved else "SUBMITTED", source_type=source_type,
        source_id=source_id, comment=f"{source_type}结构化数据快照",
    )
    return material


def ensure_structured_snapshots(db, student: GraduationStudent, user: dict) -> list[str]:
    created: list[str] = []
    taskbook = db.scalars(select(GraduationTaskBook).where(
        GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == int(student.id),
        GraduationTaskBook.is_deleted.is_(False), GraduationTaskBook.status == "CONFIRMED",
    )).first()
    if taskbook:
        _ensure_snapshot(db, student, "TASKBOOK", "毕业设计任务书", [
            ("学生", student.name), ("学号", student.student_no), ("题目", student.topic_title),
            ("任务目标", taskbook.objective), ("任务内容", taskbook.content),
            ("进度计划", taskbook.progress_plan), ("成果要求", taskbook.outcome_requirement),
            ("任务书业务版本", taskbook.taskbook_version), ("确认时间", _iso(taskbook.confirmed_at)),
        ], "TASKBOOK", str(taskbook.id), user)
        created.append("TASKBOOK")
    proposal = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == int(student.id),
        GraduationProposal.status == "APPROVED", GraduationProposal.is_deleted.is_(False),
    ).order_by(GraduationProposal.id.desc())).first()
    if proposal and proposal.defense_result:
        _ensure_snapshot(db, student, "PROPOSAL_DEFENSE", "开题答辩记录", [
            ("学生", student.name), ("题目", student.topic_title),
            ("答辩结果", proposal.defense_result), ("答辩评语", proposal.defense_comment),
            ("答辩时间", _iso(proposal.defense_at)),
        ], "PROPOSAL_DEFENSE", str(proposal.id), user, approved=proposal.defense_result == "PASS")
        created.append("PROPOSAL_DEFENSE")
    guidance = db.scalars(select(GraduationGuidance).where(
        GraduationGuidance.tenant_id == _tid(), GraduationGuidance.gd_student_id == int(student.id),
        GraduationGuidance.is_deleted.is_(False), GraduationGuidance.void_reason.is_(None),
    ).order_by(GraduationGuidance.guidance_date, GraduationGuidance.id)).all()
    if guidance:
        fields: list[tuple[str, Any]] = [("学生", student.name), ("题目", student.topic_title)]
        for index, row in enumerate(guidance, start=1):
            fields.extend([
                (f"第{index}次指导时间", _iso(row.guidance_date)),
                (f"第{index}次指导方式", row.method),
                (f"第{index}次指导内容", row.content),
                (f"第{index}次发现问题", row.issues),
            ])
        _ensure_snapshot(db, student, "GUIDANCE_RECORD", "毕业设计指导记录汇总", fields,
                         "GUIDANCE", str(guidance[-1].id), user)
        created.append("GUIDANCE_RECORD")
    midterm = db.scalars(select(GraduationMidterm).where(
        GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == int(student.id),
        GraduationMidterm.is_deleted.is_(False),
    )).first()
    if midterm and midterm.status in {"CHECKED_PASS", "RECTIFIED_PASS"}:
        _ensure_snapshot(db, student, "MIDTERM_REPORT", "毕业设计中期检查记录", [
            ("学生", student.name), ("检查结论", midterm.conclusion), ("检查意见", midterm.check_comment),
            ("检查人", midterm.check_by), ("检查时间", _iso(midterm.checked_at)),
            ("整改内容", midterm.rectify_content), ("复核意见", midterm.review_comment),
        ], "MIDTERM", str(midterm.id), user)
        created.append("MIDTERM_REPORT")
    plagiarism = db.scalars(select(GraduationPlagiarismCheck).where(
        GraduationPlagiarismCheck.tenant_id == _tid(), GraduationPlagiarismCheck.gd_student_id == int(student.id),
        GraduationPlagiarismCheck.status == "DONE", GraduationPlagiarismCheck.is_deleted.is_(False),
    ).order_by(GraduationPlagiarismCheck.id.desc())).first()
    if plagiarism:
        _ensure_snapshot(db, student, "PLAGIARISM_REPORT", "毕业设计查重结果", [
            ("学生", student.name), ("重复率", plagiarism.rate), ("阈值", plagiarism.threshold),
            ("是否超标", "是" if plagiarism.over_threshold else "否"),
            ("特例状态", plagiarism.dispute_status), ("提交时间", _iso(plagiarism.submit_at)),
        ], "PLAGIARISM", str(plagiarism.id), user,
        approved=not plagiarism.over_threshold or plagiarism.dispute_status == "APPROVED")
        created.append("PLAGIARISM_REPORT")
    reviews = db.scalars(select(GraduationReview).where(
        GraduationReview.tenant_id == _tid(), GraduationReview.gd_student_id == int(student.id),
        GraduationReview.status == "COMPLETED", GraduationReview.is_deleted.is_(False),
    ).order_by(GraduationReview.id)).all()
    if reviews:
        fields = [("学生", student.name)]
        for index, row in enumerate(reviews, start=1):
            fields.extend([(f"评阅人{index}", row.reviewer_name), (f"评阅分{index}", row.score),
                           (f"评阅意见{index}", row.opinion), (f"评阅时间{index}", _iso(row.reviewed_at))])
        _ensure_snapshot(db, student, "REVIEW_ATTACHMENT", "毕业设计评阅意见汇总", fields,
                         "REVIEW", str(reviews[-1].id), user)
        created.append("REVIEW_ATTACHMENT")
    scores = db.scalars(select(GraduationDefenseScore).where(
        GraduationDefenseScore.tenant_id == _tid(), GraduationDefenseScore.gd_student_id == int(student.id),
        GraduationDefenseScore.status == "CONFIRMED", GraduationDefenseScore.is_deleted.is_(False),
    ).order_by(GraduationDefenseScore.round_no, GraduationDefenseScore.id)).all()
    if scores:
        fields = [("学生", student.name), ("答辩组", student.defense_group)]
        for index, row in enumerate(scores, start=1):
            fields.extend([(f"评委{index}", row.judge_name), (f"分数{index}", row.score),
                           (f"评语{index}", row.comment), (f"轮次{index}", row.round_no)])
        _ensure_snapshot(db, student, "DEFENSE_RECORD", "毕业设计答辩记录", fields,
                         "DEFENSE_SCORE", str(scores[-1].id), user)
        created.append("DEFENSE_RECORD")
    grade = db.scalars(select(GraduationGrade).where(
        GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == int(student.id),
        GraduationGrade.status.in_(("REVIEWED", "PUBLISHED")), GraduationGrade.is_deleted.is_(False),
    )).first()
    if grade:
        _ensure_snapshot(db, student, "GRADE_MATERIAL", "毕业设计成绩评定表", [
            ("学生", student.name), ("导师成绩", grade.advisor_score), ("评阅成绩", grade.reviewer_score),
            ("答辩成绩", grade.defense_score), ("综合成绩", grade.total_score),
            ("等级", grade.grade_level), ("状态", grade.status), ("复核人", grade.reviewed_by),
            ("复核时间", _iso(grade.reviewed_at)), ("数据快照SHA-256", grade.source_snapshot_hash),
        ], "GRADE", str(grade.id), user)
        created.append("GRADE_MATERIAL")
    db.flush()
    return created


def _material_file_maps(db, rows: list[GraduationStudentMaterial], user: dict, include_history: bool) -> dict[int, list[dict]]:
    asset_ids = {int(row.asset_id) for row in rows if row.asset_id}
    if not asset_ids:
        return {}
    versions = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id.in_(asset_ids),
        FileVersion.is_deleted.is_(False),
        *([] if include_history else [FileVersion.is_current.is_(True)]),
    ).order_by(FileVersion.asset_id, FileVersion.version_no.desc())).all()
    file_ids = {int(row.file_object_id) for row in versions}
    files = {int(row.id): row for row in db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id.in_(file_ids or {-1}),
        FileObject.is_deleted.is_(False),
    )).all()}
    bindings = db.scalars(select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.version_id.in_({int(v.id) for v in versions} or {-1}),
        FileBinding.module_code == MODULE_CODE, FileBinding.is_deleted.is_(False),
    )).all()
    by_version: dict[int, list[FileBinding]] = {}
    for binding in bindings:
        by_version.setdefault(int(binding.version_id), []).append(binding)
    result: dict[int, list[dict]] = {}
    for version in versions:
        file_obj = files.get(int(version.file_object_id))
        if not file_obj:
            continue
        view = file_view(file_obj, user=user, bindings=by_version.get(int(version.id), []), db=db)
        view.update({
            "assetId": str(version.asset_id), "fileVersionId": str(version.id),
            "versionId": str(version.id), "versionNo": int(version.version_no),
            "versionStatus": version.status, "isCurrent": bool(version.is_current),
            "uploader": version.uploader_name_snapshot or "", "submittedAt": _iso(version.submitted_at),
        })
        result.setdefault(int(version.asset_id), []).append(view)
    return result


def student_library(gd_student_id: int | None, user: dict, *, include_history: bool = True) -> dict:
    with session() as db:
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            current = resolve_current_gd_student(db, user)
            if not current or (gd_student_id and int(gd_student_id) != int(current.id)):
                raise not_found("毕业设计材料库不存在")
            student = db.get(GraduationStudent, int(current.id))
        else:
            if not gd_student_id:
                raise AppException("VALIDATION_ERROR", "缺少毕业设计学生ID")
            student = db.get(GraduationStudent, int(gd_student_id))
            if not student or student.is_deleted or student.tenant_id != _tid():
                raise not_found("毕业设计材料库不存在")
            assert_student_access(db, student, "material.library")
        _ensure_student_rows(db, student, user)
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.module_code == MODULE_CODE,
            FileBinding.is_deleted.is_(False),
            or_(FileBinding.student_id == int(student.student_id or student.id),
                FileBinding.scope_json["gdStudentId"].as_string() == str(student.id)),
        )).all()
        for binding in bindings:
            _apply_binding_to_material(db, student, binding, user)
        rows = db.scalars(select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id == int(student.id),
            GraduationStudentMaterial.is_deleted.is_(False),
        ).order_by(GraduationStudentMaterial.biz_stage, GraduationStudentMaterial.id)).all()
        db.flush()
        file_maps = _material_file_maps(db, list(rows), user, include_history)
        items = []
        for row in rows:
            versions = file_maps.get(int(row.asset_id), []) if row.asset_id else []
            current_file = next((item for item in versions if item["isCurrent"]), None)
            spec = SPEC_BY_CODE.get(row.material_code, {})
            items.append({
                "materialId": str(row.id), "materialCode": row.material_code,
                "materialName": row.material_name, "stage": row.biz_stage,
                "ownerRole": row.owner_role, "required": row.required_status == "REQUIRED",
                "requiredStatus": row.required_status, "businessStatus": row.business_status,
                "reviewStatus": row.review_status, "archiveStatus": row.archive_status,
                "sensitivityLevel": row.sensitivity_level, "assetId": str(row.asset_id or ""),
                "currentVersionId": str(row.current_version_id or ""),
                "currentVersion": current_file, "versions": versions,
                "versionCount": len(versions), "rejectReason": row.reject_reason or "",
                "reviewer": row.reviewer_name or "", "reviewedAt": _iso(row.reviewed_at),
                "submittedAt": _iso(row.submitted_at),
                "archiveRequired": bool(spec.get("archiveRequired", False)),
                "allowedActions": (current_file or {}).get("allowedActions", []),
                "nextAction": "上传材料" if row.business_status == "MISSING" else (
                    "按退回原因重交" if row.business_status == "RETURNED" else (
                        "等待审核" if row.review_status == "PENDING" else "无需处理"
                    )
                ),
            })
        groups = [{"name": name, "items": [item for item in items if item["stage"] in stages]}
                  for name, stages in STAGE_GROUPS]
        db.commit()
        return {
            "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
            "studentName": student.name, "studentNo": student.student_no or "",
            "batchId": str(student.batch_id or ""), "collegeId": str(student.college_id or ""),
            "majorId": str(student.major_id or ""), "classId": str(student.class_id or ""),
            "advisorName": student.advisor_name or "", "topicTitle": student.topic_title or "",
            "items": items, "groups": groups, "total": len(items),
        }


def material_overview(user: dict, *, batch_id: int, page: int = 1, page_size: int = 20,
                      college_id: str = "", major_id: str = "", class_id: str = "",
                      advisor: str = "", keyword: str = "", stage: str = "",
                      material_code: str = "", missing_status: str = "",
                      scan_status: str = "", review_status: str = "",
                      archive_status: str = "") -> dict:
    page = max(1, int(page or 1)); page_size = min(100, max(1, int(page_size or 20)))
    with session() as db:
        scope_ids = set(accessible_student_ids(db, _tid(), batch_id=int(batch_id)))
        stmt = select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.id.in_(scope_ids or {-1}), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
        )
        if college_id: stmt = stmt.where(GraduationStudent.college_id == str(college_id))
        if major_id: stmt = stmt.where(GraduationStudent.major_id == str(major_id))
        if class_id: stmt = stmt.where(GraduationStudent.class_id == str(class_id))
        if advisor: stmt = stmt.where(GraduationStudent.advisor_name.like(f"%{advisor}%"))
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(GraduationStudent.name.like(like), GraduationStudent.student_no.like(like),
                                  GraduationStudent.topic_title.like(like)))
        filtered_ids = list(db.scalars(stmt.with_only_columns(GraduationStudent.id)).all())
        total = len(filtered_ids)
        students = db.scalars(stmt.order_by(GraduationStudent.college_id, GraduationStudent.class_id,
                                            GraduationStudent.student_no, GraduationStudent.id)
                              .offset((page - 1) * page_size).limit(page_size)).all()
        for student in students:
            _ensure_student_rows(db, student, user)
        db.flush()
        material_stmt = select(GraduationStudentMaterial).where(
            GraduationStudentMaterial.tenant_id == _tid(),
            GraduationStudentMaterial.gd_student_id.in_(filtered_ids or {-1}),
            GraduationStudentMaterial.is_deleted.is_(False),
        )
        if stage: material_stmt = material_stmt.where(GraduationStudentMaterial.biz_stage == stage.upper())
        if material_code: material_stmt = material_stmt.where(GraduationStudentMaterial.material_code == material_code.upper())
        if review_status: material_stmt = material_stmt.where(GraduationStudentMaterial.review_status == review_status.upper())
        if archive_status: material_stmt = material_stmt.where(GraduationStudentMaterial.archive_status == archive_status.upper())
        if missing_status.upper() == "MISSING": material_stmt = material_stmt.where(GraduationStudentMaterial.business_status == "MISSING")
        all_materials = db.scalars(material_stmt).all()
        if scan_status:
            version_ids = {int(row.current_version_id) for row in all_materials if row.current_version_id}
            matched_versions = set(db.scalars(select(FileVersion.id).join(
                FileObject, FileObject.id == FileVersion.file_object_id
            ).where(
                FileVersion.tenant_id == _tid(), FileVersion.id.in_(version_ids or {-1}),
                FileObject.scan_status == scan_status.upper(),
            )).all())
            all_materials = [row for row in all_materials if row.current_version_id in matched_versions]
        by_student: dict[int, list[GraduationStudentMaterial]] = {}
        for row in all_materials: by_student.setdefault(int(row.gd_student_id), []).append(row)
        rows = []
        for student in students:
            materials = by_student.get(int(student.id), [])
            required = [item for item in materials if item.required_status == "REQUIRED"]
            missing = sum(item.business_status == "MISSING" for item in required)
            pending = sum(item.review_status == "PENDING" for item in materials)
            returned = sum(item.review_status == "RETURNED" for item in materials)
            approved = sum(item.review_status in {"APPROVED", "NOT_REQUIRED"} for item in required)
            rows.append({
                "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
                "studentNo": student.student_no or "", "studentName": student.name,
                "batchId": str(student.batch_id or ""), "collegeId": str(student.college_id or ""),
                "majorId": str(student.major_id or ""), "classId": str(student.class_id or ""),
                "className": student.class_name or "", "advisorName": student.advisor_name or "",
                "topicTitle": student.topic_title or "", "requiredCount": len(required),
                "missingCount": missing, "pendingReviewCount": pending, "returnedCount": returned,
                "approvedRequiredCount": approved,
                "archiveReady": bool(required and approved == len(required) and missing == pending == returned == 0),
            })
        required_all = [row for row in all_materials if row.required_status == "REQUIRED"]
        missing_students = {int(row.gd_student_id) for row in required_all if row.business_status == "MISSING"}
        pending_students = {int(row.gd_student_id) for row in all_materials if row.review_status == "PENDING"}
        returned_students = {int(row.gd_student_id) for row in all_materials if row.review_status == "RETURNED"}
        archived_students = {int(row.gd_student_id) for row in all_materials if row.archive_status == "ARCHIVED"}
        ready_students = {int(row["gdStudentId"]) for row in rows if row["archiveReady"]}
        db.commit()
        return {
            "summary": {
                "expectedStudents": total,
                "completeStudents": max(0, total - len(missing_students | pending_students | returned_students)),
                "missingStudents": len(missing_students), "scanAbnormalStudents": 0,
                "pendingReviewStudents": len(pending_students), "returnedStudents": len(returned_students),
                "archiveReadyStudents": len(ready_students), "archivedStudents": len(archived_students),
            },
            "items": rows, "total": total, "page": page, "pageSize": page_size,
        }


def _legacy_models():
    return (
        ("PROPOSAL", GraduationProposal, "attachments_json"),
        ("FINAL", GraduationFinal, "attachments_json"),
        ("GUIDANCE", GraduationGuidance, "attachments_json"),
        ("TOPIC", GraduationTopic, "attachments_json"),
    )


def _record_students(db, kind: str, record) -> list[GraduationStudent]:
    if kind in {"PROPOSAL", "FINAL", "GUIDANCE"}:
        row = db.get(GraduationStudent, int(record.gd_student_id))
        return [row] if row and not row.is_deleted and row.tenant_id == _tid() else []
    return list(db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.topic_id == int(record.id),
        GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
    )).all())


def _adopt_legacy_file(db, student: GraduationStudent, kind: str, record, file_id: int,
                       index: int, user: dict, *, dry_run: bool) -> dict:
    code = {
        "GUIDANCE": f"GUIDANCE_ATTACHMENT_{record.id}_{index:02d}",
        "TOPIC": f"TOPIC_ATTACHMENT_{index:02d}",
    }[kind]
    file_obj = db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(), FileObject.id == int(file_id), FileObject.is_deleted.is_(False),
    )).first()
    if not file_obj:
        return {"status": "FAILED", "reason": "FILE_NOT_FOUND", "fileId": str(file_id)}
    try:
        legacy_center._require_file_ready(file_obj)
    except AppException as exc:
        return {"status": "FAILED", "reason": exc.code, "fileId": str(file_id), "message": exc.message}
    if dry_run:
        return {"status": "WOULD_CONVERT", "fileId": str(file_id), "materialCode": code}
    _ensure_student_rows(db, student, user)
    material = _row_for_code(db, student, code, user=user)
    existing = db.scalars(select(FileVersion).where(
        FileVersion.tenant_id == _tid(), FileVersion.asset_id == material.asset_id,
        FileVersion.file_object_id == int(file_obj.id), FileVersion.is_deleted.is_(False),
    )).first() if material.asset_id else None
    if existing:
        return {"status": "SKIPPED", "reason": "ALREADY_BOUND", "fileId": str(file_id)}
    _append_version(db, student, material, file_obj, {**user, "sourceChannel": "BACKFILL"},
                    source_channel="BACKFILL", status="APPROVED" if kind == "TOPIC" else "SUBMITTED",
                    source_type=kind, source_id=str(record.id), comment="旧附件幂等回填")
    return {"status": "CONVERTED", "fileId": str(file_id), "materialCode": code}


def backfill_legacy(user: dict, *, page_size: int = 200, cursor_model: str = "PROPOSAL",
                    cursor_id: int = 0, dry_run: bool = False) -> dict:
    page_size = min(1000, max(1, int(page_size or 200)))
    wanted = str(cursor_model or "PROPOSAL").upper()
    model_map = {kind: (model, field) for kind, model, field in _legacy_models()}
    if wanted not in model_map:
        raise AppException("VALIDATION_ERROR", "未知回填游标类型")
    model, field = model_map[wanted]
    with session() as db:
        checkpoint = db.scalars(select(GraduationMaterialBackfillCheckpoint).where(
            GraduationMaterialBackfillCheckpoint.tenant_id == _tid(),
            GraduationMaterialBackfillCheckpoint.migration_key == MIGRATION_KEY,
            GraduationMaterialBackfillCheckpoint.is_deleted.is_(False),
        ).with_for_update()).first()
        if not checkpoint:
            checkpoint = GraduationMaterialBackfillCheckpoint(
                tenant_id=_tid(), migration_key=MIGRATION_KEY, status="PENDING",
                page_size=page_size, cursor_model=wanted, cursor_id=max(0, int(cursor_id or 0)),
                created_by=_actor_id(user),
            )
            db.add(checkpoint); db.flush()
        rows = db.scalars(select(model).where(
            model.tenant_id == _tid(), model.id > max(0, int(cursor_id or 0)),
            model.is_deleted.is_(False),
        ).order_by(model.id).limit(page_size)).all()
        results: list[dict] = []
        converted = skipped = failed = 0
        checkpoint.status = "RUNNING"; checkpoint.dry_run = bool(dry_run)
        checkpoint.cursor_model = wanted; checkpoint.started_at = checkpoint.started_at or datetime.utcnow()
        for record in rows:
            file_ids = legacy_center._normalize_file_ids(getattr(record, field, None) or [])
            students = _record_students(db, wanted, record)
            if not students:
                results.append({"model": wanted, "recordId": str(record.id), "status": "FAILED", "reason": "STUDENT_NOT_FOUND"})
                failed += 1; checkpoint.cursor_id = int(record.id); continue
            if wanted in {"PROPOSAL", "FINAL"}:
                if not file_ids and wanted == "FINAL":
                    results.append({"model": wanted, "recordId": str(record.id), "status": "SKIPPED", "reason": "EMPTY_ATTACHMENTS"})
                    skipped += 1; checkpoint.cursor_id = int(record.id); continue
                try:
                    if dry_run:
                        legacy_center._load_ready_files(db, file_ids, required=wanted == "FINAL")
                        status = "WOULD_CONVERT"
                    else:
                        bindings = legacy_center._record_bindings(db, wanted, int(record.id), current_only=None)
                        if bindings:
                            status = "SKIPPED"
                        else:
                            legacy_center._adopt_record(db, wanted, record, students[0],
                                                        {**user, "sourceChannel": "BACKFILL"}, allow_existing=False)
                            bindings = legacy_center._record_bindings(db, wanted, int(record.id), current_only=None)
                            for binding in bindings: _apply_binding_to_material(db, students[0], binding, user)
                            status = "CONVERTED"
                    if status in {"CONVERTED", "WOULD_CONVERT"}: converted += 1
                    else: skipped += 1
                    results.append({"model": wanted, "recordId": str(record.id), "status": status})
                except Exception as exc:
                    failed += 1
                    results.append({"model": wanted, "recordId": str(record.id), "status": "FAILED", "reason": getattr(exc, "code", type(exc).__name__), "message": str(exc)[:300]})
            else:
                if not file_ids:
                    skipped += 1
                    results.append({"model": wanted, "recordId": str(record.id), "status": "SKIPPED", "reason": "EMPTY_ATTACHMENTS"})
                for student in students:
                    for index, file_id in enumerate(file_ids, start=1):
                        item = _adopt_legacy_file(db, student, wanted, record, file_id, index, user, dry_run=dry_run)
                        results.append({"model": wanted, "recordId": str(record.id), "gdStudentId": str(student.id), **item})
                        converted += item["status"] in {"CONVERTED", "WOULD_CONVERT"}
                        skipped += item["status"] == "SKIPPED"
                        failed += item["status"] == "FAILED"
            checkpoint.cursor_id = int(record.id)
        checkpoint.scanned_rows = int(checkpoint.scanned_rows or 0) + len(rows)
        checkpoint.converted_rows = int(checkpoint.converted_rows or 0) + converted
        checkpoint.skipped_rows = int(checkpoint.skipped_rows or 0) + skipped
        checkpoint.failed_rows = int(checkpoint.failed_rows or 0) + failed
        checkpoint.diff_report_json = {"lastPage": results[-100:], "dryRun": bool(dry_run)}
        checkpoint.status = "PARTIAL_FAILED" if failed else ("COMPLETED" if len(rows) < page_size else "RUNNING")
        checkpoint.finished_at = datetime.utcnow() if checkpoint.status in {"COMPLETED", "PARTIAL_FAILED"} else None
        db.commit()
        return {
            "migrationKey": MIGRATION_KEY, "cursorModel": wanted,
            "nextCursorId": int(checkpoint.cursor_id or 0), "pageSize": page_size,
            "dryRun": bool(dry_run), "scanned": len(rows), "converted": converted,
            "skipped": skipped, "failed": failed, "status": checkpoint.status,
            "hasMore": len(rows) == page_size, "differences": results,
        }


def publish_template_policy(template_id: int, file_id: int, payload: dict, user: dict) -> dict:
    with session() as db:
        template = db.scalars(select(GraduationTemplate).where(
            GraduationTemplate.tenant_id == _tid(), GraduationTemplate.id == int(template_id),
            GraduationTemplate.is_deleted.is_(False),
        )).first()
        if not template:
            raise not_found("毕业设计模板不存在")
        file_obj = db.get(FileObject, int(file_id))
        if not file_obj or file_obj.tenant_id != _tid() or file_obj.is_deleted:
            raise not_found("毕业设计模板文件不存在")
        if str(file_obj.ext or "").lower() not in {"docx", "pdf", "xlsx", "pptx"}:
            raise AppException("FILE_TYPE_NOT_ALLOWED", "模板仅支持 DOCX、PDF、XLSX、PPTX")
        legacy_center._require_file_ready(file_obj)
    published = legacy_center.publish_template_asset(int(template_id), int(file_id), user)
    with session() as db:
        policy = db.scalars(select(GraduationTemplateAssetPolicy).where(
            GraduationTemplateAssetPolicy.tenant_id == _tid(),
            GraduationTemplateAssetPolicy.template_id == int(template_id),
            GraduationTemplateAssetPolicy.is_deleted.is_(False),
        ).with_for_update()).first()
        code = str(payload.get("templateCode") or f"GD_TEMPLATE_{template_id}").upper()[:100]
        if not policy:
            policy = GraduationTemplateAssetPolicy(
                tenant_id=_tid(), template_id=int(template_id), template_code=code,
                created_by=_actor_id(user),
            )
            db.add(policy)
        policy.template_code = code
        policy.batch_id = int(payload["batchId"]) if str(payload.get("batchId") or "").isdigit() else None
        policy.college_id = str(payload.get("collegeId") or "")[:64] or None
        policy.major_id = str(payload.get("majorId") or "")[:64] or None
        policy.asset_id = int(published["assetId"])
        policy.current_version_id = int(published["versionId"])
        policy.variable_schema_json = payload.get("variableSchema") or {"variables": template.variables_json or []}
        policy.scope_json = payload.get("scope") or {"applicableNote": template.applicable_note or ""}
        policy.effective_at = datetime.utcnow()
        policy.enabled = template.status == "ENABLED"
        policy.status = "ENABLED" if policy.enabled else "DRAFT"
        policy.version = int(policy.version or 0) + 1
        db.commit()
        return {**published, "templateCode": policy.template_code, "policyId": str(policy.id),
                "enabled": bool(policy.enabled), "effectiveAt": _iso(policy.effective_at),
                "variableSchema": policy.variable_schema_json, "scope": policy.scope_json}


def template_catalog(user: dict, *, batch_id: int | None = None) -> dict:
    with session() as db:
        stmt = select(GraduationTemplateAssetPolicy).where(
            GraduationTemplateAssetPolicy.tenant_id == _tid(),
            GraduationTemplateAssetPolicy.is_deleted.is_(False),
        )
        if batch_id:
            stmt = stmt.where(or_(GraduationTemplateAssetPolicy.batch_id == int(batch_id),
                                  GraduationTemplateAssetPolicy.batch_id.is_(None)))
        policies = db.scalars(stmt.order_by(GraduationTemplateAssetPolicy.template_code)).all()
        template_ids = {int(row.template_id) for row in policies}
        templates = {int(row.id): row for row in db.scalars(select(GraduationTemplate).where(
            GraduationTemplate.tenant_id == _tid(), GraduationTemplate.id.in_(template_ids or {-1}),
            GraduationTemplate.is_deleted.is_(False),
        )).all()}
        versions = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(),
            FileVersion.asset_id.in_({int(row.asset_id) for row in policies if row.asset_id} or {-1}),
            FileVersion.is_deleted.is_(False),
        ).order_by(FileVersion.asset_id, FileVersion.version_no.desc())).all()
        files = {int(row.id): row for row in db.scalars(select(FileObject).where(
            FileObject.tenant_id == _tid(),
            FileObject.id.in_({int(v.file_object_id) for v in versions} or {-1}),
            FileObject.is_deleted.is_(False),
        )).all()}
        by_asset: dict[int, list[dict]] = {}
        for version in versions:
            file_obj = files.get(int(version.file_object_id))
            if file_obj:
                by_asset.setdefault(int(version.asset_id), []).append({
                    "versionId": str(version.id), "versionNo": int(version.version_no),
                    "isCurrent": bool(version.is_current), "status": version.status,
                    "fileId": str(file_obj.id), "fileName": file_obj.file_name,
                    "sizeBytes": file_obj.size_bytes, "sha256": file_obj.sha256,
                    "scanStatus": file_obj.scan_status,
                })
        items = []
        for policy in policies:
            template = templates.get(int(policy.template_id))
            if not template: continue
            items.append({
                "policyId": str(policy.id), "templateId": str(template.id),
                "templateCode": policy.template_code, "templateName": template.name,
                "templateType": template.template_type, "currentVersionId": str(policy.current_version_id or ""),
                "batchId": str(policy.batch_id or ""), "collegeId": policy.college_id or "",
                "majorId": policy.major_id or "", "enabled": bool(policy.enabled),
                "status": policy.status, "effectiveAt": _iso(policy.effective_at),
                "variableSchema": policy.variable_schema_json or {}, "scope": policy.scope_json or {},
                "versions": by_asset.get(int(policy.asset_id), []) if policy.asset_id else [],
            })
        return {"items": items, "total": len(items)}
