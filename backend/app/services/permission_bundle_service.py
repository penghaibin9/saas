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

import pathlib
import re
from functools import lru_cache
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


# 权限码形态：至少两段、点分。用于从源码里识别字符串字面量。
_CODE_LITERAL = re.compile(r"""['"]([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_*]+)+)['"]""")

# 会携带权限码的调用点：端点鉴权依赖、直接判定、以及菜单预设登记。
# ``_entry`` 是 runtime_preset_install_service 里登记菜单的工厂，dataCenter.dashboard.view
# 这类"只有菜单、没有端点校验"的权限码只能从这里发现。
_PERMISSION_CALL = re.compile(
    r"(?:require_permission|require_any_permission|require_permission_compat"
    r"|require_any_permission_compat|has_permission|has_any_permission|_entry)\s*\(([^)]*)\)",
    re.S,
)

# 明确排除：文档示例里的占位符，以及 mock/演示数据里的假权限码。
_PLACEHOLDER_CODES = {"module.domain.action", "a.b.xxx", "a.b.c"}
_EXCLUDED_FILE_HINTS = ("mock_", "_mock", "/tests/", "\\tests\\")


# 各业务域自带的权限定义模块。它们用 f-string 等方式动态生成权限码
# （如 ``{f"graduationDesign.guidance.{x}" for x in (...)}"``），正则扫源码扫不到，
# 只能在运行时读它们的模块级常量。
_PERMISSION_MODULES = (
    "app.core.graduation_permissions",
    "app.core.domain_request_permissions",
    "app.core.mobile_graduation_permissions",
    "app.core.mobile_internship_permission_gate",
    "app.core.rbac09_permission_bundles",
)

_CODE_SHAPE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+$")


def _iter_code_like(value, depth: int = 0):
    """从常量里挖出形如 ``a.b.c`` 的权限码，容器最多下钻两层。"""
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
    """读取各业务域权限模块导出的常量。导入失败的模块跳过，不影响整体。"""
    import importlib

    codes: set[str] = set()
    for name in _PERMISSION_MODULES:
        try:
            module = importlib.import_module(name)
        except Exception:  # noqa: BLE001 - 某个域模块不可用不该拖垮权限治理页面
            continue
        for attr in dir(module):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(module, attr)
            except Exception:  # noqa: BLE001
                continue
            codes.update(_iter_code_like(value))
    return frozenset(codes)


@lru_cache(maxsize=1)
def discover_endpoint_permission_codes() -> frozenset[str]:
    """扫描源码，找出真实被校验或被菜单登记的权限码。

    为什么必须扫源码：权限目录 ``SCHOOL_PERMISSION_GROUPS`` 是人工维护的，实测发现它
    完全没覆盖 ``employment`` / ``dataCenter`` 等域。而真实鉴权按前缀放行，不查目录——
    也就是说这些权限**确实在生效**，只是治理侧看不见。靠人去补目录必然再次滞后，
    所以这里以代码为准自动发现，新增端点无需再手工登记。

    结果缓存在进程内：源码在运行期不变，扫描一次即可。
    """
    root = pathlib.Path(__file__).resolve().parent.parent  # backend/app
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
                if code in _PLACEHOLDER_CODES:
                    continue
                if code == "*" or code.endswith(".*"):
                    continue
                codes.add(code)
    return frozenset(codes)


def all_known_permission_codes() -> set[str]:
    """全部具体权限码 = 权限目录 ∪ 端点/菜单扫描结果 ∪ 角色名单里的具体码。

    三个来源缺一不可：
    - 权限目录 ``collect_concrete_permission_codes``：带展示名，是页面勾选的基础；
    - 端点与菜单扫描：目录漏掉的域（employment / dataCenter 等）只能从这里补全；
    - ``ROLE_PERMISSIONS`` 里的非通配码：少数只在角色名单里出现、没有端点的码。

    曾经只用第一个来源，``systemAdmin.*`` 展开出 0 条——因为具体码在端点侧不在角色侧；
    也曾想当然地只用角色名单，同样是 0。两次都不报错，静默算错，所以三源合并。
    """
    from app.services.system_admin_catalog_service import \
        collect_concrete_permission_codes

    codes = set(collect_concrete_permission_codes())
    codes |= set(discover_endpoint_permission_codes())
    codes |= set(discover_domain_module_permission_codes())
    for granted in _role_permissions().values():
        codes |= {c for c in granted if c != "*" and not c.endswith(".*")}
    return codes


def expand_wildcard(wildcard: str, universe: Iterable[str] | None = None) -> set[str]:
    """把 ``*`` / ``a.b.*`` / ``*.view`` 展开为具体权限码。

    匹配语义与既有 ``expand_permission_patterns`` 保持一致（前缀通配、后缀通配、精确码），
    但**不能直接调用它**：它内部把全集写死成权限目录，而目录漏了 employment / dataCenter
    等域，用它展开会重新掉进"展开 0 条"的坑。这里改为对合并后的全集做同样的匹配。
    """
    codes = set(universe) if universe is not None else all_known_permission_codes()
    if wildcard == "*":
        return set(codes)
    if wildcard.endswith(".*"):
        prefix = wildcard[:-1]  # 保留末尾的点，"a.b.*" → "a.b."
        return {c for c in codes if c.startswith(prefix) or c == wildcard[:-2]}
    if wildcard.startswith("*."):
        suffix = wildcard[1:]  # "*.view" → ".view"
        return {c for c in codes if c.endswith(suffix)}
    return {wildcard} & codes


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
                # 全集已合并权限目录、端点扫描、域模块常量和角色名单四个来源。
                # 到这一步仍展开为 0，说明整个仓库都找不到该前缀的具体权限码——
                # 也就是这条通配实际上什么都没放开，是历史遗留的死通配，可安全退役。
                # 注意区别于早期版本：那时展开为 0 是因为全集取源不全（真在放行却看不见），
                # 两者危险程度完全相反，不能用同一句话描述。
                note = (
                    "由 SYS-06 自动登记；展开结果取自权限目录+端点扫描+域模块常量+角色名单四个来源"
                    if expanded
                    else "四个来源中均无该前缀的具体权限码：这条通配实际未放开任何权限，属死通配，可安全退役"
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
                # 展开为 0 = 四个来源里都找不到该前缀的具体权限码，这条通配实际未放开任何东西。
                # 这类可以安全退役，风险最低——优先从它们开始清理。
                "deadWildcard": int(r.expanded_count or 0) == 0,
                "status": r.status,
                "note": r.note,
            }
            for r in rows
        ]
        dead = sorted({i["wildcardCode"] for i in items if i["deadWildcard"]})
        return {
            "items": items,
            "deadWildcards": dead,
            "sourceCount": len(all_known_permission_codes()),
            "disclaimer": (
                f"展开基于 {len(all_known_permission_codes())} 个权限码全集"
                "（权限目录 + 端点扫描 + 各域权限模块常量 + 角色名单四个来源合并）；"
                f"其中 {len(dead)} 条通配在四个来源中均无对应权限码，实际未放开任何权限，可优先退役"
            ),
        }
