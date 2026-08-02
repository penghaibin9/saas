"""SYS-06 权限包、交付角色模板与学校自定义角色。

治理层，不接管鉴权
──────────────────
真实鉴权仍然读 ``app.core.permissions.ROLE_PERMISSIONS``。本服务做四件事：

1. 把代码里的角色固化成 **DELIVERED 模板**（只读），并记录每个模板的权限上限快照；
2. 把权限码按域组织成 **权限包**，让页面能用 20~40 个包而不是几百个原子权限来配角色；
3. 学校 **自定义角色必须从模板复制**，保存时校验"不得超出模板上限"；
4. 把 ``*`` / ``module.*`` 登记进 **通配退役队列**，展开可见、可排期。

之所以不直接把鉴权切到数据库：一次性切换会让全系统登录与权限同时受影响，必须双读对账
一个发布周期后再切，属于后续独立步骤。
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.permission_governance import (EFFECT_ALLOW,
                                              ROLE_SOURCE_CUSTOM,
                                              WILDCARD_PENDING,
                                              CustomRoleSource,
                                              PermissionBundle,
                                              PermissionBundleItem,
                                              RoleTemplate, WildcardRetirement)

# 平台交付内容挂在 tenant_id=0 下，各校共享同一份模板与包
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


def all_known_permission_codes() -> set[str]:
    """全部具体权限码。

    直接复用 ``system_admin_catalog_service.collect_concrete_permission_codes``——它才是
    仓库里权限码的权威全集。曾经想当然地从 ``ROLE_PERMISSIONS`` 的值里筛非通配码，结果
    ``systemAdmin.*`` 展开出 0 条：因为 SYS_ADMIN 只声明了通配、没有任何具体码，具体码在
    端点的 require_permission 侧。这类"看起来合理但静默算错"的实现必须避免。
    """
    from app.services.system_admin_catalog_service import \
        collect_concrete_permission_codes

    return set(collect_concrete_permission_codes())


def expand_wildcard(wildcard: str, universe: Iterable[str] | None = None) -> set[str]:
    """把 ``*`` / ``a.b.*`` / ``*.view`` 展开为具体权限码。

    复用既有 ``expand_permission_patterns``，不另写一套匹配规则——它已经处理了前缀通配、
    后缀通配和精确码三种形态，重写只会产生两套不一致的语义。
    """
    from app.services.system_admin_catalog_service import \
        expand_permission_patterns

    expanded = expand_permission_patterns({wildcard})
    if universe is not None:
        return expanded & set(universe)
    return expanded


def _domain_of(code: str) -> str:
    return code.split(".", 1)[0] if "." in code else "GENERAL"


def bootstrap_from_code(*, tenant_id: int | None = None) -> dict:
    """把当前代码里的角色固化为交付模板与权限包（幂等）。

    每个角色一份模板，模板的 ``permission_ceiling_json`` 是它展开后的权限上限；
    持有的通配同时登记进退役队列。重复执行不会产生重复行。
    """
    tid = _tenant_id(tenant_id)
    universe = all_known_permission_codes()
    role_perms = _role_permissions()

    created_bundles = created_templates = created_wildcards = 0
    with _session() as db:
        # 1) 按域建权限包
        by_domain: dict[str, set[str]] = {}
        for code in universe:
            by_domain.setdefault(_domain_of(code), set()).add(code)

        for domain, codes in sorted(by_domain.items()):
            bundle_code = f"{domain.upper()}_ALL"
            exists = db.scalars(
                select(PermissionBundle).where(
                    PermissionBundle.tenant_id == PLATFORM_TENANT,
                    PermissionBundle.bundle_code == bundle_code,
                    PermissionBundle.is_deleted.is_(False),
                )
            ).first()
            if exists:
                continue
            bundle = PermissionBundle(
                tenant_id=PLATFORM_TENANT,
                bundle_code=bundle_code,
                bundle_name=f"{domain} 全部权限",
                owner_domain=domain.upper(),
                delivered=True,
                description=f"由代码 ROLE_PERMISSIONS 固化，共 {len(codes)} 个权限码",
                created_by=_actor_id(),
                updated_by=_actor_id(),
            )
            db.add(bundle)
            db.flush()
            for code in sorted(codes):
                db.add(
                    PermissionBundleItem(
                        tenant_id=PLATFORM_TENANT,
                        bundle_id=int(bundle.id),
                        permission_code=code,
                        effect=EFFECT_ALLOW,
                        created_by=_actor_id(),
                        updated_by=_actor_id(),
                    )
                )
            created_bundles += 1

        # 2) 每个角色一份交付模板
        for role_code, granted in sorted(role_perms.items()):
            wildcards = sorted(c for c in granted if c == "*" or c.endswith(".*"))
            explicit = {c for c in granted if c not in wildcards}
            ceiling = set(explicit)
            for wc in wildcards:
                ceiling |= expand_wildcard(wc, universe)

            exists = db.scalars(
                select(RoleTemplate).where(
                    RoleTemplate.tenant_id == PLATFORM_TENANT,
                    RoleTemplate.template_code == role_code,
                    RoleTemplate.template_version == 1,
                    RoleTemplate.is_deleted.is_(False),
                )
            ).first()
            if not exists:
                db.add(
                    RoleTemplate(
                        tenant_id=PLATFORM_TENANT,
                        template_code=role_code,
                        template_name=role_code,
                        template_version=1,
                        delivered=True,
                        bundle_codes_json={"items": sorted({f"{_domain_of(c).upper()}_ALL" for c in ceiling})},
                        permission_ceiling_json={"items": sorted(ceiling)},
                        wildcard_json={"items": wildcards} if wildcards else None,
                        created_by=_actor_id(),
                        updated_by=_actor_id(),
                    )
                )
                created_templates += 1

            # 3) 通配退役队列（登记在当前学校名下，便于各校分别推进）
            for wc in wildcards:
                exists_wc = db.scalars(
                    select(WildcardRetirement).where(
                        WildcardRetirement.tenant_id == tid,
                        WildcardRetirement.role_code == role_code,
                        WildcardRetirement.wildcard_code == wc,
                        WildcardRetirement.is_deleted.is_(False),
                    )
                ).first()
                if exists_wc:
                    continue
                expanded = sorted(expand_wildcard(wc, universe))
                # 展开为 0 不等于"这个通配没用"——真实鉴权走前缀匹配，不依赖权限目录。
                # 它说明权限目录（SCHOOL_PERMISSION_GROUPS）没覆盖该域，是需要治理的缺口，
                # 必须显式标出来，否则会被当成"无害通配"而漏掉。
                note = (
                    "由 SYS-06 自动登记；展开结果只覆盖权限目录中已登记的权限码，是下界"
                    if expanded
                    else "权限目录未覆盖该前缀：真实鉴权仍按前缀放行，但治理侧看不到它到底放开了什么，需先补全权限目录"
                )
                db.add(
                    WildcardRetirement(
                        tenant_id=tid,
                        role_code=role_code,
                        wildcard_code=wc,
                        expanded_count=len(expanded),
                        expanded_json={"items": expanded},
                        status=WILDCARD_PENDING,
                        note=note,
                        created_by=_actor_id(),
                        updated_by=_actor_id(),
                    )
                )
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
        bundles = db.scalars(
            select(PermissionBundle)
            .where(PermissionBundle.is_deleted.is_(False))
            .order_by(PermissionBundle.owner_domain, PermissionBundle.bundle_code)
        ).all()
        items = []
        for b in bundles:
            count = len(
                db.scalars(
                    select(PermissionBundleItem).where(
                        PermissionBundleItem.bundle_id == b.id,
                        PermissionBundleItem.is_deleted.is_(False),
                    )
                ).all()
            )
            items.append(
                {
                    "bundleCode": b.bundle_code,
                    "bundleName": b.bundle_name,
                    "ownerDomain": b.owner_domain,
                    "riskLevel": b.risk_level,
                    "delivered": bool(b.delivered),
                    "permissionCount": count,
                    "description": b.description,
                }
            )
        return {"items": items}


def list_templates(*, tenant_id: int | None = None) -> dict:
    _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(RoleTemplate)
            .where(RoleTemplate.is_deleted.is_(False), RoleTemplate.status == "ACTIVE")
            .order_by(RoleTemplate.template_code)
        ).all()
        return {
            "items": [
                {
                    "templateCode": r.template_code,
                    "templateName": r.template_name,
                    "templateVersion": int(r.template_version or 1),
                    "delivered": bool(r.delivered),
                    "permissionCount": len((r.permission_ceiling_json or {}).get("items") or []),
                    "wildcards": (r.wildcard_json or {}).get("items") or [],
                    "bundles": (r.bundle_codes_json or {}).get("items") or [],
                }
                for r in rows
            ]
        }


def get_template(template_code: str, *, tenant_id: int | None = None) -> dict:
    _tenant_id(tenant_id)
    with _session() as db:
        row = _load_template(db, template_code)
        return {
            "templateCode": row.template_code,
            "templateName": row.template_name,
            "templateVersion": int(row.template_version or 1),
            "delivered": bool(row.delivered),
            "permissionCeiling": (row.permission_ceiling_json or {}).get("items") or [],
            "wildcards": (row.wildcard_json or {}).get("items") or [],
        }


def _load_template(db, template_code: str) -> RoleTemplate:
    row = db.scalars(
        select(RoleTemplate)
        .where(
            RoleTemplate.template_code == template_code,
            RoleTemplate.is_deleted.is_(False),
            RoleTemplate.status == "ACTIVE",
        )
        .order_by(RoleTemplate.template_version.desc())
    ).first()
    if not row:
        raise not_found(f"交付角色模板不存在：{template_code}")
    return row


def clone_template(
    template_code: str, *, new_role_code: str, permission_codes: list[str] | None = None,
    tenant_id: int | None = None,
) -> dict:
    """从交付模板复制出学校自定义角色。不传权限清单时默认继承模板全部上限。"""
    tid = _tenant_id(tenant_id)
    if not str(new_role_code or "").strip():
        raise AppException("VALIDATION_ERROR", "自定义角色编码不能为空")

    with _session() as db:
        template = _load_template(db, template_code)
        ceiling = set((template.permission_ceiling_json or {}).get("items") or [])
        picked = set(permission_codes) if permission_codes is not None else set(ceiling)

        over = sorted(picked - ceiling)
        if over:
            raise AppException(
                "PERMISSION_EXCEEDS_TEMPLATE",
                "自定义角色的权限超出了交付模板上限",
                http_status=403,
                details={"exceeded": over[:20], "exceededCount": len(over)},
            )

        exists = db.scalars(
            select(CustomRoleSource).where(
                CustomRoleSource.tenant_id == tid,
                CustomRoleSource.role_code == new_role_code,
                CustomRoleSource.is_deleted.is_(False),
            )
        ).first()
        if exists:
            raise AppException("ROLE_ALREADY_EXISTS", f"自定义角色已存在：{new_role_code}", http_status=409)

        row = CustomRoleSource(
            tenant_id=tid,
            role_code=new_role_code,
            source_template_code=template.template_code,
            source_template_version=int(template.template_version or 1),
            permission_codes_json={"items": sorted(picked)},
            status="DRAFT",
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _custom_role_row(row)


def update_custom_role(
    role_code: str, *, permission_codes: list[str], expected_version: int, tenant_id: int | None = None
) -> dict:
    """裁剪自定义角色权限。仍然只能在模板上限内，草稿保存不改变真实鉴权。"""
    tid = _tenant_id(tenant_id)
    with _session() as db:
        row = db.scalars(
            select(CustomRoleSource).where(
                CustomRoleSource.tenant_id == tid,
                CustomRoleSource.role_code == role_code,
                CustomRoleSource.is_deleted.is_(False),
            )
        ).first()
        if not row:
            raise not_found(f"自定义角色不存在：{role_code}")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "该角色已被其他人修改，请刷新后重试", http_status=409)

        template = _load_template(db, row.source_template_code)
        ceiling = set((template.permission_ceiling_json or {}).get("items") or [])
        picked = set(permission_codes or [])
        over = sorted(picked - ceiling)
        if over:
            raise AppException(
                "PERMISSION_EXCEEDS_TEMPLATE",
                "自定义角色的权限超出了交付模板上限",
                http_status=403,
                details={"exceeded": over[:20], "exceededCount": len(over)},
            )
        row.permission_codes_json = {"items": sorted(picked)}
        row.updated_by = _actor_id()
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _custom_role_row(row)


def _custom_role_row(row: CustomRoleSource) -> dict:
    return {
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
        rows = db.scalars(
            select(CustomRoleSource)
            .where(CustomRoleSource.tenant_id == tid, CustomRoleSource.is_deleted.is_(False))
            .order_by(CustomRoleSource.role_code)
        ).all()
        return {"items": [_custom_role_row(r) for r in rows]}


def wildcard_queue(*, tenant_id: int | None = None) -> dict:
    """通配权限退役队列。展开数是下界，页面必须如实标注。"""
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(WildcardRetirement)
            .where(WildcardRetirement.tenant_id == tid, WildcardRetirement.is_deleted.is_(False))
            .order_by(WildcardRetirement.expanded_count.desc())
        ).all()
        items = [
            {
                "roleCode": r.role_code,
                "wildcardCode": r.wildcard_code,
                "expandedCount": int(r.expanded_count or 0),
                # 展开为 0 = 权限目录没覆盖该前缀。真实鉴权仍按前缀放行，
                # 所以这是"看不清它放开了什么"，比普通通配更危险，不能当成没问题。
                "coverageGap": int(r.expanded_count or 0) == 0,
                "status": r.status,
                "note": r.note,
            }
            for r in rows
        ]
        gaps = sorted({i["wildcardCode"] for i in items if i["coverageGap"]})
        return {
            "items": items,
            "coverageGaps": gaps,
            "disclaimer": (
                "展开结果只覆盖权限目录中已登记的权限码，属于下界；"
                f"其中 {len(gaps)} 个前缀权限目录完全没覆盖，真实鉴权仍会按前缀放行，需先补全权限目录再退役"
            ),
        }
