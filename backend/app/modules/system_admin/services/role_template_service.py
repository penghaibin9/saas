"""B5 immutable RoleTemplate versioning on normalized canonical schema."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.core.permission_catalog import assert_custom_role_assignable
from app.db.session import get_sessionmaker
from app.models.permission_governance import (
    EFFECT_ALLOW,
    TEMPLATE_CATEGORY_SYSTEM_ROLE,
    TEMPLATE_DRAFT,
    TEMPLATE_PLANE_TENANT,
    TEMPLATE_PUBLISHED,
    CustomRoleSource,
    RoleTemplate,
    RoleTemplatePermission,
)
from app.modules.system_admin.policies.role_template_plane import assert_school_role_template_code

PLATFORM_TENANT = 0
DRAFT = TEMPLATE_DRAFT
PUBLISHED = TEMPLATE_PUBLISHED


def _digest(codes) -> str:
    payload = json.dumps(sorted(set(codes or [])), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _items(db, template: RoleTemplate | None) -> list[str]:
    if template is None:
        return []
    rows = list(db.scalars(select(RoleTemplatePermission.permission_code).where(
        RoleTemplatePermission.tenant_id == int(template.tenant_id),
        RoleTemplatePermission.role_template_id == int(template.id),
        RoleTemplatePermission.effect == EFFECT_ALLOW,
        RoleTemplatePermission.is_deleted.is_(False),
    )).all())
    if rows:
        return sorted(set(rows))
    # Upgrade-only fallback. All new writes materialize normalized rows.
    return sorted(set((template.permission_ceiling_json or {}).get("items") or []))


def _sync_permissions(db, template: RoleTemplate, permissions) -> list[str]:
    wanted = sorted({str(value or "").strip() for value in (permissions or []) if str(value or "").strip()})
    rows = list(db.scalars(select(RoleTemplatePermission).where(
        RoleTemplatePermission.tenant_id == int(template.tenant_id),
        RoleTemplatePermission.role_template_id == int(template.id),
    ).with_for_update()).all())
    by_key = {(row.permission_code, row.effect): row for row in rows}
    for row in rows:
        should_live = row.effect == EFFECT_ALLOW and row.permission_code in wanted
        row.is_deleted = not should_live
        row.updated_by = template.updated_by
        if should_live:
            row.version = int(row.version or 0) + 1
    for code in wanted:
        key = (code, EFFECT_ALLOW)
        if key not in by_key:
            db.add(RoleTemplatePermission(
                tenant_id=int(template.tenant_id),
                role_template_id=int(template.id),
                permission_code=code,
                effect=EFFECT_ALLOW,
                created_by=template.created_by,
                updated_by=template.updated_by,
            ))
    digest = _digest(wanted)
    template.permission_digest = digest
    template.permission_ceiling_json = {
        **dict(template.permission_ceiling_json or {}),
        "items": wanted,
        "permissionDigest": digest,
    }
    return wanted


def _row(db, template: RoleTemplate) -> dict:
    permissions = _items(db, template)
    previous_version = None
    if template.previous_template_id:
        previous = db.get(RoleTemplate, int(template.previous_template_id))
        if previous is not None and int(previous.tenant_id) == PLATFORM_TENANT:
            previous_version = int(previous.template_version or 0)
    return {
        "id": str(template.id),
        "templateCode": template.template_code,
        "templateName": template.template_name,
        "templateVersion": int(template.template_version or 0),
        "templatePlane": template.template_plane,
        "templateCategory": template.template_category,
        "publishStatus": template.publish_status,
        "storedStatus": template.status,
        "permissions": permissions,
        "permissionDigest": template.permission_digest or _digest(permissions),
        "previousTemplateId": str(template.previous_template_id) if template.previous_template_id else None,
        "previousTemplateVersion": previous_version,
        "changeReason": template.change_reason or "",
        "sourceCommitSha": template.source_commit_sha or "",
        "effectiveAt": template.effective_at.isoformat(timespec="seconds") if template.effective_at else None,
        "publishedAt": template.published_at.isoformat(timespec="seconds") if template.published_at else None,
        "publishedBy": template.published_by,
        "version": int(template.version or 0),
    }


def _load(db, template_id: int, *, lock: bool = False) -> RoleTemplate:
    stmt = select(RoleTemplate).where(
        RoleTemplate.id == int(template_id),
        RoleTemplate.tenant_id == PLATFORM_TENANT,
        RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
        RoleTemplate.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    item = db.scalar(stmt)
    if item is None:
        raise AppException("DATA_NOT_FOUND", "TENANT 角色模板不存在", http_status=404)
    return item


def list_versions(template_code: str) -> list[dict]:
    code = assert_school_role_template_code(template_code)
    db = get_sessionmaker()()
    try:
        rows = list(db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == PLATFORM_TENANT,
            RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
            RoleTemplate.template_code == code,
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc())).all())
        return [_row(db, item) for item in rows]
    finally:
        db.close()


def create_draft(
    *,
    template_code: str,
    template_name: str,
    permission_codes,
    change_reason: str,
    source_commit_sha: str = "",
    actor_user_id: int | None = None,
    source_template_id: int | None = None,
) -> dict:
    code = assert_school_role_template_code(template_code)
    reason = str(change_reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "模板新版本必须填写至少5个字符的变更原因")
    permissions = sorted({str(value or "").strip() for value in (permission_codes or []) if str(value or "").strip()})
    assert_custom_role_assignable(permissions, allow_legacy_patterns=False)

    db = get_sessionmaker()()
    try:
        latest = db.scalar(select(RoleTemplate).where(
            RoleTemplate.tenant_id == PLATFORM_TENANT,
            RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
            RoleTemplate.template_code == code,
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc()).limit(1))
        latest_version = int(latest.template_version or 0) if latest else 0
        previous = None
        if source_template_id is not None:
            previous = _load(db, source_template_id, lock=False)
            if previous.template_code != code:
                raise AppException("VALIDATION_ERROR", "回滚/派生源模板 code 不一致")
        elif latest is not None:
            previous = latest

        item = RoleTemplate(
            tenant_id=PLATFORM_TENANT,
            template_code=code,
            template_name=str(template_name or code).strip() or code,
            template_version=latest_version + 1,
            template_plane=TEMPLATE_PLANE_TENANT,
            template_category=TEMPLATE_CATEGORY_SYSTEM_ROLE,
            publish_status=DRAFT,
            permission_digest=_digest(permissions),
            previous_template_id=int(previous.id) if previous is not None else None,
            change_reason=reason,
            source_commit_sha=str(source_commit_sha or "").strip() or None,
            delivered=True,
            bundle_codes_json={"items": []},
            permission_ceiling_json={"items": permissions, "permissionDigest": _digest(permissions)},
            wildcard_json=None,
            status="ACTIVE",
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )
        db.add(item)
        db.flush()
        _sync_permissions(db, item, permissions)
        db.commit()
        db.refresh(item)
        return _row(db, item)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_draft(
    template_id: int,
    *,
    expected_version: int,
    permission_codes,
    change_reason: str,
    actor_user_id: int | None = None,
) -> dict:
    reason = str(change_reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "模板变更必须填写至少5个字符的原因")
    permissions = sorted({str(value or "").strip() for value in (permission_codes or []) if str(value or "").strip()})
    assert_custom_role_assignable(permissions, allow_legacy_patterns=False)
    db = get_sessionmaker()()
    try:
        item = _load(db, template_id, lock=True)
        assert_school_role_template_code(item.template_code)
        if item.publish_status != DRAFT:
            raise AppException("IMMUTABLE_TEMPLATE", "已发布角色模板不可修改；必须新建版本", http_status=409)
        if int(item.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "模板草稿已被其他人修改，请刷新后重试", http_status=409)
        item.change_reason = reason
        item.updated_by = actor_user_id
        item.version = int(item.version or 0) + 1
        _sync_permissions(db, item, permissions)
        db.commit()
        db.refresh(item)
        return _row(db, item)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def impact(template_id: int) -> dict:
    db = get_sessionmaker()()
    try:
        item = _load(db, template_id)
        current = set(_items(db, item))
        previous = _load(db, int(item.previous_template_id)) if item.previous_template_id else None
        before = set(_items(db, previous)) if previous is not None else set()
        pinned = list(db.scalars(select(CustomRoleSource).where(
            CustomRoleSource.source_template_code == item.template_code,
            CustomRoleSource.is_deleted.is_(False),
        ).order_by(CustomRoleSource.tenant_id, CustomRoleSource.role_code)).all())
        return {
            "templateId": str(item.id),
            "templateCode": item.template_code,
            "templateVersion": int(item.template_version or 0),
            "addedPermissions": sorted(current - before),
            "removedPermissions": sorted(before - current),
            "affectedPinnedCustomRoles": [
                {
                    "tenantId": str(role.tenant_id),
                    "roleId": str(role.role_id),
                    "roleCode": role.role_code,
                    "sourceTemplateVersion": int(role.source_template_version or 0),
                    "automaticUpgrade": False,
                    "policy": "DERIVED_PINNED",
                }
                for role in pinned
                if int(role.source_template_version or 0) != int(item.template_version or 0)
            ],
        }
    finally:
        db.close()


def publish_draft(
    template_id: int,
    *,
    expected_version: int,
    actor_user_id: int | None,
    effective_at: datetime | None = None,
) -> dict:
    from app.services import audit_log

    db = get_sessionmaker()()
    try:
        item = _load(db, template_id, lock=True)
        assert_school_role_template_code(item.template_code)
        if item.publish_status != DRAFT:
            raise AppException("IMMUTABLE_TEMPLATE", "只有 DRAFT 模板版本可以发布", http_status=409)
        if int(item.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "模板草稿已被其他人修改，请刷新后重试", http_status=409)
        permissions = _items(db, item)
        assert_custom_role_assignable(permissions, allow_legacy_patterns=False)
        if not permissions:
            raise AppException("VALIDATION_ERROR", "角色模板至少包含一个具体 TENANT permissionCode")
        now = datetime.utcnow()
        digest = _digest(permissions)
        item.publish_status = PUBLISHED
        item.permission_digest = digest
        item.published_at = now
        item.published_by = actor_user_id
        item.effective_at = effective_at or now
        item.updated_by = actor_user_id
        item.version = int(item.version or 0) + 1
        item.permission_ceiling_json = {
            **dict(item.permission_ceiling_json or {}),
            "items": permissions,
            "permissionDigest": digest,
        }
        audit_log.record_critical_in_session(
            db,
            "ROLE_TEMPLATE_PUBLISH",
            f"role-template:{item.template_code}:v{item.template_version}",
            detail={
                "templateCode": item.template_code,
                "templateVersion": int(item.template_version or 0),
                "templatePlane": item.template_plane,
                "permissionDigest": digest,
                "changeReason": item.change_reason or "",
            },
            tenant_id=0,
            resource_id=str(item.id),
        )
        db.commit()
        db.refresh(item)
        published = _row(db, item)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {**published, "impact": impact(template_id)}


def create_rollback_draft(
    source_template_id: int,
    *,
    change_reason: str,
    actor_user_id: int | None,
    source_commit_sha: str = "",
) -> dict:
    db = get_sessionmaker()()
    try:
        source = _load(db, source_template_id)
        if source.publish_status != PUBLISHED:
            raise AppException("VALIDATION_ERROR", "回滚源必须是已发布模板版本")
        source_snapshot = _row(db, source)
    finally:
        db.close()
    return create_draft(
        template_code=source_snapshot["templateCode"],
        template_name=source_snapshot["templateName"],
        permission_codes=source_snapshot["permissions"],
        change_reason=change_reason,
        source_commit_sha=source_commit_sha,
        actor_user_id=actor_user_id,
        source_template_id=source_template_id,
    )
