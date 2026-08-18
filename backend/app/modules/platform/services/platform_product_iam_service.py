"""B6 Platform Product IAM release governance.

Runtime IAM definitions remain code-reviewed artifacts. Platform Operations
controls which exact artifact digest is published, can inspect modules,
permissions, navigation surfaces and RoleTemplate versions, and receives a
machine diff/impact before publication. Runtime operators cannot invent a
second permission/module truth through an arbitrary JSON editor.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.permission_catalog import load_permission_catalog
from app.core.platform_assurance import assert_recent_platform_auth
from app.db.session import get_sessionmaker
from app.models import PlatformConfig
from app.models.permission_governance import (
    EFFECT_ALLOW,
    TEMPLATE_PLANE_TENANT,
    TEMPLATE_PUBLISHED,
    RoleTemplate,
    RoleTemplatePermission,
)

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = ROOT / "shared/contracts/module-manifest.json"
CONFIG_TYPE = "PLATFORM_PRODUCT_IAM_RELEASE"


def _hash(payload) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _module_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _published_templates(db) -> list[dict]:
    """Read only normalized, published TENANT RoleTemplate truth."""
    rows = list(db.scalars(select(RoleTemplate).where(
        RoleTemplate.tenant_id == 0,
        RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
        RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
        RoleTemplate.status == "ACTIVE",
        RoleTemplate.is_deleted.is_(False),
    ).order_by(RoleTemplate.template_code, RoleTemplate.template_version.desc(), RoleTemplate.id.desc())).all())
    latest = {}
    for item in rows:
        latest.setdefault(item.template_code, item)
    result: list[dict] = []
    for item in latest.values():
        permissions = sorted(set(db.scalars(select(RoleTemplatePermission.permission_code).where(
            RoleTemplatePermission.tenant_id == 0,
            RoleTemplatePermission.role_template_id == int(item.id),
            RoleTemplatePermission.effect == EFFECT_ALLOW,
            RoleTemplatePermission.is_deleted.is_(False),
        )).all()))
        legacy_items = sorted(set((item.permission_ceiling_json or {}).get("items") or []))
        if legacy_items and not permissions:
            raise AppException(
                "PRODUCT_IAM_TEMPLATE_DRIFT",
                "已发布 TENANT RoleTemplate 缺少规范化权限关系，拒绝从兼容 JSON 回退",
                http_status=409,
                details={"templateCode": item.template_code, "templateVersion": int(item.template_version or 0)},
            )
        result.append({
            "templateCode": item.template_code,
            "templateVersion": int(item.template_version or 0),
            "permissionCount": len(permissions),
            "permissionDigest": item.permission_digest or _hash(permissions),
        })
    return result


def source_snapshot() -> dict:
    manifest = _module_manifest()
    catalog = load_permission_catalog()
    modules = manifest.get("modules") or []
    internship = [item for item in modules if item.get("moduleKey") == "internship"]
    forbidden = [
        item.get("moduleKey") for item in modules
        if str(item.get("moduleKey") or "").lower() in {"recruitment", "recruitmentcenter", "enterpriserecruitment"}
    ]
    if len(internship) != 1 or forbidden:
        raise AppException(
            "PRODUCT_IAM_MODULE_DRIFT",
            "岗位实习必须且只能使用 moduleKey=internship，禁止第二套招聘顶层模块",
            http_status=409,
            details={"internshipCount": len(internship), "forbiddenModuleKeys": forbidden},
        )
    db = get_sessionmaker()()
    try:
        templates = _published_templates(db)
    finally:
        db.close()
    navigation = [
        {
            "moduleKey": item.get("moduleKey"),
            "frontendRoutePrefixes": item.get("frontendRoutePrefixes") or [],
            "schoolVisible": bool(item.get("schoolVisible")),
            "platformOnly": bool(item.get("platformOnly")),
        }
        for item in modules
    ]
    permissions = [
        {k: item.get(k) for k in (
            "permissionCode", "label", "plane", "moduleKey", "featureKey", "riskLevel",
            "tenantAssignable", "customRoleAssignable", "lifecycle"
        )}
        for item in catalog.get("entries") or []
    ]
    snapshot = {
        "moduleManifestVersion": manifest.get("manifestVersion"),
        "modules": modules,
        "permissions": permissions,
        "navigation": navigation,
        "roleTemplates": templates,
    }
    snapshot["sourceDigest"] = _hash(snapshot)
    return snapshot


def _row(row: PlatformConfig) -> dict:
    data = dict(row.config_json or {})
    return {
        "id": str(row.config_key),
        **data,
        "status": row.status,
        "version": int(row.version or 0),
        "createdAt": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
        "updatedAt": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
    }


def list_releases() -> list[dict]:
    db = get_sessionmaker()()
    try:
        rows = list(db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == CONFIG_TYPE,
            PlatformConfig.is_deleted.is_(False),
        ).order_by(PlatformConfig.created_at.desc())).all())
        return [_row(item) for item in rows]
    finally:
        db.close()


def create_release_draft(*, reason: str, source_commit_sha: str, actor: dict, request_id: str) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "Product IAM 发布草稿必须填写至少5个字符的原因")
    raw_request = str(request_id or "").strip()
    if len(raw_request) < 8:
        raise AppException("IDEMPOTENCY_KEY_REQUIRED", "创建 Product IAM 草稿必须提供 requestId", http_status=422)
    snapshot = source_snapshot()
    key = "product-iam-" + hashlib.sha256(raw_request.encode()).hexdigest()[:32]
    db = get_sessionmaker()()
    try:
        existing = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == CONFIG_TYPE,
            PlatformConfig.config_key == key,
            PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        command_digest = _hash({"reason": reason, "sourceCommitSha": source_commit_sha, "sourceDigest": snapshot["sourceDigest"]})
        if existing is not None:
            if (existing.config_json or {}).get("commandDigest") != command_digest:
                raise AppException("IDEMPOTENCY_CONFLICT", "相同 requestId 已用于不同 Product IAM 草稿", http_status=409)
            return _row(existing)
        row = PlatformConfig(
            tenant_id=0,
            config_type=CONFIG_TYPE,
            config_key=key,
            config_json={
                "releaseId": uuid.uuid4().hex,
                "reason": reason,
                "sourceCommitSha": str(source_commit_sha or "").strip(),
                "sourceDigest": snapshot["sourceDigest"],
                "snapshot": snapshot,
                "commandDigest": command_digest,
                "createdBy": actor.get("userId"),
            },
            enabled=False,
            status="DRAFT",
            remark=reason[:500],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _row(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def impact(release_id: str) -> dict:
    db = get_sessionmaker()()
    try:
        target = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == CONFIG_TYPE,
            PlatformConfig.config_key == str(release_id),
            PlatformConfig.is_deleted.is_(False),
        )).first()
        if target is None:
            raise AppException("DATA_NOT_FOUND", "Product IAM release 不存在", http_status=404)
        previous = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == CONFIG_TYPE,
            PlatformConfig.status == "PUBLISHED",
            PlatformConfig.is_deleted.is_(False),
            PlatformConfig.id != target.id,
        ).order_by(PlatformConfig.updated_at.desc())).first()
        current_snapshot = (target.config_json or {}).get("snapshot") or {}
        before_snapshot = ((previous.config_json or {}).get("snapshot") or {}) if previous else {}
        current_modules = {item.get("moduleKey") for item in current_snapshot.get("modules") or []}
        before_modules = {item.get("moduleKey") for item in before_snapshot.get("modules") or []}
        current_permissions = {item.get("permissionCode") for item in current_snapshot.get("permissions") or []}
        before_permissions = {item.get("permissionCode") for item in before_snapshot.get("permissions") or []}
        before_templates = {item.get("templateCode"): item.get("templateVersion") for item in before_snapshot.get("roleTemplates") or []}
        current_templates = {item.get("templateCode"): item.get("templateVersion") for item in current_snapshot.get("roleTemplates") or []}
        changed_templates = sorted(code for code in set(before_templates) | set(current_templates) if before_templates.get(code) != current_templates.get(code))
        return {
            "releaseId": str(release_id),
            "previousReleaseId": str(previous.config_key) if previous else "",
            "addedModules": sorted(current_modules - before_modules),
            "removedModules": sorted(before_modules - current_modules),
            "addedPermissions": sorted(current_permissions - before_permissions),
            "removedPermissions": sorted(before_permissions - current_permissions),
            "changedRoleTemplates": changed_templates,
            "internshipModuleCount": sum(1 for key in current_modules if key == "internship"),
            "secondRecruitmentModule": any(str(key or "").lower() in {"recruitment", "recruitmentcenter", "enterpriserecruitment"} for key in current_modules),
        }
    finally:
        db.close()


def publish_release(release_id: str, *, expected_version: int, actor: dict) -> dict:
    assert_recent_platform_auth(actor, require_mfa=True)
    current_source = source_snapshot()
    from app.services import audit_log

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == 0,
            PlatformConfig.config_type == CONFIG_TYPE,
            PlatformConfig.config_key == str(release_id),
            PlatformConfig.is_deleted.is_(False),
        ).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "Product IAM release 不存在", http_status=404)
        if row.status != "DRAFT":
            raise AppException("IMMUTABLE_RELEASE", "已发布 Product IAM 版本不可再次修改或发布", http_status=409)
        if int(row.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "Product IAM 草稿已变化，请刷新后重试", http_status=409)
        data = dict(row.config_json or {})
        if data.get("sourceDigest") != current_source.get("sourceDigest"):
            raise AppException(
                "PRODUCT_IAM_SOURCE_DRIFT",
                "创建草稿后代码权限/模块/模板真值已经变化，必须重新生成草稿",
                http_status=409,
                details={"draftDigest": data.get("sourceDigest"), "currentDigest": current_source.get("sourceDigest")},
            )
        iam_impact = impact(str(release_id))
        if iam_impact.get("internshipModuleCount") != 1 or iam_impact.get("secondRecruitmentModule"):
            raise AppException("PRODUCT_IAM_MODULE_DRIFT", "岗位实习模块边界不合法，拒绝发布", http_status=409)
        data["publishedBy"] = actor.get("userId")
        data["publishedAt"] = datetime.utcnow().isoformat(timespec="seconds")
        data["impact"] = iam_impact
        row.config_json = data
        row.status = "PUBLISHED"
        row.enabled = True
        row.version = int(row.version or 0) + 1
        audit_log.record_critical_in_session(
            db,
            "PLATFORM_PRODUCT_IAM_PUBLISH",
            f"product-iam:{release_id}",
            detail={"sourceDigest": data.get("sourceDigest"), "impact": iam_impact},
            tenant_id=0,
            resource_id=str(release_id),
        )
        db.commit()
        db.refresh(row)
        return _row(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
