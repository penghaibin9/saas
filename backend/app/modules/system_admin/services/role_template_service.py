"""B5 immutable RoleTemplate versioning on the existing schema.

No new table/relation is introduced here. ``permission_ceiling_json.items``
remains backward-compatible while metadata is embedded beside it until the B5
normalized relation migration is allowed after E-A01 releases Alembic.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.core.permission_catalog import assert_custom_role_assignable
from app.db.session import get_sessionmaker
from app.models.permission_governance import CustomRoleSource, RoleTemplate
from app.modules.system_admin.policies.role_template_plane import assert_school_role_template_code

PLATFORM_TENANT = 0
DRAFT = "DRAFT"
PUBLISHED = "PUBLISHED"
LEGACY_PUBLISHED = "ACTIVE"


def _digest(codes) -> str:
    payload = json.dumps(sorted(set(codes or [])), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _items(template: RoleTemplate) -> list[str]:
    return sorted(set((template.permission_ceiling_json or {}).get("items") or []))


def _row(template: RoleTemplate) -> dict:
    ceiling = dict(template.permission_ceiling_json or {})
    return {
        "id": str(template.id),
        "templateCode": template.template_code,
        "templateName": template.template_name,
        "templateVersion": int(template.template_version or 0),
        "publishStatus": "PUBLISHED" if template.status in {PUBLISHED, LEGACY_PUBLISHED} else template.status,
        "storedStatus": template.status,
        "permissions": _items(template),
        "permissionDigest": ceiling.get("permissionDigest") or _digest(_items(template)),
        "previousTemplateVersion": ceiling.get("previousTemplateVersion"),
        "changeReason": ceiling.get("changeReason") or "",
        "sourceCommitSha": ceiling.get("sourceCommitSha") or "",
        "effectiveAt": ceiling.get("effectiveAt"),
        "publishedAt": ceiling.get("publishedAt"),
        "publishedBy": ceiling.get("publishedBy"),
        "version": int(template.version or 0),
    }


def _load(db, template_id: int, *, lock: bool = False) -> RoleTemplate:
    stmt = select(RoleTemplate).where(
        RoleTemplate.id == int(template_id),
        RoleTemplate.tenant_id == PLATFORM_TENANT,
        RoleTemplate.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    item = db.scalar(stmt)
    if item is None:
        raise AppException("DATA_NOT_FOUND", "角色模板不存在", http_status=404)
    return item


def list_versions(template_code: str) -> list[dict]:
    code = assert_school_role_template_code(template_code)
    db = get_sessionmaker()()
    try:
        rows = list(db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == PLATFORM_TENANT,
            RoleTemplate.template_code == code,
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc())).all())
        return [_row(item) for item in rows]
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
    assert_custom_role_assignable(permissions, allow_legacy_patterns=True)

    db = get_sessionmaker()()
    try:
        latest_version = int(db.scalar(select(func.max(RoleTemplate.template_version)).where(
            RoleTemplate.tenant_id == PLATFORM_TENANT,
            RoleTemplate.template_code == code,
            RoleTemplate.is_deleted.is_(False),
        )) or 0)
        if source_template_id is not None:
            source = _load(db, source_template_id, lock=False)
            if source.template_code != code:
                raise AppException("VALIDATION_ERROR", "回滚/派生源模板 code 不一致")
            previous_version = int(source.template_version or 0)
        else:
            previous_version = latest_version or None
        item = RoleTemplate(
            tenant_id=PLATFORM_TENANT,
            template_code=code,
            template_name=str(template_name or code).strip() or code,
            template_version=latest_version + 1,
            delivered=True,
            bundle_codes_json={"items": []},
            permission_ceiling_json={
                "items": permissions,
                "permissionDigest": _digest(permissions),
                "previousTemplateVersion": previous_version,
                "changeReason": reason,
                "sourceCommitSha": str(source_commit_sha or "").strip(),
                "templatePlane": "TENANT",
                "templateCategory": "SYSTEM_ROLE",
                "derivationPolicy": "MANAGED",
            },
            wildcard_json=None,
            status=DRAFT,
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return _row(item)
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
    assert_custom_role_assignable(permissions, allow_legacy_patterns=True)
    db = get_sessionmaker()()
    try:
        item = _load(db, template_id, lock=True)
        assert_school_role_template_code(item.template_code)
        if item.status != DRAFT:
            raise AppException("IMMUTABLE_TEMPLATE", "已发布角色模板不可修改；必须新建版本", http_status=409)
        if int(item.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "模板草稿已被其他人修改，请刷新后重试", http_status=409)
        ceiling = dict(item.permission_ceiling_json or {})
        ceiling.update({
            "items": permissions,
            "permissionDigest": _digest(permissions),
            "changeReason": reason,
        })
        item.permission_ceiling_json = ceiling
        item.updated_by = actor_user_id
        item.version = int(item.version or 0) + 1
        db.commit()
        db.refresh(item)
        return _row(item)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def impact(template_id: int) -> dict:
    db = get_sessionmaker()()
    try:
        item = _load(db, template_id)
        current = set(_items(item))
        previous = None
        previous_version = (item.permission_ceiling_json or {}).get("previousTemplateVersion")
        if previous_version:
            previous = db.scalar(select(RoleTemplate).where(
                RoleTemplate.tenant_id == PLATFORM_TENANT,
                RoleTemplate.template_code == item.template_code,
                RoleTemplate.template_version == int(previous_version),
                RoleTemplate.is_deleted.is_(False),
            ))
        before = set(_items(previous)) if previous is not None else set()
        pinned = list(db.scalars(
            select(CustomRoleSource).where(
                CustomRoleSource.source_template_code == item.template_code,
                CustomRoleSource.is_deleted.is_(False),
            ).order_by(CustomRoleSource.tenant_id, CustomRoleSource.role_code)
        ).all())
        return {
            "templateId": str(item.id),
            "templateCode": item.template_code,
            "templateVersion": int(item.template_version or 0),
            "addedPermissions": sorted(current - before),
            "removedPermissions": sorted(before - current),
            "affectedPinnedCustomRoles": [
                {
                    "tenantId": str(role.tenant_id),
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
        if item.status != DRAFT:
            raise AppException("IMMUTABLE_TEMPLATE", "只有 DRAFT 模板版本可以发布", http_status=409)
        if int(item.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "模板草稿已被其他人修改，请刷新后重试", http_status=409)
        permissions = _items(item)
        assert_custom_role_assignable(permissions, allow_legacy_patterns=True)
        ceiling = dict(item.permission_ceiling_json or {})
        now = datetime.utcnow()
        ceiling.update({
            "permissionDigest": _digest(permissions),
            "publishedAt": now.isoformat(timespec="seconds"),
            "publishedBy": actor_user_id,
            "effectiveAt": (effective_at or now).isoformat(timespec="seconds"),
            "immutable": True,
        })
        item.permission_ceiling_json = ceiling
        item.status = PUBLISHED
        item.updated_by = actor_user_id
        item.version = int(item.version or 0) + 1
        audit_log.record_critical_in_session(
            db,
            "ROLE_TEMPLATE_PUBLISH",
            f"role-template:{item.template_code}:v{item.template_version}",
            detail={
                "templateCode": item.template_code,
                "templateVersion": int(item.template_version or 0),
                "permissionDigest": ceiling["permissionDigest"],
                "changeReason": ceiling.get("changeReason") or "",
            },
            tenant_id=0,
            resource_id=str(item.id),
        )
        db.commit()
        db.refresh(item)
        return {**_row(item), "impact": impact(int(item.id))}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
        source_snapshot = _row(source)
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
