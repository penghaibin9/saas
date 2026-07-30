"""阶段 6：毕业设计材料、版本、审核、Manifest 与归档包公共中心。

权威链：
GraduationMaterialRule/Item -> FileAsset -> FileVersion -> FileObject
                                           -> FileBinding
GraduationProposal/GraduationFinal.attachments_json 仅保留旧接口兼容与回填来源。
ArchiveManifest/ArchiveManifestItem 冻结备案时的真实版本、哈希与安全结论。
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
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
)
from app.models.file import (
    ArchiveManifest,
    ArchiveManifestItem,
    FileAsset,
    FileBinding,
    FileObject,
    FileVersion,
)
from app.models.graduation_material import GraduationMaterialItem, GraduationMaterialRule
from app.modules.graduation.services.graduation_command_service import _conflict_guard
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.modules.graduation.services.graduation_scope_service import (
    accessible_student_ids,
    assert_student_access,
)
from app.services import file_service
from app.services.db_service import _iso, _tid, session
from app.services.file_content_security import is_downloadable_status
from app.services.file_scan_constants import READY_SCAN_STATES, SCAN_NOT_REQUIRED
from app.services.storage import get_backend

MODULE_CODE = "graduation"
ARCHIVE_TYPE = "GRADUATION_STUDENT_ARCHIVE"
ARCHIVE_TARGET = "GRADUATION_ARCHIVE"
ACTIVE_MANIFEST_STATUS = {"PREPARED", "FROZEN", "PACKAGED"}
READY_VERSION_STATUS = {"READY", "SUBMITTED", "APPROVED", "ARCHIVED"}
DEFAULT_ALLOWED_EXT = ["pdf", "doc", "docx", "zip"]
MAX_FILE_SIZE = 50 * 1024 * 1024

STAGE_PROPOSAL = "PROPOSAL"
STAGE_FINAL_DRAFT = "FINAL_DRAFT"
STAGE_FINAL_APPROVED = "FINAL_APPROVED"
STAGE_TEMPLATE = "TEMPLATE"


def _actor_id(user: dict | None = None) -> int | None:
    from app.services.message_identity import resolve_message_user_id

    return resolve_message_user_id(user or get_current_user_ctx() or {}) or None


def _actor_name(user: dict | None = None) -> str:
    actor = user or get_current_user_ctx() or {}
    return str(actor.get("realName") or actor.get("name") or actor.get("loginName") or "系统")[:100]


def _safe_int(value) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _require_student_user(user: dict) -> None:
    if str((user or {}).get("userType") or "").upper() != "STUDENT":
        raise no_permission("该接口仅学生本人可用")


def _file_ready(row: FileObject | None) -> bool:
    if row is None:
        return False
    scan = str(row.scan_status or SCAN_NOT_REQUIRED).upper()
    return bool(is_downloadable_status(row.status) and scan in READY_SCAN_STATES and row.sha256)


def _require_file_ready(row: FileObject | None) -> None:
    if not _file_ready(row):
        raise AppException(
            "DATA_CONFLICT",
            "材料仍在安全扫描、扫描失败或已被隔离，不能提交、审核或归档",
            details={
                "fileId": str(getattr(row, "id", "") or ""),
                "status": getattr(row, "status", None),
                "scanStatus": getattr(row, "scan_status", None),
            },
        )
    if not row.sha256 or len(str(row.sha256)) != 64:
        raise AppException("DATA_CONFLICT", "材料缺少有效 SHA-256，不能进入公共版本链")


def _normalize_file_ids(values) -> list[int]:
    result: list[int] = []
    for raw in values or []:
        value = raw.get("fileId") or raw.get("id") if isinstance(raw, dict) else raw
        text = str(value or "").strip()
        if not text.isdigit():
            continue
        number = int(text)
        if number not in result:
            result.append(number)
    return result


def _load_ready_files(db, values, *, required: bool, allowed_ext: list[str] | None = None,
                      max_files: int = 10, max_size_bytes: int = MAX_FILE_SIZE) -> list[FileObject]:
    ids = _normalize_file_ids(values)
    if required and not ids:
        raise AppException("VALIDATION_ERROR", "请先上传毕业设计材料附件再提交")
    if len(ids) > max(1, int(max_files or 1)):
        raise AppException("VALIDATION_ERROR", f"本次最多提交 {max_files} 个文件")
    if not ids:
        return []
    rows = {int(row.id): row for row in db.scalars(select(FileObject).where(
        FileObject.tenant_id == _tid(),
        FileObject.id.in_(ids),
        FileObject.is_deleted.is_(False),
    ).with_for_update()).all()}
    if len(rows) != len(ids):
        raise AppException("VALIDATION_ERROR", "存在无效、已删除或跨租户的毕业设计材料")
    allowed = {str(ext).lower().lstrip(".") for ext in (allowed_ext or DEFAULT_ALLOWED_EXT)}
    ordered: list[FileObject] = []
    for file_id in ids:
        row = rows[file_id]
        ext = str(row.ext or "").lower()
        if ext not in allowed:
            raise AppException(
                "FILE_TYPE_NOT_ALLOWED",
                f"材料格式不允许：.{ext or '未知'}",
                details={"allowed": sorted(allowed)},
            )
        if int(row.size_bytes or 0) > int(max_size_bytes or MAX_FILE_SIZE):
            raise AppException("FILE_TOO_LARGE", "材料超过当前毕业设计规则允许的大小")
        _require_file_ready(row)
        ordered.append(row)
    return ordered


def _rule_items(db, rule_id: int) -> list[GraduationMaterialItem]:
    return list(db.scalars(select(GraduationMaterialItem).where(
        GraduationMaterialItem.tenant_id == _tid(),
        GraduationMaterialItem.rule_id == int(rule_id),
        GraduationMaterialItem.is_deleted.is_(False),
    ).order_by(GraduationMaterialItem.sort_no, GraduationMaterialItem.id)).all())


def _rule_row(db, rule: GraduationMaterialRule) -> dict:
    return {
        "id": str(rule.id),
        "batchId": str(rule.batch_id or ""),
        "ruleCode": rule.rule_code,
        "ruleName": rule.rule_name,
        "ruleVersion": int(rule.rule_version or 1),
        "status": rule.status,
        "allowedExt": rule.allowed_ext_json or DEFAULT_ALLOWED_EXT,
        "maxFiles": int(rule.max_files or 10),
        "maxSizeBytes": int(rule.max_size_bytes or MAX_FILE_SIZE),
        "applicableScope": rule.applicable_scope_json or {},
        "requiredItems": rule.required_items_json or [],
        "remark": rule.remark or "",
        "items": [{
            "id": str(item.id), "bizStage": item.biz_stage,
            "materialCode": item.material_code, "materialName": item.material_name,
            "required": bool(item.required), "reviewRequired": bool(item.review_required),
            "sortNo": int(item.sort_no or 0),
            "allowedExt": item.allowed_ext_json or rule.allowed_ext_json or DEFAULT_ALLOWED_EXT,
            "maxFiles": int(item.max_files or 1),
            "maxSizeBytes": int(item.max_size_bytes or rule.max_size_bytes or MAX_FILE_SIZE),
            "description": item.description or "",
        } for item in _rule_items(db, rule.id)],
    }


def ensure_default_rule(db, batch_id: int | None) -> GraduationMaterialRule:
    query = select(GraduationMaterialRule).where(
        GraduationMaterialRule.tenant_id == _tid(),
        GraduationMaterialRule.status == "ENABLED",
        GraduationMaterialRule.is_deleted.is_(False),
    )
    if batch_id:
        rule = db.scalars(query.where(
            GraduationMaterialRule.batch_id == int(batch_id),
        ).order_by(GraduationMaterialRule.rule_version.desc())).first()
        if rule:
            return rule
    rule = db.scalars(query.where(
        GraduationMaterialRule.batch_id.is_(None),
    ).order_by(GraduationMaterialRule.rule_version.desc())).first()
    if rule:
        return rule

    rule = GraduationMaterialRule(
        tenant_id=_tid(), batch_id=int(batch_id) if batch_id else None,
        rule_code="GD_MATERIAL_STANDARD", rule_name="毕业设计标准材料规则",
        rule_version=1, status="ENABLED",
        applicable_scope_json={"batchId": str(batch_id or ""), "scope": "CURRENT_BATCH"},
        required_items_json=["PROPOSAL_SNAPSHOT", "FINAL_DRAFT_ATTACHMENT", "FINAL_APPROVED_ATTACHMENT"],
        allowed_ext_json=DEFAULT_ALLOWED_EXT, max_files=10, max_size_bytes=MAX_FILE_SIZE,
        remark="阶段6默认规则；学校可按批次创建新版本并启用",
        created_by=_actor_id(),
    )
    db.add(rule)
    db.flush()
    defaults = [
        (STAGE_PROPOSAL, "PROPOSAL_SNAPSHOT", "开题报告正文快照", True, ["txt"], 1),
        (STAGE_PROPOSAL, "PROPOSAL_ATTACHMENT", "开题报告附件", False, DEFAULT_ALLOWED_EXT, 10),
        (STAGE_FINAL_DRAFT, "FINAL_DRAFT_ATTACHMENT", "毕业设计初稿", True, DEFAULT_ALLOWED_EXT, 10),
        (STAGE_FINAL_APPROVED, "FINAL_APPROVED_ATTACHMENT", "毕业设计定稿", True, DEFAULT_ALLOWED_EXT, 10),
        (STAGE_TEMPLATE, "TEMPLATE_SOURCE", "毕业设计模板源文件", False,
         ["pdf", "doc", "docx", "xlsx", "txt"], 1),
    ]
    for index, (stage, code, name, required, allowed, max_files) in enumerate(defaults, start=1):
        db.add(GraduationMaterialItem(
            tenant_id=_tid(), rule_id=int(rule.id), biz_stage=stage,
            material_code=code, material_name=name, required=required,
            review_required=stage != STAGE_TEMPLATE, sort_no=index,
            allowed_ext_json=allowed, max_files=max_files,
            max_size_bytes=MAX_FILE_SIZE, created_by=_actor_id(),
        ))
    db.flush()
    return rule


def list_rules(batch_id: int | None = None) -> dict:
    with session() as db:
        if batch_id:
            ensure_default_rule(db, int(batch_id))
            db.commit()
        query = select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.is_deleted.is_(False),
        )
        if batch_id:
            query = query.where(
                (GraduationMaterialRule.batch_id == int(batch_id))
                | GraduationMaterialRule.batch_id.is_(None)
            )
        rows = db.scalars(query.order_by(
            GraduationMaterialRule.status.desc(),
            GraduationMaterialRule.rule_version.desc(),
            GraduationMaterialRule.id.desc(),
        )).all()
        return {"items": [_rule_row(db, row) for row in rows], "total": len(rows)}


def create_rule(payload: dict, user: dict) -> dict:
    code = str(payload.get("ruleCode") or "").strip().upper()
    name = str(payload.get("ruleName") or "").strip()
    if not code or not name:
        raise AppException("VALIDATION_ERROR", "规则编码和名称不能为空")
    batch_id = _safe_int(payload.get("batchId"))
    with session() as db:
        latest = int(db.scalar(select(func.max(GraduationMaterialRule.rule_version)).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == batch_id if batch_id else GraduationMaterialRule.batch_id.is_(None),
            GraduationMaterialRule.rule_code == code,
        )) or 0)
        rule = GraduationMaterialRule(
            tenant_id=_tid(), batch_id=batch_id, rule_code=code, rule_name=name,
            rule_version=latest + 1, status="DRAFT",
            applicable_scope_json=payload.get("applicableScope") or {},
            required_items_json=payload.get("requiredItems") or [],
            allowed_ext_json=payload.get("allowedExt") or DEFAULT_ALLOWED_EXT,
            max_files=max(1, min(50, int(payload.get("maxFiles") or 10))),
            max_size_bytes=max(1024, min(200 * 1024 * 1024, int(payload.get("maxSizeBytes") or MAX_FILE_SIZE))),
            remark=str(payload.get("remark") or "")[:500] or None,
            created_by=_actor_id(user),
        )
        db.add(rule)
        db.flush()
        items = payload.get("items") or []
        if not items:
            source = ensure_default_rule(db, batch_id)
            items = _rule_row(db, source)["items"]
        for index, raw in enumerate(items, start=1):
            stage = str(raw.get("bizStage") or "").upper()
            material_code = str(raw.get("materialCode") or "").upper().strip()
            material_name = str(raw.get("materialName") or "").strip()
            if stage not in {STAGE_PROPOSAL, STAGE_FINAL_DRAFT, STAGE_FINAL_APPROVED, STAGE_TEMPLATE}:
                raise AppException("VALIDATION_ERROR", f"材料阶段不支持：{stage}")
            if not material_code or not material_name:
                raise AppException("VALIDATION_ERROR", "材料项编码和名称不能为空")
            db.add(GraduationMaterialItem(
                tenant_id=_tid(), rule_id=int(rule.id), biz_stage=stage,
                material_code=material_code, material_name=material_name,
                required=bool(raw.get("required", True)),
                review_required=bool(raw.get("reviewRequired", True)),
                sort_no=int(raw.get("sortNo") or index),
                allowed_ext_json=raw.get("allowedExt") or rule.allowed_ext_json,
                max_files=max(1, min(50, int(raw.get("maxFiles") or 1))),
                max_size_bytes=max(1024, min(200 * 1024 * 1024,
                    int(raw.get("maxSizeBytes") or rule.max_size_bytes))),
                description=str(raw.get("description") or "")[:500] or None,
                created_by=_actor_id(user),
            ))
        db.commit()
        return _rule_row(db, rule)


def activate_rule(rule_id: int, user: dict) -> dict:
    with session() as db:
        rule = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.id == int(rule_id),
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).first()
        if not rule:
            raise not_found("材料规则不存在")
        if rule.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档规则不可启用")
        peers = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == rule.batch_id,
            GraduationMaterialRule.status == "ENABLED",
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).all()
        for peer in peers:
            if peer.id != rule.id:
                peer.status = "DISABLED"
                peer.updated_by = _actor_id(user)
        rule.status = "ENABLED"
        rule.updated_by = _actor_id(user)
        db.commit()
        return _rule_row(db, rule)


def _family(record_type: str, final_type: str | None = None) -> str:
    rt = str(record_type).upper()
    if rt == "PROPOSAL":
        return STAGE_PROPOSAL
    if rt == "FINAL":
        return STAGE_FINAL_APPROVED if str(final_type or "") == "定稿" else STAGE_FINAL_DRAFT
    raise AppException("VALIDATION_ERROR", "未知毕业设计材料类型")


def _asset_code(student: GraduationStudent, family: str, slot: str) -> str:
    return f"GD_MATERIAL:{_tid()}:{int(student.id)}:{family}:{slot}"


def _ensure_asset(db, student: GraduationStudent, family: str, slot: str, title: str) -> FileAsset:
    code = _asset_code(student, family, slot)
    asset = db.scalars(select(FileAsset).where(
        FileAsset.tenant_id == _tid(), FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False),
    ).with_for_update()).first()
    if not asset:
        asset = FileAsset(
            tenant_id=_tid(), asset_code=code, title=title,
            category_code=f"GRADUATION_{family}", owner_type="GRADUATION_STUDENT_MATERIAL",
            owner_id=str(student.id), lifecycle_status="ACTIVE", version_count=0,
            sensitivity_level="SENSITIVE", created_by=_actor_id(),
        )
        db.add(asset)
        db.flush()
    else:
        asset.title = title
    return asset


def _invalidate_family(db, student: GraduationStudent, family: str, user: dict) -> None:
    assets = db.scalars(select(FileAsset).where(
        FileAsset.tenant_id == _tid(),
        FileAsset.owner_type == "GRADUATION_STUDENT_MATERIAL",
        FileAsset.owner_id == str(student.id),
        FileAsset.category_code == f"GRADUATION_{family}",
        FileAsset.is_deleted.is_(False),
    ).with_for_update()).all()
    now = datetime.utcnow()
    for asset in assets:
        versions = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        ).with_for_update()).all()
        version_ids: list[int] = []
        for version in versions:
            version.is_current = False
            if version.status not in {"APPROVED", "ARCHIVED"}:
                version.status = "INVALIDATED"
            version.invalidated_at = now
            version.invalidated_by = _actor_name(user)
            version.invalid_reason = "学生提交毕业设计新版本"
            version_ids.append(int(version.id))
        if version_ids:
            bindings = db.scalars(select(FileBinding).where(
                FileBinding.tenant_id == _tid(), FileBinding.version_id.in_(version_ids),
                FileBinding.is_current.is_(True), FileBinding.is_deleted.is_(False),
            ).with_for_update()).all()
            for binding in bindings:
                binding.is_current = False
                binding.status = "SUPERSEDED"
                binding.invalidated_at = now


def _record_bindings(db, record_type: str, record_id: int, *, current_only: bool | None = None):
    relation = "GRADUATION_PROPOSAL_MATERIAL" if str(record_type).upper() == "PROPOSAL" else "GRADUATION_FINAL_MATERIAL"
    query = select(FileBinding).where(
        FileBinding.tenant_id == _tid(), FileBinding.module_code == MODULE_CODE,
        FileBinding.biz_type == "GRADUATION_MATERIAL", FileBinding.biz_id == str(record_id),
        FileBinding.relation_type == relation, FileBinding.is_deleted.is_(False),
    )
    if current_only is not None:
        query = query.where(FileBinding.is_current.is_(bool(current_only)))
    return list(db.scalars(query.order_by(FileBinding.version_no, FileBinding.id)).all())


def _proposal_snapshot_bytes(record: GraduationProposal, student: GraduationStudent) -> bytes:
    text = "\n".join([
        "毕业设计开题报告正文快照",
        f"学生：{student.name}",
        f"学号：{student.student_no or ''}",
        f"课题：{student.topic_title or ''}",
        f"版本：{record.version or 'v1'}",
        f"提交时间：{_iso(record.submit_at) or ''}",
        "",
        "【选题背景】",
        record.background or "",
        "",
        "【研究方案与进度】",
        record.plan or "",
        "",
        "【预期成果】",
        record.outcome or "",
    ])
    return text.encode("utf-8")


def _store_proposal_snapshot(db, record: GraduationProposal, student: GraduationStudent, user: dict) -> FileObject:
    safe_student = re.sub(r"[\\/:*?\"<>|]+", "_", student.name or "学生")
    meta = file_service.store_bytes(
        _proposal_snapshot_bytes(record, student),
        f"开题报告_{safe_student}_{record.version or 'v1'}_正文快照.txt",
        biz_type="GRADUATION_MATERIAL", biz_id=None, mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE", db=db,
    )
    row = db.get(FileObject, int(meta["fileId"]))
    if not row or row.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "开题正文快照写入失败")
    row.biz_type = "GRADUATION_MATERIAL"
    row.biz_id = str(record.id)
    return row


def _final_snapshot_bytes(record: GraduationFinal, student: GraduationStudent) -> bytes:
    text = "\n".join([
        "毕业设计成果提交记录快照（历史无原始附件兼容）",
        f"学生：{student.name}",
        f"学号：{student.student_no or ''}",
        f"课题：{student.topic_title or ''}",
        f"成果类型：{record.final_type or ''}",
        f"业务版本：{record.version or 'v1'}",
        f"提交时间：{_iso(record.submit_at) or ''}",
        f"业务状态：{record.status or ''}",
    ])
    return text.encode("utf-8")


def _store_final_snapshot(db, record: GraduationFinal, student: GraduationStudent, user: dict) -> FileObject:
    safe_student = re.sub(r"[\\/:*?"<>|]+", "_", student.name or "学生")
    meta = file_service.store_bytes(
        _final_snapshot_bytes(record, student),
        f"成果提交记录_{safe_student}_{record.final_type or '成果'}_{record.version or 'v1'}.txt",
        biz_type="GRADUATION_MATERIAL", biz_id=None, mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE", db=db,
    )
    row = db.get(FileObject, int(meta["fileId"]))
    if not row or row.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "成果提交记录快照写入失败")
    row.biz_type = "GRADUATION_MATERIAL"
    row.biz_id = str(record.id)
    return row


def _status_for_record(status: str) -> str:
    return {"APPROVED": "APPROVED", "REJECTED": "REJECTED"}.get(str(status), "SUBMITTED")


def _adopt_record(db, record_type: str, record, student: GraduationStudent, user: dict,
                  *, allow_existing: bool = True) -> list[dict]:
    existing_bindings = _record_bindings(db, record_type, int(record.id), current_only=None)
    if allow_existing and existing_bindings:
        return _version_views(db, existing_bindings, student_mode=False)

    family = _family(record_type, getattr(record, "final_type", None))
    rule = ensure_default_rule(db, student.batch_id)
    items = {item.material_code: item for item in _rule_items(db, rule.id)}
    attachment_ids = _normalize_file_ids(record.attachments_json or [])
    rule_key = "PROPOSAL_ATTACHMENT" if family == STAGE_PROPOSAL else (
        "FINAL_APPROVED_ATTACHMENT" if family == STAGE_FINAL_APPROVED else "FINAL_DRAFT_ATTACHMENT"
    )
    item_rule = items.get(rule_key)
    files = _load_ready_files(
        db, attachment_ids,
        required=False,
        allowed_ext=(item_rule.allowed_ext_json if item_rule else rule.allowed_ext_json),
        max_files=(item_rule.max_files if item_rule else rule.max_files),
        max_size_bytes=(item_rule.max_size_bytes if item_rule else rule.max_size_bytes),
    )
    materials: list[tuple[str, str, FileObject]] = []
    if family == STAGE_PROPOSAL:
        snapshot = _store_proposal_snapshot(db, record, student, user)
        # snapshot 已在独立写会话提交并从该会话分离；旧业务事务处于 MySQL
        # REPEATABLE READ 时不得再次 db.get，否则可能得到 None。
        _require_file_ready(snapshot)
        materials.append(("PROPOSAL_SNAPSHOT", "开题报告正文快照", snapshot))
        for index, file_obj in enumerate(files, start=1):
            materials.append((f"PROPOSAL_ATTACHMENT_{index:02d}", f"开题附件{index}", file_obj))
    else:
        prefix = "FINAL_APPROVED_ATTACHMENT" if family == STAGE_FINAL_APPROVED else "FINAL_DRAFT_ATTACHMENT"
        label = "定稿" if family == STAGE_FINAL_APPROVED else "初稿"
        for index, file_obj in enumerate(files, start=1):
            materials.append((f"{prefix}_{index:02d}", f"{label}附件{index}", file_obj))
        if not files and str((user or {}).get("sourceChannel") or "").upper() == "BACKFILL":
            snapshot = _store_final_snapshot(db, record, student, user)
            _require_file_ready(snapshot)
            materials.append((f"{prefix}_LEGACY_RECORD", f"{label}历史提交记录快照", snapshot))
    if not materials:
        raise AppException("DATA_CONFLICT", "毕业设计记录没有可进入公共版本链的真实文件")

    _invalidate_family(db, student, family, user)
    relation = "GRADUATION_PROPOSAL_MATERIAL" if str(record_type).upper() == "PROPOSAL" else "GRADUATION_FINAL_MATERIAL"
    review_status = str(record.status or "PENDING_REVIEW")
    created: list[FileBinding] = []
    for sort_no, (material_code, material_name, file_obj) in enumerate(materials, start=1):
        _require_file_ready(file_obj)
        asset = _ensure_asset(db, student, family, material_code, material_name)
        latest_no = int(db.scalar(select(func.max(FileVersion.version_no)).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
            FileVersion.is_deleted.is_(False),
        )) or 0)
        version = FileVersion(
            tenant_id=_tid(), asset_id=int(asset.id), file_object_id=int(file_obj.id),
            version_no=latest_no + 1,
            source_channel="BACKFILL" if str((user or {}).get("sourceChannel") or "") == "BACKFILL"
                           else "STUDENT_SUBMISSION",
            uploader_user_id=str(_actor_id(user) or file_obj.owner_user_id or "") or None,
            uploader_name_snapshot=_actor_name(user),
            submit_comment=f"{material_name}·{getattr(record, 'version', '')}",
            status=_status_for_record(review_status), is_current=True,
            submitted_at=record.submit_at or datetime.utcnow(), created_by=_actor_id(user),
        )
        db.add(version)
        db.flush()
        binding = FileBinding(
            tenant_id=_tid(), file_id=int(file_obj.id), biz_type="GRADUATION_MATERIAL",
            biz_id=str(record.id), relation_type=relation, subject_type="STUDENT",
            subject_id=str(student.student_id or student.id), batch_id=str(student.batch_id or "") or None,
            version_no=int(version.version_no), is_current=True, status="ACTIVE",
            scope_json={
                "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
                "batchId": str(student.batch_id or ""), "recordType": str(record_type).upper(),
                "recordId": str(record.id), "materialCode": material_code,
                "materialName": material_name, "reviewStatus": review_status,
                "sortNo": sort_no,
            },
            asset_id=int(asset.id), version_id=int(version.id), module_code=MODULE_CODE,
            student_id=int(student.student_id or student.id),
            college_id=_safe_int(student.college_id), class_id=_safe_int(student.class_id),
            data_scope_snapshot_json={
                "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
                "batchId": str(student.batch_id or ""), "collegeId": str(student.college_id or ""),
                "classId": str(student.class_id or ""), "mentorId": str(student.mentor_id or ""),
            },
            created_by=_actor_id(user),
        )
        db.add(binding)
        db.flush()
        asset.current_version_id = int(version.id)
        asset.version_count = max(int(asset.version_count or 0), int(version.version_no))
        file_obj.biz_type = "GRADUATION_MATERIAL"
        file_obj.biz_id = str(record.id)
        file_obj.visibility = "BIZ_SCOPED"
        file_obj.security_level = "SENSITIVE"
        created.append(binding)
    db.flush()
    return _version_views(db, created, student_mode=False)


def _version_views(db, bindings: list[FileBinding], *, student_mode: bool) -> list[dict]:
    result: list[dict] = []
    for binding in bindings:
        version = db.get(FileVersion, int(binding.version_id)) if binding.version_id else None
        file_obj = db.get(FileObject, int(binding.file_id))
        if not version or not file_obj or file_obj.is_deleted:
            continue
        scope = binding.scope_json or {}
        ready = _file_ready(file_obj)
        base = "/api/v1/mobile/graduation/material-center/files" if student_mode \
            else "/api/v1/graduation/material-center/files"
        result.append({
            "bindingId": str(binding.id), "assetId": str(binding.asset_id or ""),
            "versionId": str(version.id), "versionNo": int(version.version_no or 1),
            "isCurrent": bool(version.is_current and binding.is_current),
            "versionStatus": version.status, "bindingStatus": binding.status,
            "materialCode": scope.get("materialCode") or "GRADUATION_MATERIAL",
            "materialName": scope.get("materialName") or file_obj.file_name,
            "recordType": scope.get("recordType"), "recordId": scope.get("recordId"),
            "reviewStatus": scope.get("reviewStatus"),
            "fileId": str(file_obj.id), "fileName": file_obj.file_name,
            "sizeBytes": file_obj.size_bytes, "sha256": file_obj.sha256,
            "status": file_obj.status, "scanStatus": file_obj.scan_status,
            "readyForBusiness": ready,
            "allowedActions": ["viewMetadata"] + (["preview", "download"] if ready else []),
            "previewUrl": f"{base}/{file_obj.id}/download" if ready else None,
            "downloadUrl": f"{base}/{file_obj.id}/download" if ready else None,
            "submittedAt": _iso(version.submitted_at),
            "sortNo": int(scope.get("sortNo") or 0),
        })
    return sorted(result, key=lambda row: (row.get("sortNo", 0), row.get("versionNo", 0), row.get("fileId", "")))


def record_versions(record_type: str, record_id: int, *, student_mode: bool = False,
                    include_history: bool = True) -> list[dict]:
    with session() as db:
        bindings = _record_bindings(db, record_type, int(record_id), current_only=None if include_history else True)
        return _version_views(db, bindings, student_mode=student_mode)


def _require_reviewable(db, record_type: str, record, student: GraduationStudent, user: dict) -> list[dict]:
    bindings = _record_bindings(db, record_type, int(record.id), current_only=True)
    if not bindings:
        _adopt_record(db, record_type, record, student, {**(user or {}), "sourceChannel": "BACKFILL"})
        bindings = _record_bindings(db, record_type, int(record.id), current_only=True)
    if not bindings:
        raise AppException("DATA_CONFLICT", "当前记录尚未形成公共文件版本，不能审核")
    views = _version_views(db, bindings, student_mode=False)
    if not views or any(not item["readyForBusiness"] for item in views):
        raise AppException("DATA_CONFLICT", "当前材料版本未通过安全门禁，不能审核")
    for binding in bindings:
        version = db.get(FileVersion, int(binding.version_id)) if binding.version_id else None
        if not version or not version.is_current or version.status not in {"READY", "SUBMITTED", "REJECTED"}:
            raise AppException("DATA_CONFLICT", "材料版本已变化，请刷新详情后重新审核")
    return views


def _mark_review_status(db, record_type: str, record_id: int, target: str) -> None:
    bindings = _record_bindings(db, record_type, int(record_id), current_only=True)
    for binding in bindings:
        version = db.get(FileVersion, int(binding.version_id)) if binding.version_id else None
        if version:
            version.status = target
        scope = dict(binding.scope_json or {})
        scope["reviewStatus"] = target
        binding.scope_json = scope


@_conflict_guard
def submit_proposal(user: dict, body: dict) -> dict:
    _require_student_user(user)
    background = str((body or {}).get("background") or "").strip()
    plan = str((body or {}).get("plan") or "").strip()
    outcome = str((body or {}).get("outcome") or "").strip()
    if not background:
        raise AppException("VALIDATION_ERROR", "选题背景不能为空")
    if not plan:
        raise AppException("VALIDATION_ERROR", "研究方案与进度不能为空")
    with session() as db:
        resolved = resolve_current_gd_student(db, user)
        if not resolved:
            raise not_found("未找到你的毕业设计档案，请联系毕设管理员")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(resolved.id), GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        if not student.topic_id:
            raise AppException("DATA_CONFLICT", "请先完成选题确认后再提交开题报告")
        if (student.eligibility_status or "PENDING") == "UNQUALIFIED":
            raise AppException("DATA_CONFLICT", "资格不合格，不能提交开题报告")
        taskbook = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == student.id,
            GraduationTaskBook.is_deleted.is_(False), GraduationTaskBook.status == "CONFIRMED",
        ).limit(1)).first()
        if not taskbook:
            raise AppException("DATA_CONFLICT", "请先确认任务书后再提交开题报告")
        existing = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == student.id,
            GraduationProposal.is_deleted.is_(False),
        ).order_by(GraduationProposal.id.desc()).with_for_update()).all()
        latest = existing[0] if existing else None
        if latest and latest.status == "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "已有待审阅的开题报告，请等待指导教师批阅")
        if latest and latest.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "开题报告已通过，无需重复提交")
        rule = ensure_default_rule(db, student.batch_id)
        item = next((x for x in _rule_items(db, rule.id) if x.material_code == "PROPOSAL_ATTACHMENT"), None)
        files = _load_ready_files(
            db, (body or {}).get("attachments") or [], required=False,
            allowed_ext=item.allowed_ext_json if item else rule.allowed_ext_json,
            max_files=item.max_files if item else rule.max_files,
            max_size_bytes=item.max_size_bytes if item else rule.max_size_bytes,
        )
        version_label = f"v{len(existing) + 1}"
        proposal = GraduationProposal(
            tenant_id=_tid(), gd_student_id=student.id, version=version_label,
            is_resubmit=bool(existing), submit_at=datetime.now(timezone.utc),
            background=background, plan=plan, outcome=outcome,
            attachments_json=[int(row.id) for row in files], status="PENDING_REVIEW",
            active_key=f"pending:{student.id}", created_by=_actor_id(user),
        )
        db.add(proposal)
        db.flush()
        versions = _adopt_record(db, "PROPOSAL", proposal, student, user, allow_existing=False)
        from app.modules.graduation.services import graduation_service as legacy
        legacy._audit(
            db, "PROPOSAL", proposal.id,
            "提交开题报告-" + ("重交" if existing else "首次"),
            f"{student.name} {version_label}", "", "PENDING_REVIEW",
        )
        from app.modules.graduation.services import graduation_todo_helper as todo
        todo.push_proposal_todo(db, proposal, student)
        db.commit()
        return {
            "id": str(proposal.id), "version": version_label,
            "isResubmit": bool(existing), "status": "PENDING_REVIEW",
            "fileVersionCount": len({row["versionId"] for row in versions}), "currentSafeVersions": versions,
        }


@_conflict_guard
def submit_final(user: dict, body: dict) -> dict:
    _require_student_user(user)
    final_type = str((body or {}).get("finalType") or "初稿")
    if final_type not in {"初稿", "定稿"}:
        raise AppException("VALIDATION_ERROR", "成果类型必须是 初稿/定稿")
    with session() as db:
        resolved = resolve_current_gd_student(db, user)
        if not resolved:
            raise not_found("未找到你的毕业设计档案，请联系毕设管理员")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(resolved.id), GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
        ).with_for_update()).first()
        assert_student_access(db, student, "final.submit")
        if student.stage not in ("FINAL_CHECK", "DEFENSE"):
            raise AppException("DATA_CONFLICT", "当前阶段不可提交成果（须进入成果检查阶段）")
        if not student.topic_id:
            raise AppException("DATA_CONFLICT", "请先完成选题确认后再提交成果")
        if (student.eligibility_status or "PENDING") == "UNQUALIFIED":
            raise AppException("DATA_CONFLICT", "资格不合格，不能提交成果")
        midterm = db.scalars(select(GraduationMidterm).where(
            GraduationMidterm.tenant_id == _tid(), GraduationMidterm.gd_student_id == student.id,
            GraduationMidterm.is_deleted.is_(False),
        ).order_by(GraduationMidterm.id.desc()).with_for_update()).first()
        from app.modules.graduation.services import graduation_service as legacy
        if not legacy.midterm_allows_final_submit(midterm):
            raise AppException("DATA_CONFLICT", "中期检查未通过或尚未完成，不能提交成果")
        existing = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == student.id,
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).with_for_update()).all()
        pending = next((row for row in existing if row.status == "PENDING_REVIEW"), None)
        if pending:
            same_ids = _normalize_file_ids(pending.attachments_json or []) == _normalize_file_ids(
                (body or {}).get("attachments") or [])
            if pending.final_type == final_type and same_ids:
                versions = _version_views(db, _record_bindings(db, "FINAL", pending.id, current_only=True),
                                          student_mode=True)
                return {
                    "id": str(pending.id), "finalType": pending.final_type,
                    "version": pending.version, "status": pending.status,
                    "fileVersionCount": len({row["versionId"] for row in versions}), "currentSafeVersions": versions,
                }
            raise AppException("DATA_CONFLICT", "已有待审阅的成果，请等待指导教师批阅")
        if final_type == "定稿":
            if not any(row.final_type == "初稿" and row.status == "APPROVED" for row in existing):
                raise AppException("DATA_CONFLICT", "请先提交初稿并通过后再提交定稿")
            if any(row.final_type == "定稿" and row.status == "APPROVED" for row in existing):
                raise AppException("DATA_CONFLICT", "定稿已通过，无需重复提交")
        family = STAGE_FINAL_APPROVED if final_type == "定稿" else STAGE_FINAL_DRAFT
        rule = ensure_default_rule(db, student.batch_id)
        rule_code = "FINAL_APPROVED_ATTACHMENT" if family == STAGE_FINAL_APPROVED else "FINAL_DRAFT_ATTACHMENT"
        item = next((x for x in _rule_items(db, rule.id) if x.material_code == rule_code), None)
        files = _load_ready_files(
            db, (body or {}).get("attachments") or [], required=True,
            allowed_ext=item.allowed_ext_json if item else rule.allowed_ext_json,
            max_files=item.max_files if item else rule.max_files,
            max_size_bytes=item.max_size_bytes if item else rule.max_size_bytes,
        )
        same_type = [row for row in existing if row.final_type == final_type]
        version_label = f"v{len(same_type) + 1}"
        final = GraduationFinal(
            tenant_id=_tid(), gd_student_id=student.id, final_type=final_type,
            version=version_label, submit_at=datetime.now(timezone.utc),
            plagiarism_rate=None, plagiarism_status="未检测",
            attachments_json=[int(row.id) for row in files], status="PENDING_REVIEW",
            active_key=f"pending:{student.id}", created_by=_actor_id(user),
        )
        db.add(final)
        db.flush()
        versions = _adopt_record(db, "FINAL", final, student, user, allow_existing=False)
        legacy._audit(
            db, "FINAL", final.id, f"提交成果-{final_type}",
            f"{student.name} {final_type} {version_label}", "", "PENDING_REVIEW",
        )
        from app.modules.graduation.services import graduation_todo_helper as todo
        todo.push_final_todo(db, final, student)
        db.commit()
        return {
            "id": str(final.id), "finalType": final_type, "version": version_label,
            "status": "PENDING_REVIEW", "fileVersionCount": len({row["versionId"] for row in versions}),
            "currentSafeVersions": [dict(row, previewUrl=row["previewUrl"], downloadUrl=row["downloadUrl"])
                                    for row in versions],
        }


def proposal_detail(proposal_id: int) -> dict:
    from app.modules.graduation.services import graduation_service as legacy
    detail = legacy.get_proposal_detail(proposal_id)
    with session() as db:
        bindings = _record_bindings(db, "PROPOSAL", int(proposal_id), current_only=True)
        versions = _version_views(db, bindings, student_mode=False)
    attachments = [
        {
            "fileId": item["fileId"], "fileName": item["fileName"],
            "sizeBytes": item["sizeBytes"], "scanStatus": item["scanStatus"],
            "readyForBusiness": item["readyForBusiness"],
            "allowedActions": item["allowedActions"],
            "previewUrl": item["previewUrl"], "downloadUrl": item["downloadUrl"],
        }
        for item in versions
        if str(item.get("materialCode") or "").startswith("PROPOSAL_ATTACHMENT_")
    ]
    detail.update({
        "currentSafeVersions": versions,
        "currentVersionCount": len({item["versionId"] for item in versions}),
        "reviewReady": bool(versions and all(item["readyForBusiness"] for item in versions)),
        "migrationRequired": not bool(versions),
        "attachments": len(attachments), "attachmentsList": attachments,
    })
    return detail


def final_detail(final_id: int) -> dict:
    from app.modules.graduation.services import graduation_service as legacy
    detail = legacy.get_final_detail(final_id)
    with session() as db:
        bindings = _record_bindings(db, "FINAL", int(final_id), current_only=True)
        versions = _version_views(db, bindings, student_mode=False)
    attachments = [
        {
            "fileId": item["fileId"], "fileName": item["fileName"],
            "sizeBytes": item["sizeBytes"], "scanStatus": item["scanStatus"],
            "readyForBusiness": item["readyForBusiness"],
            "allowedActions": item["allowedActions"],
            "previewUrl": item["previewUrl"], "downloadUrl": item["downloadUrl"],
        }
        for item in versions
        if str(item.get("materialCode") or "").startswith("PROPOSAL_ATTACHMENT_")
    ]
    detail.update({
        "currentSafeVersions": versions,
        "currentVersionCount": len({item["versionId"] for item in versions}),
        "reviewReady": bool(versions and all(item["readyForBusiness"] for item in versions)),
        "migrationRequired": not bool(versions),
        "attachments": len(attachments), "attachmentsList": attachments,
    })
    return detail


@_conflict_guard
def review_proposal(proposal_id: int, action: str, comment: str | None, user: dict) -> dict:
    action = str(action or "").upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        proposal = db.scalars(select(GraduationProposal).where(
            GraduationProposal.id == int(proposal_id), GraduationProposal.tenant_id == _tid(),
            GraduationProposal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not proposal:
            raise not_found("开题材料不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == proposal.gd_student_id, GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, student, "proposal.review")
        if proposal.status in {"APPROVED", "REJECTED"}:
            raise AppException("DATA_CONFLICT", "该开题已被处理，请刷新")
        safe_versions = _require_reviewable(db, "PROPOSAL", proposal, student, user)
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
        before = proposal.status
        proposal.status = target
        proposal.active_key = None
        proposal.reviewer = _actor_name(user)
        proposal.review_comment = str(comment or "").strip()
        proposal.review_time = datetime.now(timezone.utc)
        proposal.version = proposal.version or "v1"
        _mark_review_status(db, "PROPOSAL", proposal.id, target)
        from app.modules.graduation.services import graduation_service as legacy
        legacy._audit(
            db, "PROPOSAL", proposal.id,
            "批阅开题-" + ("通过" if action == "APPROVE" else "驳回"),
            str(comment or "").strip(), before, target,
        )
        from app.modules.graduation.services import graduation_todo_helper as todo
        todo.todo_done(db, biz_id=proposal.id, todo_type=todo.TODO_PROPOSAL)
        if action == "APPROVE" and student.stage in {"TOPIC_SELECTING", "TASKBOOK_CONFIRM"}:
            taskbook = db.scalars(select(GraduationTaskBook).where(
                GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == student.id,
                GraduationTaskBook.is_deleted.is_(False), GraduationTaskBook.status == "CONFIRMED",
            ).limit(1)).first()
            student.stage = "GUIDING" if taskbook else "TASKBOOK_CONFIRM"
        db.commit()
        return {
            "id": str(proposal.id), "status": target,
            "statusLabel": "已通过" if target == "APPROVED" else "已驳回",
            "reviewedVersionIds": [item["versionId"] for item in safe_versions],
        }


@_conflict_guard
def review_final(final_id: int, action: str, comment: str | None, user: dict) -> dict:
    action = str(action or "").upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len(str(comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.id == int(final_id), GraduationFinal.tenant_id == _tid(),
            GraduationFinal.is_deleted.is_(False),
        ).with_for_update()).first()
        if not final:
            raise not_found("成果不存在")
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == final.gd_student_id, GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        assert_student_access(db, student, "final.review")
        if final.status in {"APPROVED", "REJECTED"}:
            raise AppException("DATA_CONFLICT", "该成果已被处理，请刷新")
        safe_versions = _require_reviewable(db, "FINAL", final, student, user)
        if action == "APPROVE":
            check = db.scalars(select(GraduationPlagiarismCheck).where(
                GraduationPlagiarismCheck.tenant_id == _tid(),
                GraduationPlagiarismCheck.gd_final_id == final.id,
                GraduationPlagiarismCheck.is_deleted.is_(False),
            ).order_by(GraduationPlagiarismCheck.id.desc()).with_for_update()).first()
            if final.final_type == "定稿" and (not check or check.status != "DONE"):
                raise AppException("DATA_CONFLICT", "查重尚未完成，不能通过成果审核")
            if check and check.status == "DONE" and check.over_threshold and check.dispute_status != "APPROVED":
                raise AppException("DATA_CONFLICT", f"查重率 {check.rate} 超标，须退回修改或完成特例审批")
        safe_versions = _require_reviewable(db, "FINAL", final, student, user)
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
        before = final.status
        final.status = target
        final.active_key = None
        final.reviewer = _actor_name(user)
        final.review_comment = str(comment or "").strip()
        final.review_time = datetime.now(timezone.utc)
        _mark_review_status(db, "FINAL", final.id, target)
        from app.modules.graduation.services import graduation_service as legacy
        legacy._audit(
            db, "FINAL", final.id,
            "批阅成果-" + ("通过" if action == "APPROVE" else "退回修改"),
            str(comment or "").strip(), before, target,
        )
        from app.modules.graduation.services import graduation_todo_helper as todo
        todo.todo_done(db, biz_id=final.id, todo_type=todo.TODO_FINAL)
        db.commit()
        return {
            "id": str(final.id), "status": target,
            "statusLabel": "已通过" if target == "APPROVED" else "已退回修改",
            "reviewedVersionIds": [item["versionId"] for item in safe_versions],
        }


def backfill_legacy(user: dict, *, limit: int = 500) -> dict:
    converted_proposals = converted_finals = 0
    backfill_user = {**(user or {}), "sourceChannel": "BACKFILL"}
    with session() as db:
        proposals = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.is_deleted.is_(False),
        ).order_by(GraduationProposal.gd_student_id, GraduationProposal.id).limit(max(1, min(5000, int(limit))))).all()
        for proposal in proposals:
            if _record_bindings(db, "PROPOSAL", proposal.id, current_only=None):
                continue
            student = db.get(GraduationStudent, int(proposal.gd_student_id))
            if not student or student.is_deleted:
                raise AppException("DATA_CONFLICT", f"旧开题记录{proposal.id}缺少学生档案，停止回填")
            _adopt_record(db, "PROPOSAL", proposal, student, backfill_user, allow_existing=False)
            converted_proposals += 1
        finals = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.gd_student_id, GraduationFinal.final_type, GraduationFinal.id)
         .limit(max(1, min(5000, int(limit))))).all()
        for final in finals:
            if _record_bindings(db, "FINAL", final.id, current_only=None):
                continue
            student = db.get(GraduationStudent, int(final.gd_student_id))
            if not student or student.is_deleted:
                raise AppException("DATA_CONFLICT", f"旧成果记录{final.id}缺少学生档案，停止回填")
            _adopt_record(db, "FINAL", final, student, backfill_user, allow_existing=False)
            converted_finals += 1
        db.commit()
    return {
        "convertedProposals": converted_proposals,
        "convertedFinals": converted_finals,
        "completed": converted_proposals == 0 and converted_finals == 0,
    }


def student_material_library(gd_student_id: int | None, user: dict, *, include_history: bool = True) -> dict:
    with session() as db:
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            current = resolve_current_gd_student(db, user)
            if not current:
                raise not_found("毕业设计材料库不存在")
            if gd_student_id and int(gd_student_id) != int(current.id):
                raise not_found("毕业设计材料库不存在")
            student = current
            student_mode = True
        else:
            if not gd_student_id:
                raise AppException("VALIDATION_ERROR", "缺少毕业设计学生ID")
            student = db.get(GraduationStudent, int(gd_student_id))
            if not student or student.is_deleted or student.tenant_id != _tid():
                raise not_found("毕业设计材料库不存在")
            assert_student_access(db, student, "material.library")
            student_mode = False
        assets = db.scalars(select(FileAsset).where(
            FileAsset.tenant_id == _tid(), FileAsset.owner_type == "GRADUATION_STUDENT_MATERIAL",
            FileAsset.owner_id == str(student.id), FileAsset.is_deleted.is_(False),
        ).order_by(FileAsset.category_code, FileAsset.id)).all()
        result = []
        for asset in assets:
            query = select(FileVersion).where(
                FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
                FileVersion.is_deleted.is_(False),
            )
            if not include_history:
                query = query.where(FileVersion.is_current.is_(True))
            versions = db.scalars(query.order_by(FileVersion.version_no.desc())).all()
            version_rows = []
            for version in versions:
                bindings = db.scalars(select(FileBinding).where(
                    FileBinding.tenant_id == _tid(), FileBinding.version_id == int(version.id),
                    FileBinding.module_code == MODULE_CODE, FileBinding.is_deleted.is_(False),
                )).all()
                version_rows.extend(_version_views(db, list(bindings), student_mode=student_mode))
            result.append({
                "assetId": str(asset.id), "assetCode": asset.asset_code,
                "title": asset.title, "categoryCode": asset.category_code,
                "currentVersionId": str(asset.current_version_id or ""),
                "versionCount": int(asset.version_count or 0),
                "lifecycleStatus": asset.lifecycle_status,
                "versions": version_rows,
            })
        return {
            "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
            "studentName": student.name, "studentNo": student.student_no or "",
            "batchId": str(student.batch_id or ""), "items": result, "total": len(result),
        }


def publish_template_asset(template_id: int, file_id: int | None, user: dict) -> dict:
    with session() as db:
        template = db.scalars(select(GraduationTemplate).where(
            GraduationTemplate.id == int(template_id), GraduationTemplate.tenant_id == _tid(),
            GraduationTemplate.is_deleted.is_(False),
        ).with_for_update()).first()
        if not template:
            raise not_found("毕业设计模板不存在")
        if file_id:
            file_obj = db.get(FileObject, int(file_id))
            if not file_obj or file_obj.is_deleted or file_obj.tenant_id != _tid():
                raise not_found("模板文件不存在")
            _require_file_ready(file_obj)
        else:
            text = "\n".join([
                f"模板名称：{template.name}", f"模板类型：{template.template_type}",
                f"业务版本：{template.template_version or 'v1'}", "", template.content or "",
            ]).encode("utf-8")
            meta = file_service.store_bytes(
                text, f"{template.name}_{template.template_version or 'v1'}.txt",
                biz_type="GRADUATION_TEMPLATE", biz_id=str(template.id), mime_type="text/plain",
                user=user, visibility="BIZ_SCOPED", security_level="NORMAL", db=db,
            )
            file_obj = db.get(FileObject, int(meta["fileId"]))
            _require_file_ready(file_obj)
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
        current = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
            FileVersion.is_current.is_(True), FileVersion.is_deleted.is_(False),
        ).with_for_update()).all()
        for old in current:
            old.is_current = False
            old.status = "INVALIDATED"
            old.invalidated_at = datetime.utcnow()
            old.invalidated_by = _actor_name(user)
            old.invalid_reason = "模板发布新版本"
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
        binding = FileBinding(
            tenant_id=_tid(), file_id=int(file_obj.id), biz_type="GRADUATION_TEMPLATE",
            biz_id=str(template.id), relation_type="GRADUATION_TEMPLATE_SOURCE",
            subject_type="BUSINESS_OBJECT", subject_id=str(template.id),
            version_no=int(version.version_no), is_current=True, status="ACTIVE",
            scope_json={"templateId": str(template.id), "templateType": template.template_type,
                        "templateVersion": template.template_version or ""},
            asset_id=int(asset.id), version_id=int(version.id), module_code=MODULE_CODE,
            created_by=_actor_id(user),
        )
        db.add(binding)
        asset.current_version_id = int(version.id)
        asset.version_count = int(version.version_no)
        file_obj.biz_type = "GRADUATION_TEMPLATE"
        file_obj.biz_id = str(template.id)
        file_obj.visibility = "BIZ_SCOPED"
        db.commit()
        return {
            "templateId": str(template.id), "assetId": str(asset.id),
            "versionId": str(version.id), "versionNo": int(version.version_no),
            "fileId": str(file_obj.id), "fileName": file_obj.file_name,
            "sha256": file_obj.sha256, "status": version.status,
        }


def template_versions(template_id: int) -> dict:
    with session() as db:
        asset = db.scalars(select(FileAsset).where(
            FileAsset.tenant_id == _tid(), FileAsset.owner_type == "GRADUATION_TEMPLATE",
            FileAsset.owner_id == str(template_id), FileAsset.is_deleted.is_(False),
        )).first()
        if not asset:
            return {"templateId": str(template_id), "items": [], "total": 0}
        versions = db.scalars(select(FileVersion).where(
            FileVersion.tenant_id == _tid(), FileVersion.asset_id == int(asset.id),
            FileVersion.is_deleted.is_(False),
        ).order_by(FileVersion.version_no.desc())).all()
        items = []
        for version in versions:
            file_obj = db.get(FileObject, int(version.file_object_id))
            if file_obj:
                items.append({
                    "assetId": str(asset.id), "versionId": str(version.id),
                    "versionNo": int(version.version_no), "status": version.status,
                    "isCurrent": bool(version.is_current), "fileId": str(file_obj.id),
                    "fileName": file_obj.file_name, "sizeBytes": file_obj.size_bytes,
                    "sha256": file_obj.sha256, "scanStatus": file_obj.scan_status,
                    "readyForBusiness": _file_ready(file_obj),
                })
        return {"templateId": str(template_id), "items": items, "total": len(items)}


def _manifest_item_row(item: ArchiveManifestItem) -> dict:
    return {
        "materialCode": item.material_code, "assetId": str(item.asset_id),
        "versionId": str(item.version_id), "fileObjectId": str(item.file_object_id),
        "fileName": item.file_name_snapshot, "sizeBytes": item.size_snapshot,
        "sha256": item.sha256_snapshot, "reviewStatus": item.review_status,
        "scanResult": item.scan_result, "sortNo": int(item.sort_no or 0),
    }


def _manifest_row(db, manifest: ArchiveManifest) -> dict:
    items = db.scalars(select(ArchiveManifestItem).where(
        ArchiveManifestItem.tenant_id == _tid(),
        ArchiveManifestItem.manifest_id == int(manifest.id),
        ArchiveManifestItem.is_deleted.is_(False),
    ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
    return {
        "manifestId": str(manifest.id), "revision": int(manifest.revision or 1),
        "status": manifest.status, "ruleVersion": manifest.rule_version,
        "manifestSha256": manifest.manifest_sha256 or "",
        "packageFileId": str(manifest.package_file_id or ""),
        "frozenAt": _iso(manifest.frozen_at),
        "items": [_manifest_item_row(item) for item in items], "itemCount": len(items),
    }


def _collect_archive_versions(db, student: GraduationStudent, user: dict) -> list[dict]:
    proposal = db.scalars(select(GraduationProposal).where(
        GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == student.id,
        GraduationProposal.status == "APPROVED", GraduationProposal.is_deleted.is_(False),
    ).order_by(GraduationProposal.id.desc()).with_for_update()).first()
    final = db.scalars(select(GraduationFinal).where(
        GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == student.id,
        GraduationFinal.final_type == "定稿", GraduationFinal.status == "APPROVED",
        GraduationFinal.is_deleted.is_(False),
    ).order_by(GraduationFinal.id.desc()).with_for_update()).first()
    if not proposal or not final:
        raise AppException("DATA_CONFLICT", "缺少已通过的开题报告或成果定稿，不能冻结归档清单")
    for record_type, record in (("PROPOSAL", proposal), ("FINAL", final)):
        if not _record_bindings(db, record_type, int(record.id), current_only=True):
            _adopt_record(db, record_type, record, student, {**(user or {}), "sourceChannel": "BACKFILL"})
        _mark_review_status(db, record_type, int(record.id), "APPROVED")
    bindings = (
        _record_bindings(db, "PROPOSAL", proposal.id, current_only=True)
        + _record_bindings(db, "FINAL", final.id, current_only=True)
    )
    frozen: list[dict] = []
    seen: set[int] = set()
    for binding in bindings:
        if not binding.version_id or int(binding.version_id) in seen:
            continue
        version = db.get(FileVersion, int(binding.version_id))
        file_obj = db.get(FileObject, int(binding.file_id))
        if not version or not file_obj or version.file_object_id != file_obj.id:
            raise AppException("DATA_CONFLICT", "毕业设计归档版本引用损坏")
        if not version.is_current or version.status != "APPROVED":
            raise AppException("DATA_CONFLICT", "毕业设计归档材料不是当前已通过版本")
        _require_file_ready(file_obj)
        scope = binding.scope_json or {}
        seen.add(int(version.id))
        frozen.append({
            "materialCode": scope.get("materialCode") or f"GD_FILE_{file_obj.id}",
            "assetId": int(version.asset_id), "versionId": int(version.id),
            "fileObjectId": int(file_obj.id), "fileName": file_obj.file_name,
            "sizeBytes": file_obj.size_bytes, "sha256": file_obj.sha256,
            "reviewStatus": "APPROVED", "scanResult": str(file_obj.scan_status or SCAN_NOT_REQUIRED).upper(),
            "sortNo": len(frozen) + 1,
        })
    if not frozen:
        raise AppException("DATA_CONFLICT", "毕业设计归档没有可冻结的真实文件版本")
    return frozen


def freeze_archive_manifest(db, archive: GraduationArchiveRecord, student: GraduationStudent,
                            archive_batch_no: str, user: dict) -> dict:
    frozen = _collect_archive_versions(db, student, user)
    active = db.scalars(select(ArchiveManifest).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == ARCHIVE_TARGET,
        ArchiveManifest.target_id == str(archive.id),
        ArchiveManifest.status.in_(ACTIVE_MANIFEST_STATUS), ArchiveManifest.is_deleted.is_(False),
    ).with_for_update()).all()
    for old in active:
        old.status = "SUPERSEDED"
    revision = int(db.scalar(select(func.max(ArchiveManifest.revision)).where(
        ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
        ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_type == ARCHIVE_TARGET,
        ArchiveManifest.target_id == str(archive.id),
    )) or 0) + 1
    rule = ensure_default_rule(db, student.batch_id)
    from app.modules.graduation.services.graduation_archive_consistency import manifest_payload
    semantic = manifest_payload(db, student, archive_batch_no)
    payload = {
        "schemaVersion": "GRADUATION_FILE_VERSION_MANIFEST_V1",
        "tenantId": str(_tid()), "gdStudentId": str(student.id),
        "studentId": str(student.student_id or ""), "batchId": str(student.batch_id or ""),
        "archiveId": str(archive.id), "archiveBatchNo": archive_batch_no,
        "revision": revision, "ruleCode": rule.rule_code,
        "ruleVersion": int(rule.rule_version or 1),
        "semanticManifestHash": semantic.get("manifestHash"), "items": frozen,
    }
    digest = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    manifest = ArchiveManifest(
        tenant_id=_tid(), module_code=MODULE_CODE, archive_type=ARCHIVE_TYPE,
        target_type=ARCHIVE_TARGET, target_id=str(archive.id), revision=revision,
        status="FROZEN", rule_version=f"{rule.rule_code}:v{rule.rule_version}",
        manifest_sha256=digest, created_by_name=_actor_name(user),
        frozen_at=datetime.utcnow(), created_by=_actor_id(user),
    )
    db.add(manifest)
    db.flush()
    for item in frozen:
        db.add(ArchiveManifestItem(
            tenant_id=_tid(), manifest_id=int(manifest.id),
            material_code=item["materialCode"], asset_id=item["assetId"],
            version_id=item["versionId"], file_object_id=item["fileObjectId"],
            file_name_snapshot=item["fileName"], size_snapshot=item["sizeBytes"],
            sha256_snapshot=item["sha256"], review_status=item["reviewStatus"],
            scan_result=item["scanResult"], sort_no=item["sortNo"],
            created_by=_actor_id(user),
        ))
    db.flush()
    return _manifest_row(db, manifest)


@_conflict_guard
def file_archive(gd_student_id: int, archive_batch_no: str | None, user: dict) -> dict:
    from app.modules.graduation.services import graduation_archive_service as archive_service
    with session() as db:
        student = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == int(gd_student_id), GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "archive.file")
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(),
            GraduationArchiveRecord.gd_student_id == student.id,
            GraduationArchiveRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if not archive:
            raise not_found("毕业设计归档记录不存在")
        requested = str(archive_batch_no or archive.archive_batch_no or f"GDARCH-{datetime.now():%Y%m%d}").strip()
        if archive.status == "FILED":
            if archive.archive_batch_no != requested:
                raise AppException("IDEMPOTENCY_CONFLICT", "归档记录已进入其他备案批次")
            manifest = db.scalars(select(ArchiveManifest).where(
                ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
                ArchiveManifest.target_id == str(archive.id), ArchiveManifest.is_deleted.is_(False),
            ).order_by(ArchiveManifest.revision.desc())).first()
            row = archive_service._row(archive, student)
            row["fileVersionManifest"] = _manifest_row(db, manifest) if manifest else None
            return row
        if archive.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅已提交记录可核验归档")
        archive_service._assert_no_open_risks(db, student)
        checklist, missing = archive_service._check_completeness(db, student)
        if missing:
            raise AppException("DATA_CONFLICT", "归档完整性已变化，请重新生成后提交")
        manifest = freeze_archive_manifest(db, archive, student, requested, user)
        archive.checklist_json, archive.missing_items = checklist, missing
        archive.status = "FILED"
        archive.verified_by = _actor_name(user)
        archive.filed_at = datetime.now(timezone.utc)
        archive.archive_batch_no = requested
        archive.manifest_hash = manifest["manifestSha256"]
        archive.version = int(archive.version or 0) + 1
        if student.stage != "ARCHIVED":
            student.stage = "ARCHIVED"
            student.version = int(student.version or 0) + 1
        archive_service._audit(
            db, archive.id, "核验归档",
            detail=f"{requested};fileVersionManifest={manifest['manifestId']};sha256={manifest['manifestSha256']}",
        )
        from app.modules.graduation.services.graduation_risk_service import notify_risk_rescan
        notify_risk_rescan(db, student.id)
        db.commit()
        row = archive_service._row(archive, student)
        row["fileVersionManifest"] = manifest
        return row


@_conflict_guard
def batch_file(archive_batch_no: str | None, batch_id: int, preview_token: str, user: dict) -> dict:
    from app.modules.graduation.services import graduation_archive_consistency as consistency
    from app.modules.graduation.services import graduation_archive_service as archive_service
    from app.modules.graduation.services.graduation_archive_batch_consistency import _archive_no

    archive_no = _archive_no(archive_batch_no or f"GDARCH-{datetime.now():%Y%m%d}")
    with session() as db:
        batch = archive_service._require_batch(db, batch_id)
        snapshot = consistency._snapshot(db, batch, "FILE", lock=True)
        consistency._verify_token(preview_token, consistency._token_payload("FILE", batch, snapshot))
        filed = skipped = 0
        manifest_ids: list[str] = []
        for snap in snapshot["rows"]:
            student = db.get(GraduationStudent, int(snap["studentId"]))
            archive = db.get(GraduationArchiveRecord, int(snap["archiveId"]))
            if not student or not archive or archive.status != "SUBMITTED":
                skipped += 1
                continue
            checklist, missing = archive_service._check_completeness(db, student)
            if missing or archive_service._count_open_risks(db, student) > 0:
                skipped += 1
                continue
            manifest = freeze_archive_manifest(db, archive, student, archive_no, user)
            archive.checklist_json, archive.missing_items = checklist, missing
            archive.status = "FILED"
            archive.verified_by = _actor_name(user)
            archive.filed_at = datetime.now(timezone.utc)
            archive.archive_batch_no = archive_no
            archive.manifest_hash = manifest["manifestSha256"]
            archive.version = int(archive.version or 0) + 1
            if student.stage != "ARCHIVED":
                student.stage = "ARCHIVED"
                student.version = int(student.version or 0) + 1
            archive_service._audit(
                db, archive.id, "批量核验归档",
                detail=f"batchId={batch.id};archiveBatchNo={archive_no};manifest={manifest['manifestSha256']}",
            )
            manifest_ids.append(manifest["manifestId"])
            filed += 1
        archive_service._audit(
            db, f"batch-file-{batch.id}", "批量核验归档汇总",
            detail=f"filed={filed};skipped={skipped};archiveBatchNo={archive_no};manifests={len(manifest_ids)}",
        )
        db.commit()
        return {
            "filed": filed, "skipped": skipped, "archiveBatchNo": archive_no,
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "manifestIds": manifest_ids,
        }


def get_manifest(gd_student_id: int, user: dict) -> dict:
    with session() as db:
        student = db.get(GraduationStudent, int(gd_student_id))
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("毕业设计归档清单不存在")
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            current = resolve_current_gd_student(db, user)
            if not current or int(current.id) != int(student.id):
                raise not_found("毕业设计归档清单不存在")
        else:
            assert_student_access(db, student, "archive.manifest")
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(), GraduationArchiveRecord.gd_student_id == student.id,
            GraduationArchiveRecord.is_deleted.is_(False),
        )).first()
        if not archive:
            raise not_found("毕业设计归档清单不存在")
        manifest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.archive_type == ARCHIVE_TYPE, ArchiveManifest.target_id == str(archive.id),
            ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc())).first()
        if not manifest:
            raise not_found("毕业设计归档清单不存在")
        return _manifest_row(db, manifest)


def _safe_name(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", str(value or "").strip()) or "未命名"


def _manifest_entries(db, manifest: ArchiveManifest, student: GraduationStudent,
                      *, folder_prefix: str = "") -> tuple[list[dict], dict[str, bytes]]:
    items = db.scalars(select(ArchiveManifestItem).where(
        ArchiveManifestItem.tenant_id == _tid(), ArchiveManifestItem.manifest_id == int(manifest.id),
        ArchiveManifestItem.is_deleted.is_(False),
    ).order_by(ArchiveManifestItem.sort_no, ArchiveManifestItem.id)).all()
    if not items:
        raise AppException("DATA_CONFLICT", "归档清单没有真实文件版本")
    payload: list[dict] = []
    entries: dict[str, bytes] = {}
    for item in items:
        version = db.get(FileVersion, int(item.version_id))
        file_obj = db.get(FileObject, int(item.file_object_id))
        if not version or not file_obj or version.file_object_id != file_obj.id:
            raise AppException("DATA_CONFLICT", "归档清单引用的文件版本已损坏")
        if version.status not in {"APPROVED", "ARCHIVED"}:
            raise AppException("DATA_CONFLICT", "归档版本审核状态已变化")
        _require_file_ready(file_obj)
        if file_obj.sha256 != item.sha256_snapshot:
            raise AppException("DATA_CONFLICT", "归档材料哈希与冻结清单不一致")
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise AppException("DATA_CONFLICT", "归档材料真实字节不存在")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != item.sha256_snapshot:
            raise AppException("DATA_CONFLICT", "归档材料真实字节哈希校验失败")
        archive_path = (
            f"{folder_prefix}materials/{int(item.sort_no or 0):03d}_"
            f"{_safe_name(item.material_code)}_{_safe_name(item.file_name_snapshot)}"
        )
        if archive_path in entries:
            raise AppException("DATA_CONFLICT", "归档包内文件名冲突")
        entries[archive_path] = data
        payload.append({
            "materialCode": item.material_code, "assetId": str(item.asset_id),
            "versionId": str(item.version_id), "fileObjectId": str(item.file_object_id),
            "fileName": item.file_name_snapshot, "archivePath": archive_path,
            "sizeBytes": len(data), "sha256": digest,
            "reviewStatus": item.review_status, "scanResult": item.scan_result,
            "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
            "studentName": student.name, "studentNo": student.student_no or "",
        })
    return payload, entries


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive_zip:
        for name in sorted(entries):
            archive_zip.writestr(name, entries[name])
    return output.getvalue()


def build_student_package(gd_student_id: int, user: dict) -> dict:
    with session() as db:
        student = db.get(GraduationStudent, int(gd_student_id))
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("毕业设计学生不存在")
        assert_student_access(db, student, "archive.package")
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(), GraduationArchiveRecord.gd_student_id == student.id,
            GraduationArchiveRecord.status == "FILED", GraduationArchiveRecord.is_deleted.is_(False),
        ).with_for_update()).first()
        if not archive:
            raise AppException("DATA_CONFLICT", "仅已备案学生可生成归档包")
        manifest = db.scalars(select(ArchiveManifest).where(
            ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
            ArchiveManifest.target_id == str(archive.id),
            ArchiveManifest.status.in_(("FROZEN", "PACKAGED")), ArchiveManifest.is_deleted.is_(False),
        ).order_by(ArchiveManifest.revision.desc()).with_for_update()).first()
        if not manifest:
            raise AppException("DATA_CONFLICT", "缺少已冻结的毕业设计版本清单")
        payload_items, entries = _manifest_entries(db, manifest, student)
        package_manifest = {
            "schemaVersion": "GRADUATION_ARCHIVE_PACKAGE_V1",
            "manifestId": str(manifest.id), "manifestRevision": int(manifest.revision),
            "manifestSha256": manifest.manifest_sha256, "tenantId": str(_tid()),
            "gdStudentId": str(student.id), "studentId": str(student.student_id or ""),
            "batchId": str(student.batch_id or ""), "archiveBatchNo": archive.archive_batch_no,
            "generatedAt": datetime.utcnow().isoformat() + "Z", "generatedBy": _actor_name(user),
            "materialFileCount": len(payload_items), "items": payload_items,
        }
        entries["manifest.json"] = json.dumps(
            package_manifest, ensure_ascii=False, indent=2, sort_keys=True,
        ).encode("utf-8")
        zip_data = _zip_bytes(entries)
        meta = file_service.store_bytes(
            zip_data,
            f"毕业设计归档_{_safe_name(student.name)}_{_safe_name(student.student_no or str(student.id))}_m{manifest.revision}.zip",
            biz_type="GRADUATION_ARCHIVE_PACKAGE", biz_id=str(student.id), mime_type="application/zip",
            user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE",
        )
        manifest.package_file_id = int(meta["fileId"])
        manifest.status = "PACKAGED"
        db.commit()
        return {
            "fileId": str(meta["fileId"]), "fileName": meta["fileName"],
            "sizeBytes": meta["sizeBytes"], "sha256": meta["sha256"],
            "manifestId": str(manifest.id), "manifestRevision": int(manifest.revision),
            "materialFileCount": len(payload_items), "packageReady": True,
        }


def build_batch_package(batch_id: int, user: dict) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    with session() as db:
        batch = db.get(GraduationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("毕业设计批次不存在")
        scope_ids = set(accessible_student_ids(db, _tid(), batch_id=batch.id))
        archives = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == _tid(), GraduationArchiveRecord.status == "FILED",
            GraduationArchiveRecord.gd_student_id.in_(scope_ids or [-1]),
            GraduationArchiveRecord.is_deleted.is_(False),
        ).order_by(GraduationArchiveRecord.gd_student_id).with_for_update()).all()
        entries: dict[str, bytes] = {}
        all_items: list[dict] = []
        manifest_rows: list[dict] = []
        manifests: list[ArchiveManifest] = []
        for archive in archives:
            student = db.get(GraduationStudent, int(archive.gd_student_id))
            if not student or student.batch_id != batch.id:
                continue
            assert_student_access(db, student, "archive.batch.package")
            manifest = db.scalars(select(ArchiveManifest).where(
                ArchiveManifest.tenant_id == _tid(), ArchiveManifest.module_code == MODULE_CODE,
                ArchiveManifest.target_id == str(archive.id),
                ArchiveManifest.status.in_(("FROZEN", "PACKAGED")), ArchiveManifest.is_deleted.is_(False),
            ).order_by(ArchiveManifest.revision.desc()).with_for_update()).first()
            if not manifest:
                raise AppException("DATA_CONFLICT", f"学生{student.name}缺少冻结版本清单")
            folder = f"students/{_safe_name(student.student_no or str(student.id))}_{_safe_name(student.name)}/"
            item_rows, item_entries = _manifest_entries(db, manifest, student, folder_prefix=folder)
            for path, data in item_entries.items():
                if path in entries:
                    raise AppException("DATA_CONFLICT", "批量归档包路径冲突")
                entries[path] = data
            all_items.extend(item_rows)
            manifest_rows.append({
                "gdStudentId": str(student.id), "studentNo": student.student_no or "",
                "studentName": student.name, "manifestId": str(manifest.id),
                "manifestRevision": int(manifest.revision),
                "manifestSha256": manifest.manifest_sha256,
                "materialFileCount": len(item_rows),
            })
            manifests.append(manifest)
        if not all_items:
            raise AppException("DATA_CONFLICT", "当前批次没有可打包的已备案真实材料")

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "毕业设计归档索引"
        headers = ["学号", "学生", "材料编码", "版本ID", "文件对象ID", "文件名", "大小", "SHA-256", "包内路径"]
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for item in all_items:
            sheet.append([
                item["studentNo"], item["studentName"], item["materialCode"],
                item["versionId"], item["fileObjectId"], item["fileName"],
                item["sizeBytes"], item["sha256"], item["archivePath"],
            ])
        sheet.freeze_panes = "A2"
        widths = [18, 14, 32, 16, 16, 36, 14, 68, 72]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[chr(64 + index)].width = width
        excel_buffer = io.BytesIO()
        workbook.save(excel_buffer)
        excel_data = excel_buffer.getvalue()
        excel_name = f"毕业设计归档索引_{_safe_name(batch.batch_name)}_{datetime.now():%Y%m%d_%H%M}.xlsx"
        excel_meta = file_service.store_bytes(
            excel_data, excel_name,
            biz_type="GRADUATION_ARCHIVE_INDEX", biz_id=str(batch.id),
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE",
        )
        entries["归档索引.xlsx"] = excel_data
        package_manifest = {
            "schemaVersion": "GRADUATION_BATCH_ARCHIVE_PACKAGE_V1",
            "tenantId": str(_tid()), "batchId": str(batch.id), "batchName": batch.batch_name,
            "generatedAt": datetime.utcnow().isoformat() + "Z", "generatedBy": _actor_name(user),
            "studentManifestCount": len(manifest_rows), "materialFileCount": len(all_items),
            "indexFile": {"fileName": excel_name, "sha256": hashlib.sha256(excel_data).hexdigest()},
            "studentManifests": manifest_rows, "items": all_items,
        }
        entries["manifest.json"] = json.dumps(
            package_manifest, ensure_ascii=False, indent=2, sort_keys=True,
        ).encode("utf-8")
        zip_data = _zip_bytes(entries)
        zip_meta = file_service.store_bytes(
            zip_data, f"毕业设计批量归档_{_safe_name(batch.batch_name)}_{datetime.now():%Y%m%d_%H%M}.zip",
            biz_type="GRADUATION_ARCHIVE_PACKAGE", biz_id=str(batch.id), mime_type="application/zip",
            user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE",
        )
        for manifest in manifests:
            manifest.package_file_id = int(zip_meta["fileId"])
            manifest.status = "PACKAGED"
        db.commit()
        return {
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "zipFileId": str(zip_meta["fileId"]), "zipFileName": zip_meta["fileName"],
            "zipSha256": zip_meta["sha256"], "zipSizeBytes": zip_meta["sizeBytes"],
            "excelFileId": str(excel_meta["fileId"]), "excelFileName": excel_meta["fileName"],
            "excelSha256": excel_meta["sha256"],
            "studentManifestCount": len(manifest_rows), "materialFileCount": len(all_items),
            "packageReady": True,
        }


def resolve_material_download(file_id: int, user: dict, *, student_mode: bool = False):
    with session() as db:
        file_obj = db.scalars(select(FileObject).where(
            FileObject.id == int(file_id), FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_obj:
            raise not_found("毕业设计材料不存在")
        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == _tid(), FileBinding.file_id == int(file_id),
            FileBinding.module_code == MODULE_CODE, FileBinding.is_deleted.is_(False),
        ).order_by(FileBinding.is_current.desc(), FileBinding.id.desc())).all()
        if not bindings:
            raise not_found("毕业设计材料不存在")
        student_ids = {
            _safe_int((binding.scope_json or {}).get("gdStudentId"))
            for binding in bindings
        }
        student_ids.discard(None)
        if len(student_ids) != 1:
            raise not_found("毕业设计材料不存在")
        gd_student_id = next(iter(student_ids))
        student = db.get(GraduationStudent, int(gd_student_id))
        if not student or student.is_deleted:
            raise not_found("毕业设计材料不存在")
        if student_mode or str((user or {}).get("userType") or "").upper() == "STUDENT":
            current = resolve_current_gd_student(db, user)
            if not current or int(current.id) != int(student.id):
                raise not_found("毕业设计材料不存在")
        else:
            assert_student_access(db, student, "material.download")
        _require_file_ready(file_obj)
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("毕业设计材料不存在")
        return path, file_obj.file_name


def resolve_package_download(file_id: int, user: dict):
    with session() as db:
        file_obj = db.scalars(select(FileObject).where(
            FileObject.id == int(file_id), FileObject.tenant_id == _tid(),
            FileObject.biz_type.in_(("GRADUATION_ARCHIVE_PACKAGE", "GRADUATION_ARCHIVE_INDEX")),
            FileObject.is_deleted.is_(False),
        )).first()
        if not file_obj:
            raise not_found("毕业设计归档文件不存在")
        if str((user or {}).get("userType") or "").upper() == "STUDENT":
            if file_obj.biz_type != "GRADUATION_ARCHIVE_PACKAGE":
                raise not_found("毕业设计归档文件不存在")
            current = resolve_current_gd_student(db, user)
            if not current or str(file_obj.biz_id or "") != str(current.id):
                raise not_found("毕业设计归档文件不存在")
        elif not (
            has_permission(user or {}, "graduationDesign.archive.view")
            or has_permission(user or {}, "graduationDesign.archive.file")
            or has_permission(user or {}, "graduationDesign.archive.export")
        ):
            raise not_found("毕业设计归档文件不存在")
        _require_file_ready(file_obj)
        path = get_backend().fetch_local(file_obj.file_key)
        if not path or not path.exists():
            raise not_found("毕业设计归档文件不存在")
        return path, file_obj.file_name
