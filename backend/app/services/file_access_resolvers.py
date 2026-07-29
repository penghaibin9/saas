"""公共文件中心内置业务 resolver 注册。

该模块通过 registry 正式注册，不改写 file_service 函数，不使用运行时 monkey-patch。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.permissions import has_permission
from app.services.file_access_service import (
    _FILE_VIEW_PERMISSION,
    _actor_id,
    _actor_student_values,
    _binding_subject_allows,
    _is_file_admin,
    register_file_resolver,
)


@register_file_resolver(
    "GRADUATION_MATERIAL",
    "INTERNSHIP",
    "COURSE_MATERIAL",
    "ATTACHMENT",
    "LEAVE",
    "AID",
    "RISK",
    "MENTAL",
)
def scoped_binding_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    actor_id = _actor_id(user)
    owner = str(file_obj.owner_user_id or file_obj.created_by or "").strip()
    if actor_id and owner and actor_id == owner:
        return True
    if _is_file_admin(user):
        return True

    active = [item for item in bindings if not item.is_deleted and item.status == "ACTIVE"]
    if active:
        subject_allowed = any(_binding_subject_allows(item, user) for item in active)
        if not subject_allowed:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            return any(
                str(item.subject_type or "").upper() in {"STUDENT", "USER"}
                and _binding_subject_allows(item, user)
                for item in active
            )
        permission = _FILE_VIEW_PERMISSION.get(str(file_obj.biz_type or "").upper())
        return bool(permission and has_permission(user, permission))

    # 历史对象没有绑定表时，仅兼容本人或明确业务权限。
    if str(user.get("userType") or "").upper() == "STUDENT":
        biz_id = str(file_obj.biz_id or "").strip()
        return bool(biz_id and biz_id in _actor_student_values(user))
    permission = _FILE_VIEW_PERMISSION.get(str(file_obj.biz_type or "").upper())
    return bool(permission and has_permission(user, permission))


@register_file_resolver("AFFAIRS_ARCHIVE")
def affairs_archive_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学工归档文件：archive.view 与目标学生数据范围必须同时成立。"""
    if not has_permission(user or {}, "studentAffairs.archive.view"):
        return False
    student_id = str(file_obj.biz_id or "").strip()
    if not student_id.isdigit() or db is None:
        return False
    try:
        from app.core.affairs_security import build_affairs_context

        build_affairs_context(user or {}, db).require_student(db, int(student_id))
        return True
    except Exception:
        return False


@register_file_resolver("MATERIAL_REQUIREMENT")
def material_requirement_resolver(db, file_obj, bindings: list[Any], user: dict, action: str) -> bool:
    """学工补材料附件：业务权限与材料目标学生范围必须同时成立。"""
    raw_id = str(file_obj.biz_id or "").strip()
    if not raw_id.isdigit() or db is None:
        return False
    try:
        from app.models.affairs_operations import AffairsMaterialRequirement
        from app.services import affairs_operations_service as operations

        requirement = db.scalars(select(AffairsMaterialRequirement).where(
            AffairsMaterialRequirement.tenant_id == int(file_obj.tenant_id),
            AffairsMaterialRequirement.id == int(raw_id),
            AffairsMaterialRequirement.is_deleted.is_(False),
        )).first()
        if not requirement:
            return False
        permissions = operations._BIZ_PERMISSIONS.get(requirement.biz_type, ())
        if not any(has_permission(user or {}, code) for code in permissions):
            return False
        operations._require_student_scope(db, requirement.student_id, user or {})
        return True
    except Exception:
        return False
