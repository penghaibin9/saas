"""公共文件中心内置业务 resolver 注册。

该模块通过 registry 正式注册，不改写 file_service 函数，不使用运行时 monkey-patch。
"""
from __future__ import annotations

from typing import Any

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
