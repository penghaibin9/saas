"""Authoritative versioned material rules for each graduation batch."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException, check_version, not_found
from app.models import GraduationBatch, GraduationStudent
from app.models.graduation_material import GraduationMaterialItem, GraduationMaterialRule, GraduationStudentMaterial
from app.services.db_service import _tid, session
from app.services.message_identity import resolve_message_user_id

from .definitions import DEFAULT_MATERIAL_DEFINITIONS, REVIEW_PERMISSION_BY_CODE


def _actor_id(user: dict | None) -> int | None:
    return resolve_message_user_id(user or {}) or None


def active_rule(db, batch_id: int, *, lock: bool = False) -> GraduationMaterialRule:
    stmt = select(GraduationMaterialRule).where(
        GraduationMaterialRule.tenant_id == _tid(),
        GraduationMaterialRule.batch_id == int(batch_id),
        GraduationMaterialRule.status == "ENABLED",
        GraduationMaterialRule.enabled.is_(True),
        GraduationMaterialRule.is_deleted.is_(False),
    ).order_by(GraduationMaterialRule.rule_version.desc(), GraduationMaterialRule.id.desc())
    if lock:
        stmt = stmt.with_for_update()
    rows = list(db.scalars(stmt).all())
    if not rows:
        raise AppException("MATERIAL_RULE_NOT_INITIALIZED", "当前批次尚未初始化材料规则")
    if len(rows) > 1:
        raise AppException("MATERIAL_RULE_CONFLICT", "当前批次存在多个启用规则，请先修复规则状态")
    return rows[0]


def rule_items(db, rule_id: int, *, lock: bool = False) -> list[GraduationMaterialItem]:
    stmt = select(GraduationMaterialItem).where(
        GraduationMaterialItem.tenant_id == _tid(),
        GraduationMaterialItem.rule_id == int(rule_id),
        GraduationMaterialItem.enabled.is_(True),
        GraduationMaterialItem.is_deleted.is_(False),
    ).order_by(GraduationMaterialItem.sort_no, GraduationMaterialItem.id)
    if lock:
        stmt = stmt.with_for_update()
    return list(db.scalars(stmt).all())


def rule_item(db, batch_id: int, material_code: str, *, lock: bool = False) -> tuple[GraduationMaterialRule, GraduationMaterialItem]:
    rule = active_rule(db, int(batch_id), lock=lock)
    stmt = select(GraduationMaterialItem).where(
        GraduationMaterialItem.tenant_id == _tid(),
        GraduationMaterialItem.rule_id == int(rule.id),
        GraduationMaterialItem.material_code == str(material_code or "").strip().upper(),
        GraduationMaterialItem.enabled.is_(True),
        GraduationMaterialItem.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    item = db.scalars(stmt).first()
    if not item:
        raise AppException("MATERIAL_NOT_IN_BATCH_RULE", "该材料不在当前批次冻结规则中")
    return rule, item


def _normalize_item(raw: dict[str, Any], sort_no: int) -> dict[str, Any]:
    code = str(raw.get("materialCode") or "").strip().upper()
    name = str(raw.get("materialName") or "").strip()
    stage = str(raw.get("stage") or raw.get("bizStage") or "").strip().upper()
    owner = str(raw.get("ownerRole") or "STUDENT").strip().upper()
    extensions = sorted({str(value).lower().lstrip(".") for value in (raw.get("allowedExtensions") or []) if str(value).strip()})
    max_size = int(raw.get("maxSizeBytes") or 0)
    if not code or not name or not stage or not owner:
        raise AppException("VALIDATION_ERROR", f"材料规则第 {sort_no} 项缺少 code/name/stage/ownerRole")
    if not extensions or max_size <= 0:
        raise AppException("VALIDATION_ERROR", f"材料 {code} 缺少允许扩展名或大小限制")
    review_required = bool(raw.get("reviewRequired", True))
    if review_required and code not in REVIEW_PERMISSION_BY_CODE:
        raise AppException(
            "VALIDATION_ERROR",
            f"材料 {code} 要求人工审核，但未登记受支持的原子审核权限",
        )
    return {
        "material_code": code,
        "material_name": name[:200],
        "biz_stage": stage[:40],
        "owner_role": owner[:40],
        "required": bool(raw.get("required", False)),
        "allowed_ext_json": extensions,
        "max_files": max(1, int(raw.get("maxFileCount") or raw.get("maxFiles") or 1)),
        "max_size_bytes": max_size,
        "version_policy": str(raw.get("versionPolicy") or "IMMUTABLE_APPEND").upper()[:40],
        "review_required": review_required,
        "archive_required": bool(raw.get("archiveRequired", True)),
        "sensitivity_level": str(raw.get("sensitivityLevel") or "SENSITIVE").upper()[:30],
        "applicable_major_id": str(raw.get("applicableMajor") or "")[:64] or None,
        "applicable_topic_type": str(raw.get("applicableTopicType") or "")[:64] or None,
        "sort_no": sort_no,
        "enabled": bool(raw.get("enabled", True)),
        "description": str(raw.get("description") or "")[:500] or None,
    }


def _create_rule_in_session(db, *, batch_id: int, name: str, items: list[dict[str, Any]], user: dict | None,
                            status: str = "DRAFT") -> GraduationMaterialRule:
    batch = db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == _tid(), GraduationBatch.id == int(batch_id), GraduationBatch.is_deleted.is_(False),
    ).with_for_update()).first()
    if not batch:
        raise not_found("毕业设计批次不存在")
    normalized = [_normalize_item(raw, index) for index, raw in enumerate(items, start=1)]
    codes = [row["material_code"] for row in normalized]
    if len(codes) != len(set(codes)):
        raise AppException("VALIDATION_ERROR", "材料规则代码不能重复")
    latest = int(db.scalar(select(func.max(GraduationMaterialRule.rule_version)).where(
        GraduationMaterialRule.tenant_id == _tid(),
        GraduationMaterialRule.batch_id == int(batch_id),
        GraduationMaterialRule.rule_code == "GD_MATERIAL_STANDARD",
    )) or 0)
    row = GraduationMaterialRule(
        tenant_id=_tid(), batch_id=int(batch_id), rule_code="GD_MATERIAL_STANDARD",
        rule_name=name[:200], rule_version=latest + 1, status=status,
        enabled=status == "ENABLED", default_owner_role="STUDENT",
        version_policy="IMMUTABLE_APPEND", archive_required=True,
        sensitivity_level="SENSITIVE", applicable_scope_json={"batchId": str(batch_id)},
        required_items_json=[item["material_code"] for item in normalized if item["required"]],
        allowed_ext_json=sorted({ext for item in normalized for ext in item["allowed_ext_json"]}),
        max_files=max(item["max_files"] for item in normalized),
        max_size_bytes=max(item["max_size_bytes"] for item in normalized),
        effective_at=datetime.utcnow() if status == "ENABLED" else None,
        created_by=_actor_id(user),
    )
    db.add(row)
    db.flush()
    for values in normalized:
        db.add(GraduationMaterialItem(tenant_id=_tid(), rule_id=int(row.id), created_by=_actor_id(user), **values))
    db.flush()
    return row


def initialize_default_rule_in_session(db, batch_id: int, user: dict | None = None) -> GraduationMaterialRule:
    try:
        return active_rule(db, int(batch_id), lock=True)
    except AppException as exc:
        if exc.code != "MATERIAL_RULE_NOT_INITIALIZED":
            raise
    drafts = list(db.scalars(select(GraduationMaterialRule).where(
        GraduationMaterialRule.tenant_id == _tid(), GraduationMaterialRule.batch_id == int(batch_id),
        GraduationMaterialRule.status == "DRAFT", GraduationMaterialRule.is_deleted.is_(False),
    ).order_by(GraduationMaterialRule.rule_version.desc(), GraduationMaterialRule.id.desc()).with_for_update()).all())
    if drafts:
        selected = drafts[0]
        selected.status = "ENABLED"
        selected.enabled = True
        selected.effective_at = datetime.utcnow()
        return selected
    return _create_rule_in_session(
        db, batch_id=int(batch_id), name="毕业设计标准材料规则",
        items=[dict(row) for row in DEFAULT_MATERIAL_DEFINITIONS], user=user, status="ENABLED",
    )


def initialize_default_rule(batch_id: int, user: dict | None = None) -> dict:
    with session() as db:
        row = initialize_default_rule_in_session(db, int(batch_id), user)
        db.commit()
        return {"ruleId": str(row.id), "ruleVersion": int(row.rule_version), "status": row.status}


def create_rule(body: dict, user: dict) -> dict:
    batch_id = body.get("batchId")
    if not str(batch_id or "").isdigit():
        raise AppException("VALIDATION_ERROR", "batchId 不能为空")
    items = body.get("items")
    if not isinstance(items, list) or not items:
        if body.get("useDefaultTemplate") is True:
            items = [dict(row) for row in DEFAULT_MATERIAL_DEFINITIONS]
        else:
            raise AppException("VALIDATION_ERROR", "规则必须提供完整 items；默认模板需显式 useDefaultTemplate=true")
    with session() as db:
        row = _create_rule_in_session(
            db, batch_id=int(batch_id), name=str(body.get("ruleName") or "毕业设计材料规则"),
            items=items, user=user, status="DRAFT",
        )
        db.commit()
        return {"id": str(row.id), "batchId": str(row.batch_id), "ruleVersion": int(row.rule_version), "status": row.status}


def impact_analysis(db, candidate: GraduationMaterialRule) -> dict:
    candidate_items = {row.material_code: row for row in rule_items(db, int(candidate.id))}
    current = db.scalars(select(GraduationMaterialRule).where(
        GraduationMaterialRule.tenant_id == _tid(),
        GraduationMaterialRule.batch_id == int(candidate.batch_id),
        GraduationMaterialRule.status == "ENABLED", GraduationMaterialRule.enabled.is_(True),
        GraduationMaterialRule.id != int(candidate.id), GraduationMaterialRule.is_deleted.is_(False),
    ).order_by(GraduationMaterialRule.rule_version.desc())).first()
    current_items = {row.material_code: row for row in rule_items(db, int(current.id))} if current else {}
    changed = sorted(code for code in candidate_items.keys() & current_items.keys() if any((
        candidate_items[code].material_name != current_items[code].material_name,
        candidate_items[code].biz_stage != current_items[code].biz_stage,
        candidate_items[code].owner_role != current_items[code].owner_role,
        candidate_items[code].required != current_items[code].required,
        candidate_items[code].review_required != current_items[code].review_required,
        candidate_items[code].archive_required != current_items[code].archive_required,
        candidate_items[code].allowed_ext_json != current_items[code].allowed_ext_json,
        candidate_items[code].max_files != current_items[code].max_files,
        candidate_items[code].max_size_bytes != current_items[code].max_size_bytes,
        candidate_items[code].version_policy != current_items[code].version_policy,
        candidate_items[code].sensitivity_level != current_items[code].sensitivity_level,
        candidate_items[code].applicable_major_id != current_items[code].applicable_major_id,
        candidate_items[code].applicable_topic_type != current_items[code].applicable_topic_type,
    )))
    affected_students = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(candidate.batch_id),
        GraduationStudent.record_status == "ACTIVE", GraduationStudent.is_deleted.is_(False),
    )) or 0)
    material_rows = int(db.scalar(select(func.count()).select_from(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(), GraduationStudentMaterial.batch_id == int(candidate.batch_id),
        GraduationStudentMaterial.is_deleted.is_(False),
    )) or 0)
    return {
        "previousRuleId": str(current.id) if current else "",
        "candidateRuleId": str(candidate.id),
        "candidateVersion": int(candidate.version or 0),
        "affectedStudents": affected_students,
        "existingMaterialRows": material_rows,
        "addedCodes": sorted(candidate_items.keys() - current_items.keys()),
        "removedCodes": sorted(current_items.keys() - candidate_items.keys()),
        "changedCodes": changed,
        "requiresCatalogRepair": bool(material_rows and (changed or candidate_items.keys() != current_items.keys())),
    }


def get_impact(rule_id: int, user: dict | None = None) -> dict:
    del user
    with session() as db:
        candidate = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(), GraduationMaterialRule.id == int(rule_id),
            GraduationMaterialRule.is_deleted.is_(False),
        )).first()
        if not candidate:
            raise not_found("材料规则不存在")
        return impact_analysis(db, candidate)


def _migrate_catalog_to_candidate(db, candidate: GraduationMaterialRule, user: dict) -> dict:
    items = {row.material_code: row for row in rule_items(db, int(candidate.id), lock=True)}
    archived_student_ids = set(db.scalars(select(GraduationStudent.id).where(
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.batch_id == int(candidate.batch_id),
        GraduationStudent.stage == "ARCHIVED",
        GraduationStudent.is_deleted.is_(False),
    ).with_for_update()).all())
    rows = list(db.scalars(select(GraduationStudentMaterial).where(
        GraduationStudentMaterial.tenant_id == _tid(),
        GraduationStudentMaterial.batch_id == int(candidate.batch_id),
        GraduationStudentMaterial.is_deleted.is_(False),
    ).with_for_update()).all())
    migrated = removed_empty = preserved_archived = 0
    for material in rows:
        if int(material.gd_student_id or 0) in archived_student_ids or material.archive_status in {"FROZEN", "ARCHIVED"}:
            preserved_archived += 1
            continue
        item = items.get(material.material_code)
        if not item:
            if material.current_version_id:
                raise AppException(
                    "MATERIAL_RULE_REMOVAL_CONFLICT",
                    f"材料 {material.material_code} 已有文件，不能从新规则移除",
                )
            material.is_deleted = True
            material.updated_by = _actor_id(user)
            removed_empty += 1
            continue
        material.rule_id = int(candidate.id)
        material.rule_version = int(candidate.rule_version)
        material.material_name = item.material_name
        material.biz_stage = item.biz_stage
        material.owner_role = item.owner_role
        material.required_status = "REQUIRED" if item.required else "OPTIONAL"
        material.sensitivity_level = item.sensitivity_level
        material.updated_by = _actor_id(user)
        migrated += 1
    return {"migrated": migrated, "removedEmpty": removed_empty, "preservedArchived": preserved_archived}


def activate_rule(
    rule_id: int, user: dict, *, expected_version: int, confirm_catalog_repair: bool = False,
) -> dict:
    with session() as db:
        candidate = db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(), GraduationMaterialRule.id == int(rule_id),
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).first()
        if not candidate:
            raise not_found("材料规则不存在")
        check_version(int(candidate.version or 0), expected_version)
        if candidate.status == "ENABLED" and candidate.enabled:
            return {"id": str(candidate.id), "status": candidate.status, "impactAnalysis": impact_analysis(db, candidate)}
        if candidate.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿规则可启用")
        impact = impact_analysis(db, candidate)
        if impact["requiresCatalogRepair"] and not confirm_catalog_repair:
            raise AppException(
                "MATERIAL_RULE_REPAIR_REQUIRED",
                "规则变更会影响现有学生材料目录；请先查看影响分析并显式确认目录迁移",
                http_status=409,
            )
        current = list(db.scalars(select(GraduationMaterialRule).where(
            GraduationMaterialRule.tenant_id == _tid(),
            GraduationMaterialRule.batch_id == int(candidate.batch_id),
            GraduationMaterialRule.status == "ENABLED", GraduationMaterialRule.enabled.is_(True),
            GraduationMaterialRule.is_deleted.is_(False),
        ).with_for_update()).all())
        migration = {"migrated": 0, "removedEmpty": 0, "preservedArchived": 0}
        if impact["requiresCatalogRepair"]:
            migration = _migrate_catalog_to_candidate(db, candidate, user)
        for row in current:
            row.status = "DISABLED"
            row.enabled = False
            row.version = int(row.version or 0) + 1
            row.updated_by = _actor_id(user)
        candidate.status = "ENABLED"
        candidate.enabled = True
        candidate.effective_at = datetime.utcnow()
        candidate.updated_by = _actor_id(user)
        candidate.version = int(candidate.version or 0) + 1
        from .command_service import initialize_batch_materials_in_session

        initialized = initialize_batch_materials_in_session(db, int(candidate.batch_id), user)
        db.commit()
        return {
            "id": str(candidate.id), "status": candidate.status,
            "ruleVersion": int(candidate.rule_version), "impactAnalysis": impact,
            "catalogMigration": {**migration, **initialized},
        }
