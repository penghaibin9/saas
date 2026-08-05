"""包 6：公共文件入口与默认对象 ACL 的 fail-closed 安全层。

通用上传只产生 TEMP_PRIVATE 文件。正式业务文件必须依赖 ACTIVE binding 与
业务 resolver；上传者身份、通用模块 view 权限或无范围 BUSINESS_OBJECT 绑定
均不能单独授予正式文件读取权限。
"""
from __future__ import annotations

from typing import Any

from app.core.permissions import has_permission
from app.services import file_access_service as access
from app.services import file_access_resolvers as resolvers


_INSTALLED = False


def _is_temporary_private(file_obj) -> bool:
    """只识别无正式目标的临时对象；正式业务类型绝不能因 owner 放行。"""
    biz_type = str(getattr(file_obj, "biz_type", "") or "").upper()
    visibility = str(getattr(file_obj, "visibility", "") or "PRIVATE").upper()
    status = str(getattr(file_obj, "status", "") or "").upper()
    storage_zone = str(getattr(file_obj, "storage_zone", "") or "").upper()
    no_target = not str(getattr(file_obj, "biz_id", "") or "").strip()
    explicit_temp = biz_type == "TEMP_PRIVATE"
    import_staging = bool(
        biz_type.endswith("_IMPORT_SOURCE")
        and (status in {"UPLOADED", "QUARANTINED", "STORED"} or storage_zone == "QUARANTINE")
    )
    return bool(no_target and visibility == "PRIVATE" and (explicit_temp or import_staging))


def _active_bindings(bindings: list[Any]) -> list[Any]:
    return [
        item
        for item in bindings
        if not bool(getattr(item, "is_deleted", False))
        and str(getattr(item, "status", "") or "").upper() == "ACTIVE"
    ]


def strict_default_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """未知业务类型没有权威 resolver 时仅允许管理临时私有文件。"""
    if _is_temporary_private(file_obj):
        return resolvers._owner_allows(file_obj, user or {})
    active = _active_bindings(bindings)
    return bool(active and any(access._binding_subject_allows(item, user or {}) for item in active))


def strict_scoped_binding_resolver(
    db,
    file_obj,
    bindings: list[Any],
    user: dict,
    action: str,
) -> bool:
    """普通业务文件必须同时具备动作权限与具体对象关系。"""
    if _is_temporary_private(file_obj):
        return resolvers._owner_allows(file_obj, user or {})

    active = _active_bindings(bindings)
    if not active:
        return False

    biz_type = str(getattr(file_obj, "biz_type", "") or "").upper()
    actor = user or {}

    # 实习教师必须先通过具体实习记录/学生指导关系；不能只凭模块权限。
    if biz_type in {"INTERNSHIP", "ENT_EVAL", "LEAVE"}:
        if resolvers._internship_staff_scope_allows(db, file_obj, active, actor):
            return True

    if str(actor.get("userType") or "").upper() == "STUDENT":
        return any(
            str(getattr(item, "subject_type", "") or "").upper() in {"STUDENT", "USER"}
            and access._binding_subject_allows(item, actor)
            for item in active
        )

    permission = access._FILE_VIEW_PERMISSION.get(biz_type)
    if not permission or not has_permission(actor, permission):
        return False
    return any(access._binding_subject_allows(item, actor) for item in active)


def install() -> None:
    """幂等安装公共 ACL；由权威 file contract 在路由加载时执行。"""
    global _INSTALLED
    if _INSTALLED:
        return
    access._default_resolver = strict_default_resolver
    for biz_type in (
        "INTERNSHIP",
        "ENT_EVAL",
        "COURSE_MATERIAL",
        "ATTACHMENT",
        "LEAVE",
        "AID",
        "RISK",
        "MENTAL",
    ):
        access._RESOLVERS[biz_type] = strict_scoped_binding_resolver
    _INSTALLED = True
