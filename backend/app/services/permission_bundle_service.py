"""SYS-06 权限包、RoleTemplate 与学校 CUSTOM Role 治理。

B1/B5 终态：
- t_role 是学校角色唯一 runtime identity；
- t_custom_role_source 通过 role_id 1:1 记录模板/provenance；
- t_role_template_permission 是模板权限规范化真值；
- permission_ceiling_json 仅保留兼容快照；
- DRAFT 自定义角色不物化 RolePermission，只有 SecurityChange 激活才改变 runtime 权限。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from datetime import datetime
from functools import lru_cache
from typing import Iterable

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.permission_governance import (
    EFFECT_ALLOW,
    ROLE_SOURCE_CUSTOM,
    TEMPLATE_CATEGORY_SYSTEM_ROLE,
    TEMPLATE_PLANE_TENANT,
    TEMPLATE_PUBLISHED,
    WILDCARD_PENDING,
    CustomRoleSource,
    PermissionBundle,
    PermissionBundleItem,
    RoleTemplate,
    RoleTemplatePermission,
    WildcardRetirement,
)

PLATFORM_TENANT = 0


def _tenant_id(value: int | None = None) -> int:
    tenant_id = int(value or current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


def _actor_id() -> int | None:
    user = get_current_user_ctx() or {}
    raw = user.get("userId") or user.get("id")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _session():
    return get_sessionmaker()()


def _role_permissions() -> dict[str, set[str]]:
    from app.core.permissions import ROLE_PERMISSIONS
    return ROLE_PERMISSIONS


def _digest(codes) -> str:
    payload = json.dumps(sorted({str(c) for c in (codes or []) if str(c)}), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_CODE_LITERAL = re.compile(r"""['"]([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_*]+)+)['"]""")
_PERMISSION_CALL = re.compile(
    r"(?:require_permission|require_any_permission|require_permission_compat"
    r"|require_any_permission_compat|has_permission|has_any_permission|_entry)\s*\(([^)]*)\)",
    re.S,
)
_PLACEHOLDER_CODES = {"module.domain.action", "a.b.xxx", "a.b.c"}
_EXCLUDED_FILE_HINTS = ("mock_", "_mock", "/tests/", "\\tests\\")
_PERMISSION_MODULES = (
    "app.core.graduation_permissions",
    "app.core.domain_request_permissions",
    "app.core.mobile_graduation_permissions",
    "app.core.mobile_internship_permission_gate",
    "app.core.rbac09_permission_bundles",
)
_CODE_SHAPE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+$")


def _iter_code_like(value, depth: int = 0):
    if depth > 2:
        return
    if isinstance(value, str):
        if _CODE_SHAPE.match(value) and value not in _PLACEHOLDER_CODES:
            yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _iter_code_like(k, depth + 1)
            yield from _iter_code_like(v, depth + 1)
    elif isinstance(value, (set, frozenset, list, tuple)):
        for item in value:
            yield from _iter_code_like(item, depth + 1)


@lru_cache(maxsize=1)
def discover_domain_module_permission_codes() -> frozenset[str]:
    import importlib

    codes: set[str] = set()
    for name in _PERMISSION_MODULES:
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        for attr in dir(module):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(module, attr)
            except Exception:
                continue
            codes.update(_iter_code_like(value))
    return frozenset(codes)


@lru_cache(maxsize=1)
def discover_endpoint_permission_codes() -> frozenset[str]:
    root = pathlib.Path(__file__).resolve().parent.parent
    codes: set[str] = set()
    for path in root.rglob("*.py"):
        text = str(path)
        if any(hint in text.replace("\\", "/") for hint in _EXCLUDED_FILE_HINTS):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for call in _PERMISSION_CALL.finditer(source):
            for code in _CODE_LITERAL.findall(call.group(1)):
                if code in _PLACEHOLDER_CODES or code == "*" or code.endswith(".*"):
                    continue
                codes.add(code)
    return frozenset(codes)


def all_known_permission_codes() -> set[str]:
    from app.services.system_admin_catalog_service import collect_concrete_permission_codes

    codes = set(collect_concrete_permission_codes())
    codes |= set(discover_endpoint_permission_codes())
    codes |= set(discover_domain_module_permission_codes())
    for granted in _role_permissions().values():
        codes |= {c for c in granted if c != "*" and not c.endswith(".*")}
    return codes


def expand_wildcard(wildcard: str, universe: Iterable[str] | None = None) -> set[str]:
    codes = set(universe) if universe is not None else all_known_permission_codes()
    if wildcard == "*":
        return set(codes)
    if wildcard.endswith(".*"):
        prefix = wildcard[:-1]
        return {c for c in codes if c.startswith(prefix) or c == wildcard[:-2]}
    if wildcard.startswith("*."):
        suffix = wildcard[1:]
        return {c for c in codes if c.endswith(suffix)}
    return {wildcard} & codes


def _domain_of(code: str) -> str:
    return code.split(".", 1)[0] if "." in code else "GENERAL"


def _template_permissions(db, template: RoleTemplate) -> list[str]:
    rows = list(db.scalars(select(RoleTemplatePermission.permission_code).where(
        RoleTemplatePermission.tenant_id == template.tenant_id,
        RoleTemplatePermission.role_template_id == template.id,
        RoleTemplatePermission.effect == EFFECT_ALLOW,
        RoleTemplatePermission.is_deleted.is_(False),
    )).all())
    if rows:
        return sorted(set(rows))
    # Upgrade compatibility only. New writes always create normalized rows.
    return sorted(set((template.permission_ceiling_json or {}).get("items") or []))


def _sync_template_permissions(db, template: RoleTemplate, codes) -> None:
    wanted = sorted({str(code) for code in (codes or []) if str(code)})
    existing = list(db.scalars(select(RoleTemplatePermission).where(
        RoleTemplatePermission.tenant_id == template.tenant_id,
        RoleTemplatePermission.role_template_id == template.id,
    )).all())
    by_code = {(row.permission_code, row.effect): row for row in existing}
    for row in existing:
        if row.effect != EFFECT_ALLOW or row.permission_code not in wanted:
            row.is_deleted = True
    for code in wanted:
        key = (code, EFFECT_ALLOW)
        if key in by_code:
            by_code[key].is_deleted = False
        else:
            db.add(RoleTemplatePermission(
                tenant_id=int(template.tenant_id),
                role_template_id=int(template.id),
                permission_code=code,
                effect=EFFECT_ALLOW,
                created_by=_actor_id(),
                updated_by=_actor_id(),
            ))
    template.permission_ceiling_json = {
        **dict(template.permission_ceiling_json or {}),
        "items": wanted,
        "permissionDigest": _digest(wanted),
    }
    template.permission_digest = _digest(wanted)


def bootstrap_from_code(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    universe = all_known_permission_codes()
    role_perms = _role_permissions()
    created_bundles = created_templates = created_wildcards = 0
    now = datetime.utcnow()

    with _session() as db:
        by_domain: dict[str, set[str]] = {}
        for code in universe:
            by_domain.setdefault(_domain_of(code), set()).add(code)

        for domain, codes in sorted(by_domain.items()):
            bundle_code = f"{domain.upper()}_ALL"
            exists = db.scalars(select(PermissionBundle).where(
                PermissionBundle.tenant_id == PLATFORM_TENANT,
                PermissionBundle.bundle_code == bundle_code,
                PermissionBundle.is_deleted.is_(False),
            )).first()
            if exists:
                continue
            bundle = PermissionBundle(
                tenant_id=PLATFORM_TENANT,
                bundle_code=bundle_code,
                bundle_name=f"{domain} 全部权限",
                owner_domain=domain.upper(),
                delivered=True,
                description=f"由代码 ROLE_PERMISSIONS 固化，共 {len(codes)} 个权限码",
                created_by=_actor_id(), updated_by=_actor_id(),
            )
            db.add(bundle)
            db.flush()
            for code in sorted(codes):
                db.add(PermissionBundleItem(
                    tenant_id=PLATFORM_TENANT,
                    bundle_id=int(bundle.id),
                    permission_code=code,
                    effect=EFFECT_ALLOW,
                    created_by=_actor_id(), updated_by=_actor_id(),
                ))
            created_bundles += 1

        for role_code, granted in sorted(role_perms.items()):
            # PLATFORM workforce never enters school RoleTemplate.
            if str(role_code).upper().startswith("PLATFORM_"):
                continue
            wildcards = sorted(c for c in granted if c == "*" or c.endswith(".*"))
            explicit = {c for c in granted if c not in wildcards}
            ceiling = set(explicit)
            for wc in wildcards:
                ceiling |= expand_wildcard(wc, universe)

            template = db.scalars(select(RoleTemplate).where(
                RoleTemplate.tenant_id == PLATFORM_TENANT,
                RoleTemplate.template_code == role_code,
                RoleTemplate.template_version == 1,
                RoleTemplate.is_deleted.is_(False),
            )).first()
            if template is None:
                template = RoleTemplate(
                    tenant_id=PLATFORM_TENANT,
                    template_code=role_code,
                    template_name=role_code,
                    template_version=1,
                    template_plane=TEMPLATE_PLANE_TENANT,
                    template_category=TEMPLATE_CATEGORY_SYSTEM_ROLE,
                    publish_status=TEMPLATE_PUBLISHED,
                    permission_digest=_digest(ceiling),
                    change_reason="bootstrap from ROLE_PERMISSIONS",
                    effective_at=now,
                    published_at=now,
                    published_by=_actor_id(),
                    delivered=True,
                    bundle_codes_json={"items": sorted({f"{_domain_of(c).upper()}_ALL" for c in ceiling})},
                    permission_ceiling_json={"items": sorted(ceiling), "permissionDigest": _digest(ceiling)},
                    wildcard_json={"items": wildcards} if wildcards else None,
                    status="ACTIVE",
                    created_by=_actor_id(), updated_by=_actor_id(),
                )
                db.add(template)
                db.flush()
                created_templates += 1
            _sync_template_permissions(db, template, ceiling)

            for wc in wildcards:
                exists_wc = db.scalars(select(WildcardRetirement).where(
                    WildcardRetirement.tenant_id == tid,
                    WildcardRetirement.role_code == role_code,
                    WildcardRetirement.wildcard_code == wc,
                    WildcardRetirement.is_deleted.is_(False),
                )).first()
                if exists_wc:
                    continue
                expanded = sorted(expand_wildcard(wc, universe))
                note = (
                    "由 SYS-06 自动登记；展开结果取自权限目录+端点扫描+域模块常量+角色名单四个来源"
                    if expanded
                    else "四个来源中均无该前缀的具体权限码：这条通配实际未放开任何权限，属死通配，可安全退役"
                )
                db.add(WildcardRetirement(
                    tenant_id=tid,
                    role_code=role_code,
                    wildcard_code=wc,
                    expanded_count=len(expanded),
                    expanded_json={"items": expanded},
                    status=WILDCARD_PENDING,
                    note=note,
                    created_by=_actor_id(), updated_by=_actor_id(),
                ))
                created_wildcards += 1
        db.commit()

    return {
        "createdBundles": created_bundles,
        "createdTemplates": created_templates,
        "createdWildcards": created_wildcards,
        "knownPermissionCodes": len(universe),
    }


def list_bundles(*, tenant_id: int | None = None) -> dict:
    _tenant_id(tenant_id)
    with _session() as db:
        bundles = db.scalars(select(PermissionBundle).where(
            PermissionBundle.is_deleted.is_(False)
        ).order_by(PermissionBundle.owner_domain, PermissionBundle.bundle_code)).all()
        items = []
        for bundle in bundles:
            count = len(db.scalars(select(PermissionBundleItem).where(
                PermissionBundleItem.bundle_id == bundle.id,
                PermissionBundleItem.is_deleted.is_(False),
            )).all())
            items.append({
                "bundleCode": bundle.bundle_code,
                "bundleName": bundle.bundle_name,
                "ownerDomain": bundle.owner_domain,
                "riskLevel": bundle.risk_level,
                "delivered": bool(bundle.delivered),
                "permissionCount": count,
                "description": bundle.description,
            })
        return {"items": items}


def list_templates(*, tenant_id: int | None = None) -> dict:
    _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(select(RoleTemplate).where(
            RoleTemplate.is_deleted.is_(False),
            RoleTemplate.status == "ACTIVE",
            RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
            RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
        ).order_by(RoleTemplate.template_code, RoleTemplate.template_version.desc())).all()
        seen: set[str] = set()
        items = []
        for row in rows:
            if row.template_code in seen:
                continue
            seen.add(row.template_code)
            items.append({
                "templateCode": row.template_code,
                "templateName": row.template_name,
                "templateVersion": int(row.template_version or 1),
                "templatePlane": row.template_plane,
                "publishStatus": row.publish_status,
                "delivered": bool(row.delivered),
                "permissionCount": len(_template_permissions(db, row)),
                "permissionDigest": row.permission_digest or _digest(_template_permissions(db, row)),
                "wildcards": (row.wildcard_json or {}).get("items") or [],
                "bundles": (row.bundle_codes_json or {}).get("items") or [],
            })
        return {"items": items}


def _load_template(db, template_code: str) -> RoleTemplate:
    row = db.scalars(select(RoleTemplate).where(
        RoleTemplate.tenant_id == PLATFORM_TENANT,
        RoleTemplate.template_code == template_code,
        RoleTemplate.template_plane == TEMPLATE_PLANE_TENANT,
        RoleTemplate.publish_status == TEMPLATE_PUBLISHED,
        RoleTemplate.status == "ACTIVE",
        RoleTemplate.is_deleted.is_(False),
    ).order_by(RoleTemplate.template_version.desc())).first()
    if not row:
        raise not_found(f"已发布 TENANT 角色模板不存在：{template_code}")
    return row


def get_template(template_code: str, *, tenant_id: int | None = None) -> dict:
    _tenant_id(tenant_id)
    with _session() as db:
        row = _load_template(db, template_code)
        permissions = _template_permissions(db, row)
        return {
            "templateCode": row.template_code,
            "templateName": row.template_name,
            "templateVersion": int(row.template_version or 1),
            "templatePlane": row.template_plane,
            "publishStatus": row.publish_status,
            "delivered": bool(row.delivered),
            "permissionCeiling": permissions,
            "permissionDigest": row.permission_digest or _digest(permissions),
            "wildcards": (row.wildcard_json or {}).get("items") or [],
        }


def clone_template(
    template_code: str, *, new_role_code: str, permission_codes: list[str] | None = None,
    tenant_id: int | None = None,
) -> dict:
    """同事务创建 runtime CUSTOM Role + pinned governance source；不提前物化权限。"""
    from app.models import Role

    tid = _tenant_id(tenant_id)
    code = str(new_role_code or "").strip()
    if not code:
        raise AppException("VALIDATION_ERROR", "自定义角色编码不能为空")
    if code.upper().startswith("PLATFORM_"):
        raise AppException("NO_PERMISSION", "学校角色不能使用 PLATFORM_ 命名空间", http_status=403)

    with _session() as db:
        template = _load_template(db, template_code)
        ceiling = set(_template_permissions(db, template))
        picked = set(permission_codes) if permission_codes is not None else set(ceiling)
        over = sorted(picked - ceiling)
        if over:
            raise AppException(
                "PERMISSION_EXCEEDS_TEMPLATE", "自定义角色的权限超出了交付模板上限",
                http_status=403, details={"exceeded": over[:20], "exceededCount": len(over)},
            )

        source_exists = db.scalars(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tid,
            CustomRoleSource.role_code == code,
            CustomRoleSource.is_deleted.is_(False),
        )).first()
        role_exists = db.scalars(select(Role).where(
            Role.tenant_id == tid,
            Role.role_code == code,
            Role.is_deleted.is_(False),
        )).first()
        if source_exists or role_exists:
            raise AppException("ROLE_ALREADY_EXISTS", f"自定义角色已存在：{code}", http_status=409)

        role = Role(
            tenant_id=tid,
            role_code=code,
            role_name=code,
            role_type="CUSTOM",
            status="ACTIVE",
            remark=f"DERIVED_PINNED:{template.template_code}:v{int(template.template_version or 1)}",
            created_by=_actor_id(), updated_by=_actor_id(),
        )
        db.add(role)
        db.flush()
        source = CustomRoleSource(
            tenant_id=tid,
            role_id=int(role.id),
            role_code=code,
            source_template_code=template.template_code,
            source_template_version=int(template.template_version or 1),
            permission_codes_json={"items": sorted(picked)},
            drift_json={"policy": "DERIVED_PINNED", "automaticUpgrade": False},
            status="DRAFT",
            created_by=_actor_id(), updated_by=_actor_id(),
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return _custom_role_row(source)


def _load_custom_role(db, tid: int, role_code: str):
    from app.models import Role

    source = db.scalars(select(CustomRoleSource).where(
        CustomRoleSource.tenant_id == tid,
        CustomRoleSource.role_code == role_code,
        CustomRoleSource.is_deleted.is_(False),
    ).with_for_update()).first()
    if source is None:
        raise not_found(f"自定义角色不存在：{role_code}")
    role = db.scalars(select(Role).where(
        Role.tenant_id == tid,
        Role.id == source.role_id,
        Role.role_code == source.role_code,
        Role.role_type == "CUSTOM",
        Role.is_deleted.is_(False),
    ).with_for_update()).first()
    if role is None:
        raise AppException(
            "CUSTOM_ROLE_BINDING_DRIFT",
            "自定义角色治理源与 runtime Role 绑定已漂移，拒绝继续修改",
            http_status=409,
            details={"roleCode": source.role_code, "roleId": str(source.role_id)},
        )
    return source, role


def update_custom_role(
    role_code: str, *, permission_codes: list[str], expected_version: int, tenant_id: int | None = None
) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        source, role = _load_custom_role(db, tid, role_code)
        if int(source.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "该角色已被其他人修改，请刷新后重试", http_status=409)
        template = _load_template(db, source.source_template_code)
        ceiling = set(_template_permissions(db, template))
        picked = set(permission_codes or [])
        over = sorted(picked - ceiling)
        if over:
            raise AppException(
                "PERMISSION_EXCEEDS_TEMPLATE", "自定义角色的权限超出了交付模板上限",
                http_status=403, details={"exceeded": over[:20], "exceededCount": len(over)},
            )
        source.permission_codes_json = {"items": sorted(picked)}
        source.updated_by = _actor_id()
        source.version = int(source.version or 0) + 1
        role.updated_by = _actor_id()
        role.version = int(role.version or 0) + 1
        db.commit()
        db.refresh(source)
        return _custom_role_row(source)


def _custom_role_row(row: CustomRoleSource) -> dict:
    return {
        "roleId": str(row.role_id),
        "roleCode": row.role_code,
        "sourceTemplate": row.source_template_code,
        "sourceTemplateVersion": int(row.source_template_version or 1),
        "permissionCodes": (row.permission_codes_json or {}).get("items") or [],
        "roleType": ROLE_SOURCE_CUSTOM,
        "status": row.status,
        "version": int(row.version or 0),
    }


def list_custom_roles(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tid,
            CustomRoleSource.is_deleted.is_(False),
        ).order_by(CustomRoleSource.role_code)).all()
        return {"items": [_custom_role_row(row) for row in rows]}


def wildcard_queue(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(select(WildcardRetirement).where(
            WildcardRetirement.tenant_id == tid,
            WildcardRetirement.is_deleted.is_(False),
        ).order_by(WildcardRetirement.expanded_count.desc())).all()
        items = [{
            "roleCode": row.role_code,
            "wildcardCode": row.wildcard_code,
            "expandedCount": int(row.expanded_count or 0),
            "deadWildcard": int(row.expanded_count or 0) == 0,
            "status": row.status,
            "note": row.note,
        } for row in rows]
        dead = sorted({item["wildcardCode"] for item in items if item["deadWildcard"]})
        source_count = len(all_known_permission_codes())
        return {
            "items": items,
            "deadWildcards": dead,
            "sourceCount": source_count,
            "disclaimer": (
                f"展开基于 {source_count} 个权限码全集"
                "（权限目录 + 端点扫描 + 各域权限模块常量 + 角色名单四个来源合并）；"
                f"其中 {len(dead)} 条通配在四个来源中均无对应权限码，实际未放开任何权限，可优先退役"
            ),
        }
